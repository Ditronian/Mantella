from enum import Enum
import logging
from threading import Thread, Lock
import time
from typing import Any
from openai.types.chat import ChatCompletionMessageParam
from src.llm.ai_client import AIClient
from src.llm.sentence_content import SentenceTypeEnum, sentence_content
from src.characters_manager import Characters
from src.conversation.conversation_log import conversation_log
from src.conversation.action import action
from src.llm.sentence_queue import sentence_queue
from src.llm.sentence import sentence
from src.remember.remembering import remembering
from src.output_manager import ChatManager
from src.llm.messages import assistant_message, system_message, user_message
from src.conversation.context import context
from src.llm.message_thread import message_thread
from src.conversation.conversation_type import conversation_type, multi_npc, pc_to_npc, radiant
from src.character_manager import Character
from src.http.communication_constants import communication_constants as comm_consts
from src.stt import Transcriber
import src.utils as utils

class conversation_continue_type(Enum):
    NPC_TALK = 1
    PLAYER_TALK = 2
    END_CONVERSATION = 3

class conversation:
    TOKEN_LIMIT_PERCENT: float = 0.9
    TOKEN_LIMIT_RELOAD_MESSAGES: float = 0.1
    """Controls the flow of a conversation."""
    def __init__(self, context_for_conversation: context, output_manager: ChatManager, rememberer: remembering, llm_client: AIClient, stt: Transcriber | None, mic_input: bool, mic_ptt: bool) -> None:
        
        self.__context: context = context_for_conversation
        self.__mic_input: bool = mic_input
        self.__mic_ptt: bool = mic_ptt
        self.__allow_interruption: bool = context_for_conversation.config.allow_interruption # allow mic interruption
        self.__is_player_interrupting = False
        self.__stt: Transcriber | None = stt
        self.__events_refresh_time: float = context_for_conversation.config.events_refresh_time  # Time in seconds before events are considered stale
        self.__transcribed_text: str | None = None
        if not self.__context.npcs_in_conversation.contains_player_character(): # TODO: fix this being set to a radiant conversation because of NPCs in conversation not yet being added
            self.__conversation_type: conversation_type = radiant(context_for_conversation.config)
        else:
            self.__conversation_type: conversation_type = pc_to_npc(context_for_conversation.config)        
        self.__messages: message_thread = message_thread(self.__context.config, None)
        self.__output_manager: ChatManager = output_manager
        self.__rememberer: remembering = rememberer
        self.__llm_client = llm_client
        self.__has_already_ended: bool = False
        self.__allow_mic_input: bool = True # this flag ensures mic input is disabled on conversation end
        self.__sentences: sentence_queue = sentence_queue()
        self.__generation_thread: Thread | None = None
        self.__generation_start_lock: Lock = Lock()
        # self.__actions: list[action] = actions
        self.__nsfw_enabled: bool = False
        self.__normal_model: str = context_for_conversation.config.llm
        self.__nsfw_model: str = context_for_conversation.config.nsfw_model
        self.last_sentence_audio_length = 0
        self.last_sentence_start_time = time.time()
        self.__end_conversation_keywords = utils.parse_keywords(context_for_conversation.config.end_conversation_keyword)

    @property
    def has_already_ended(self) -> bool:
        return self.__has_already_ended
    
    @property
    def context(self) -> context:
        return self.__context
    
    @property
    def output_manager(self) -> ChatManager:
        return self.__output_manager
    
    @property
    def transcribed_text(self) -> str | None:
        return self.__transcribed_text
    
    @property
    def stt(self) -> Transcriber | None:
        return self.__stt
    
    @utils.time_it
    def add_or_update_character(self, new_character: list[Character]):
        """Adds or updates a character in the conversation.

        Args:
            new_character (Character): the character to add or update
        """
        characters_removed_by_update = self.__context.add_or_update_characters(new_character)
        if len(characters_removed_by_update) > 0:
            all_characters = self.__context.npcs_in_conversation.get_all_characters()
            all_characters.extend(characters_removed_by_update)
            self.__save_conversations_for_characters(all_characters, is_reload=True)

    @utils.time_it
    def start_conversation(self) -> tuple[str, sentence | None]:
        """Starts a new conversation.

        Returns:
            tuple[str, sentence | None]: Returns a tuple consisting of a reply type and an optional sentence
        """
        # Check radiant topic for NSFW keyword before generating greeting
        if isinstance(self.__conversation_type, radiant):
            radiant_topic = self.__context.get_custom_context_value("radiant_topic")
            if radiant_topic and isinstance(radiant_topic, str) and radiant_topic.strip():
                cleaned_topic = self.__check_and_strip_nsfw_from_direction(radiant_topic)
                if cleaned_topic != radiant_topic:
                    self.__context.set_custom_context_value("radiant_topic", cleaned_topic)

        greeting: user_message | None = self.__conversation_type.get_user_message(self.__context, self.__messages)
        if greeting:
            self.__messages.add_message(greeting)
            self.__start_generating_npc_sentences()
            return comm_consts.KEY_REPLYTYPE_NPCTALK, None
        else:
            return comm_consts.KEY_REPLYTYPE_PLAYERTALK, None

    @utils.time_it
    def continue_conversation(self) -> tuple[str, sentence | None]:
        """Main workhorse of the conversation. Decides what happens next based on the state of the conversation

        Returns:
            tuple[str, sentence | None]: Returns a tuple consisting of a reply type and an optional sentence
        """
        if self.has_already_ended:
            return comm_consts.KEY_REPLYTYPE_ENDCONVERSATION, None
        if self.__llm_client.is_too_long(self.__messages, self.TOKEN_LIMIT_PERCENT):
            # Check if conversation too long and if yes initiate intermittent reload
            self.__initiate_reload_conversation()

        # Check for radiant direction before other processing
        radiant_direction = self.__should_direct_radiant_npc()
        if radiant_direction:
            radiant_direction = self.__check_and_strip_nsfw_from_direction(radiant_direction)
            logging.info(f"Radiant direction detected: {radiant_direction}")
            with self.__generation_start_lock:
                self.__stop_generation()
                self.__sentences.clear()
                self.__add_radiant_direction(radiant_direction)
                self.__context.clear_custom_context_value("radiant_direction")
            self.__start_generating_npc_sentences()
            return comm_consts.KEY_REPLYTYPE_NPCTALK, None

        # interrupt response if player has spoken
        if self.__stt and self.__stt.has_player_spoken:
            self.__stop_generation()
            self.__sentences.clear()
            self.__is_player_interrupting = True
            return comm_consts.KEY_REQUESTTYPE_TTS, None
        
        # restart mic listening as soon as NPC's first sentence is processed
        if self.__mic_input and self.__allow_interruption and not self.__mic_ptt and not self.__stt.is_listening and self.__allow_mic_input and not isinstance(self.__conversation_type, radiant):
            mic_prompt = self.__get_mic_prompt()
            self.__stt.start_listening(mic_prompt)
        
        #Grab the next sentence from the queue
        next_sentence: sentence | None = self.retrieve_sentence_from_queue()
        
        if next_sentence and len(next_sentence.text) > 0:
            if comm_consts.ACTION_REMOVECHARACTER in next_sentence.actions:
                self.__context.remove_character(next_sentence.speaker)
            #if there is a next sentence and it actually has content, return it as something for an NPC to say
            if self.last_sentence_audio_length > 0:
                logging.debug(f'Waiting {round(self.last_sentence_audio_length, 1)} seconds for last voiceline to play')
            # before immediately sending the next voiceline, give the player the chance to interrupt
            while time.time() - self.last_sentence_start_time < self.last_sentence_audio_length:
                if self.__stt and self.__stt.has_player_spoken:
                    self.__stop_generation()
                    self.__sentences.clear()
                    self.__is_player_interrupting = True
                    return comm_consts.KEY_REQUESTTYPE_TTS, None
                time.sleep(0.01)
            self.last_sentence_audio_length = next_sentence.voice_line_duration + self.__context.config.wait_time_buffer
            self.last_sentence_start_time = time.time()
            return comm_consts.KEY_REPLYTYPE_NPCTALK, next_sentence
        else:
            #Ask the conversation type here, if we should end the conversation
            if self.__conversation_type.should_end(self.__context, self.__messages):
                self.initiate_end_sequence()
                return comm_consts.KEY_REPLYTYPE_NPCTALK, None
            else:
                #If not ended, ask the conversation type for an automatic user message. If there is None, signal the game that the player must provide it 
                new_user_message = self.__conversation_type.get_user_message(self.__context, self.__messages)
                if new_user_message:
                    self.__messages.add_message(new_user_message)
                    self.__start_generating_npc_sentences()
                    return comm_consts.KEY_REPLYTYPE_NPCTALK, None
                else:
                    return comm_consts.KEY_REPLYTYPE_PLAYERTALK, None

    @utils.time_it
    def process_player_input(self, player_text: str) -> tuple[str, bool, sentence|None]:
        """Submit the input of the player to the conversation

        Args:
            player_text (str): The input text / voice transcribe of what the player character is supposed to say. Can be empty if mic input has not yet been parsed

        Returns:
            tuple[str, bool]: Returns a tuple consisting of updated player text (if using mic input) and whether or not in-game events need to be refreshed (depending on how much time has passed)
        """
        player_character = self.__context.npcs_in_conversation.get_player_character()
        if not player_character:
            return '', False, None # If there is no player in the conversation, exit here
        
        events_need_updating: bool = False

        with self.__generation_start_lock: #This lock makes sure no new generation by the LLM is started while we clear this
            self.__stop_generation() # Stop generation of additional sentences right now
            self.__sentences.clear() # Clear any remaining sentences from the list

            # If the player's input does not already exist, parse mic input if mic is enabled
            if self.__mic_input and len(player_text) == 0:
                player_text = None
                if not self.__stt.is_listening and self.__allow_mic_input:
                    self.__stt.start_listening(self.__get_mic_prompt())
                
                # Start tracking how long it has taken to receive a player response
                input_wait_start_time = time.time()
                while not player_text:
                    player_text = self.__stt.get_latest_transcription()
                if time.time() - input_wait_start_time >= self.__events_refresh_time:
                    # If too much time has passed, in-game events need to be updated
                    events_need_updating = True
                    logging.debug('Updating game events...')
                    return player_text, events_need_updating, None
                
                # Stop listening once input has been detected to give the NPC a chance to speak
                # This also needs to apply when interruptions are allowed, 
                # otherwise the player could constantly speak over the NPC and never hear a response
                self.__stt.stop_listening()
            
            new_message: user_message = user_message(self.__context.config, player_text, player_character.name, False)
            new_message.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
            new_message = self.update_game_events(new_message)
            text = new_message.text
            logging.log(23, f"Text passed to NPC: {text}")

            # Check for special keywords BEFORE generating player voiceline or adding to messages
            # This prevents TTS generation for command keywords
            is_resume = self.__should_resume_conversation(text)
            redo_guidance = self.__should_redo_response(text)
            direct_instruction = self.__should_direct_npc(text)
            nsfw_toggle = self.__should_toggle_nsfw(text)

            # Only generate player voiceline if this isn't a special command
            # Note: redo_guidance can be None (not a redo), "" (redo without guidance), or a string (redo with guidance)
            if not is_resume and redo_guidance is None and direct_instruction is None and nsfw_toggle is None:
                player_voiceline = self.__get_player_voiceline(player_character, player_text)
            else:
                player_voiceline = None  # No voiceline for command keywords

            # Now add message to thread
            self.__messages.add_message(new_message)

        # Check if player wants to resume from previous conversation history
        if self.__should_resume_conversation(text):
            logging.info("Resume conversation keyword detected. Loading previous conversation history...")
            self.__load_previous_conversation_history()
            # Remove the "restart" message from the thread since it's not part of the actual conversation
            # We need to remove the message we just added
            # For now, just mark it as system-generated so it doesn't get saved
            new_message.is_system_generated_message = True
            # Don't start generation - just return so game can continue
            return player_text, events_need_updating, player_voiceline

        # Check if player wants to redo the last NPC response
        # redo_guidance is None if not a redo, "" if redo without guidance, or a string if redo with guidance
        if redo_guidance is not None:
            if redo_guidance:
                logging.info(f"Redo command detected with guidance: {redo_guidance}")
            else:
                logging.info("Redo command detected (no specific guidance)")
            # Mark the original "Redo: ..." message as system-generated so it doesn't get saved
            new_message.is_system_generated_message = True
            # Execute the redo
            if self.__redo_last_response(redo_guidance, player_character.name if player_character else ""):
                # Start new generation with the redo directive
                self.__start_generating_npc_sentences()
            # Return so game can continue
            return player_text, events_need_updating, player_voiceline

        # Check if player is giving direct instructions to NPCs
        if direct_instruction is not None:
            logging.info(f"Direct command detected: {direct_instruction}")
            # Mark the original "Direct: ..." message as system-generated so it doesn't get saved
            new_message.is_system_generated_message = True
            # Add the director's instruction
            if self.__add_direct_instruction(direct_instruction, player_character.name if player_character else ""):
                # Start new generation with the direct instruction
                self.__start_generating_npc_sentences()
            # Return so game can continue
            return player_text, events_need_updating, player_voiceline

        # Check if player is toggling NSFW mode
        if nsfw_toggle is not None:
            new_message.is_system_generated_message = True
            self.__toggle_nsfw_mode(nsfw_toggle == "on")
            return player_text, events_need_updating, player_voiceline

        ejected_npc = self.__does_dismiss_npc_from_conversation(text)
        if ejected_npc:
            self.__prepare_eject_npc_from_conversation(ejected_npc)
        elif self.__has_conversation_ended(text):
            new_message.is_system_generated_message = True # Flag message containing goodbye as a system message to exclude from summary
            self.initiate_end_sequence()
        else:
            self.__start_generating_npc_sentences()

        return player_text, events_need_updating, player_voiceline

    def __get_mic_prompt(self):
        mic_prompt = f"This is a conversation with {self.__context.get_character_names_as_text(False)} in {self.__context.location}."
        #logging.log(23, f'Context for mic transcription: {mic_prompt}')
        return mic_prompt
    
    @utils.time_it
    def __get_player_voiceline(self, player_character: Character | None, player_text: str) -> sentence | None:
        """Synthesizes the player's input if player voice input is enabled, or else returns None
        """
        player_character_voiced_sentence: sentence | None = None
        if self.__should_voice_player_input(player_character):
            player_character_voiced_sentence = self.__output_manager.generate_sentence(sentence_content(player_character, player_text, SentenceTypeEnum.SPEECH, False))
            if player_character_voiced_sentence.error_message:
                player_message_content: sentence_content = sentence_content(player_character, player_text, SentenceTypeEnum.SPEECH, False)
                player_character_voiced_sentence = sentence(player_message_content, "" , 2.0)

        return player_character_voiced_sentence

    @utils.time_it
    def update_context(self, location: str | None, time: int, custom_ingame_events: list[str], weather: str, custom_context_values: dict[str, Any]):
        """Updates the context with a new set of values

        Args:
            location (str): the location the characters are currently in
            time (int): the current ingame time
            custom_ingame_events (list[str]): a list of events that happend since the last update
            custom_context_values (dict[str, Any]): the current set of context values
        """
        self.__context.update_context(location, time, custom_ingame_events, weather, custom_context_values)
        if self.__context.have_actors_changed:
            self.__update_conversation_type()
            self.__context.have_actors_changed = False

    @utils.time_it
    def __update_conversation_type(self):
        """This changes between pc_to_npc, multi_npc and radiant conversation_types based on the current state of the context
        """
        # If the conversation can proceed for the first time, it starts and we add the system_message with the prompt
        if not self.__has_already_ended:
            self.__stop_generation()
            self.__sentences.clear()
            
            if not self.__context.npcs_in_conversation.contains_player_character():
                self.__conversation_type = radiant(self.__context.config)
            elif self.__context.npcs_in_conversation.active_character_count() >= 3:
                self.__conversation_type = multi_npc(self.__context.config)
            else:
                self.__conversation_type = pc_to_npc(self.__context.config)

            new_prompt = self.__conversation_type.generate_prompt(self.__context)        
            if len(self.__messages) == 0:
                self.__messages: message_thread = message_thread(self.__context.config, new_prompt)
            else:
                self.__conversation_type.adjust_existing_message_thread(new_prompt, self.__messages)
                self.__messages.reload_message_thread(new_prompt, self.__llm_client.is_too_long, self.TOKEN_LIMIT_RELOAD_MESSAGES)

    @utils.time_it
    def update_game_events(self, message: user_message) -> user_message:
        """Add in-game events to player's response"""

        all_ingame_events = self.__context.get_context_ingame_events()
        if self.__is_player_interrupting:
            all_ingame_events.append('Interrupting...')
            self.__is_player_interrupting = False
        max_events = min(len(all_ingame_events) ,self.__context.config.max_count_events)
        message.add_event(all_ingame_events[-max_events:])
        self.__context.clear_context_ingame_events()        

        if message.count_ingame_events() > 0:            
            logging.log(28, f'In-game events since previous exchange:\n{message.get_ingame_events_text()}')

        return message

    @utils.time_it
    def retrieve_sentence_from_queue(self) -> sentence | None:
        """Retrieves the next sentence from the queue.
        If there is a sentence, adds the sentence to the last assistant_message of the message_thread.
        If the last message is not an assistant_message, a new one will be added.

        Returns:
            sentence | None: The next sentence from the queue or None if the queue is empty
        """
        next_sentence: sentence | None = self.__sentences.get_next_sentence() #This is a blocking call. Execution will wait here until queue is filled again
        if not next_sentence:
            return None
        
        if not next_sentence.is_system_generated_sentence and not next_sentence.speaker.is_player_character:
            last_message = self.__messages.get_last_message()
            if not isinstance(last_message, assistant_message):
                last_message = assistant_message(self.__context.config)
                last_message.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
                self.__messages.add_message(last_message)
            last_message.add_sentence(next_sentence)
        return next_sentence
   
    @utils.time_it
    def initiate_end_sequence(self):
        """Replaces all remaining sentences with a "goodbye" sentence that also prompts the game to request a stop to the conversation using an action
        """
        if not self.__has_already_ended:
            config = self.__context.config            
            self.__stop_generation()
            self.__sentences.clear()
            if self.__stt:
                self.__stt.stop_listening()
                self.__allow_mic_input = False
            # say goodbyes
            npc = self.__context.npcs_in_conversation.last_added_character
            if npc:
                goodbye_sentence = self.__output_manager.generate_sentence(sentence_content(npc, config.goodbye_npc_response, SentenceTypeEnum.SPEECH, True))
                if goodbye_sentence:
                    goodbye_sentence.actions.append(comm_consts.ACTION_ENDCONVERSATION)
                    self.__sentences.put(goodbye_sentence)
                    
    @utils.time_it
    def contains_character(self, ref_id: str) -> bool:
        for actor in self.__context.npcs_in_conversation.get_all_characters():
            if actor.ref_id == ref_id:
                return True
        return False
    
    @utils.time_it
    def get_character(self, ref_id: str) -> Character | None:
        for actor in self.__context.npcs_in_conversation.get_all_characters():
            if actor.ref_id == ref_id:
                return actor
        return None

    @utils.time_it
    def end(self):
        """Ends a conversation
        """
        self.__has_already_ended = True
        self.__stop_generation()
        self.__sentences.clear()
        self.__save_conversation(is_reload=False)
    
    @utils.time_it
    def __start_generating_npc_sentences(self):
        """Starts a background Thread to generate sentences into the sentence_queue"""    
        with self.__generation_start_lock:
            if not self.__generation_thread:
                self.__sentences.is_more_to_come = True
                self.__generation_thread = Thread(None, self.__output_manager.generate_response, None, [self.__messages, self.__context.npcs_in_conversation, self.__sentences, self.context.config.actions]).start()   

    @utils.time_it
    def __stop_generation(self):
        """Stops the current generation of sentences if there is one
        """
        self.__output_manager.stop_generation()
        while self.__generation_thread and self.__generation_thread.is_alive():
            time.sleep(0.1)
        self.__generation_thread = None

    @utils.time_it
    def __prepare_eject_npc_from_conversation(self, npc: Character):
        if not self.__has_already_ended:            
            self.__stop_generation()
            self.__sentences.clear()            
            # say goodbye
            goodbye_sentence = self.__output_manager.generate_sentence(sentence_content(npc, self.__context.config.goodbye_npc_response, SentenceTypeEnum.SPEECH, False))
            if goodbye_sentence:
                goodbye_sentence.actions.append(comm_consts.ACTION_REMOVECHARACTER)
                self.__sentences.put(goodbye_sentence)        

    @utils.time_it
    def __save_conversation(self, is_reload: bool):
        """Saves conversation log and state for each NPC in the conversation"""
        self.__save_conversations_for_characters(self.__context.npcs_in_conversation.get_all_characters(), is_reload)

    @utils.time_it
    def __save_conversations_for_characters(self, characters_to_save_for: list[Character], is_reload: bool):
        characters_object = Characters()
        for npc in characters_to_save_for:
            if not npc.is_player_character:
                characters_object.add_or_update_character(npc)
                conversation_log.save_conversation_log(npc, self.__messages.transform_to_openai_messages(self.__messages.get_talk_only()), self.__context.world_id)
        self.__rememberer.save_conversation_state(self.__messages, characters_object, self.__context.world_id, is_reload)

    @utils.time_it
    def __initiate_reload_conversation(self):
        """Places a "gather thoughts" sentence add the front of the queue that also prompts the game to request a reload of the conversation using an action"""
        latest_npc = self.__context.npcs_in_conversation.last_added_character
        if not latest_npc: 
            self.initiate_end_sequence()
            return
        
        # Play gather thoughts
        collecting_thoughts_text = self.__context.config.collecting_thoughts_npc_response
        collecting_thoughts_sentence = self.__output_manager.generate_sentence(sentence_content(latest_npc, collecting_thoughts_text, SentenceTypeEnum.SPEECH, True))
        if collecting_thoughts_sentence:
            collecting_thoughts_sentence.actions.append(comm_consts.ACTION_RELOADCONVERSATION)
            self.__sentences.put_at_front(collecting_thoughts_sentence)
    
    @utils.time_it
    def trigger_auto_continuation(self):
        """Triggers the NPC auto-continuation feature.
        Called when the game mod's timer expires and the player hasn't responded.
        Injects the continuation directive and starts NPC generation.
        """
        logging.info("NPC auto-continuation triggered - injecting continuation directive")

        # Create a system-generated user message with the continuation prompt
        continuation_message = user_message(
            self.__context.config,
            self.__context.config.npc_auto_continue_prompt,
            "",  # No speaker name for system messages
            True  # Mark as system-generated
        )
        continuation_message.is_multi_npc_message = False

        # Add the continuation directive to the message thread
        self.__messages.add_message(continuation_message)

        # Start generating NPC response
        self.__start_generating_npc_sentences()

    @utils.time_it
    def reload_conversation(self):
        """Reloads the conversation
        """
        self.__save_conversation(is_reload=True)
        # Reload
        new_prompt = self.__conversation_type.generate_prompt(self.__context)
        self.__messages.reload_message_thread(new_prompt, self.__llm_client.is_too_long, self.TOKEN_LIMIT_RELOAD_MESSAGES)

    @utils.time_it
    def __has_conversation_ended(self, last_user_text: str) -> bool:
        """Checks if the last player text has ended the conversation

        Args:
            last_user_text (str): the text to check

        Returns:
            bool: true if the conversation has ended, false otherwise
        """
        # transcriber = self.__stt
        config = self.__context.config
        transcript_cleaned = utils.clean_text(last_user_text)

        # check if user is ending conversation
        return Transcriber.activation_name_exists(transcript_cleaned, self.__end_conversation_keywords)

    def __should_resume_conversation(self, last_user_text: str) -> bool:
        """Checks if the player input is exactly the resume conversation keyword

        Args:
            last_user_text (str): the text to check

        Returns:
            bool: true if player wants to resume from previous history, false otherwise
        """
        # Get the configured keyword and clean both for comparison
        resume_keyword = self.__context.config.resume_conversation_keyword.strip().lower()
        transcript_cleaned = utils.clean_text(last_user_text).strip().lower()

        # Must be an exact match - no extra words allowed
        return transcript_cleaned == resume_keyword

    def __should_redo_response(self, last_user_text: str) -> str | None:
        """Checks if the player input is a redo command and extracts the guidance

        Args:
            last_user_text (str): the text to check

        Returns:
            str | None: the guidance text (can be empty string if no guidance provided), or None if not a redo command
        """
        import re

        # Get the configured keyword
        redo_keyword = self.__context.config.redo_conversation_keyword.strip().lower()

        # Pattern 1: "redo: guidance text here" (with guidance)
        pattern_with_guidance = rf"^{re.escape(redo_keyword)}:\s*(.+)$"
        match = re.match(pattern_with_guidance, last_user_text.strip(), re.IGNORECASE)
        if match:
            guidance = match.group(1).strip()
            return guidance

        # Pattern 2: just "redo" with optional colon but no guidance (redo without guidance)
        pattern_no_guidance = rf"^{re.escape(redo_keyword)}:?\s*$"
        match = re.match(pattern_no_guidance, last_user_text.strip(), re.IGNORECASE)
        if match:
            return ""  # Empty string means redo without guidance

        return None  # Not a redo command at all

    def __redo_last_response(self, guidance: str, player_name: str) -> bool:
        """Removes the last NPC response batch and adds redo directive

        Args:
            guidance (str): the guidance for regenerating the response
            player_name (str): the player's name for the directive message

        Returns:
            bool: True if successful, False if no assistant message found
        """
        # Find and remove the last assistant_message
        removed = False
        removed_content = ""
        for i in range(len(self.__messages._message_thread__messages) - 1, -1, -1):
            if isinstance(self.__messages._message_thread__messages[i], assistant_message):
                removed_msg = self.__messages._message_thread__messages.pop(i)
                removed_content = removed_msg.get_formatted_content()
                logging.info(f"Removed last NPC response for redo (first 100 chars): {removed_content[:100]}...")
                removed = True
                break

        if not removed:
            logging.warning("Redo requested but no assistant message found to remove")
            return False

        # Add redo directive as user_message with clear marking
        # Include the removed response for context so LLM knows what it said before
        if guidance:
            # Redo with specific guidance
            directive_text = f"<<<REDO DIRECTIVE: You previously responded with: '{removed_content}' This response was unsatisfactory. Please regenerate your response with this guidance: {guidance}>>>"
        else:
            # Redo without guidance - just try again differently
            directive_text = f"<<<REDO DIRECTIVE: You previously responded with: '{removed_content}' This response was unsatisfactory. Please regenerate your response differently.>>>"

        redo_directive = user_message(
            self.__context.config,
            directive_text,
            player_name,
            is_system_generated_message=False  # Keep it in history for context
        )
        redo_directive.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
        self.__messages.add_message(redo_directive)

        logging.info(f"Added redo directive{' with guidance: ' + guidance if guidance else ' (no specific guidance)'}")
        return True

    def __should_direct_npc(self, last_user_text: str) -> str | None:
        """Checks if the player input is a direct command and extracts the instruction

        Args:
            last_user_text (str): the text to check

        Returns:
            str | None: the instruction text, or None if not a direct command
        """
        import re

        # Get the configured keyword
        direct_keyword = self.__context.config.direct_conversation_keyword.strip().lower()

        # Pattern: "direct: instruction text here" (requires colon and instruction)
        pattern = rf"^{re.escape(direct_keyword)}:\s*(.+)$"
        match = re.match(pattern, last_user_text.strip(), re.IGNORECASE)
        if match:
            instruction = match.group(1).strip()
            return instruction

        return None  # Not a direct command

    def __should_toggle_nsfw(self, last_user_text: str) -> str | None:
        """Checks if the player input is an NSFW toggle command

        Args:
            last_user_text (str): the text to check

        Returns:
            str | None: "on" or "off" if matched, None otherwise
        """
        import re
        nsfw_keyword = self.__context.config.nsfw_keyword.strip().lower()
        pattern = rf"^{re.escape(nsfw_keyword)}\s+(on|off)\s*$"
        match = re.match(pattern, last_user_text.strip(), re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return None

    def __toggle_nsfw_mode(self, enable: bool):
        """Toggles NSFW mode on or off, swapping the model and system prompt

        Args:
            enable (bool): True to enable NSFW, False to disable
        """
        if not self.__nsfw_model:
            logging.warning("NSFW toggle requested but no NSFW model is configured. Set 'NSFW Model' in LLM settings.")
            return

        self.__nsfw_enabled = enable
        target_model = self.__nsfw_model if enable else self.__normal_model
        self.__llm_client.swap_model(target_model)

        new_prompt = self.__conversation_type.generate_prompt(self.__context, nsfw=enable)
        self.__messages.replace_system_message(new_prompt)

        state = "ON" if enable else "OFF"
        logging.info(f"NSFW mode toggled {state} — model: {target_model}")

    def __add_direct_instruction(self, instruction: str, player_name: str) -> bool:
        """Adds a director's instruction to guide NPC behavior

        Args:
            instruction (str): the instruction for the NPC
            player_name (str): the player's name for the directive message

        Returns:
            bool: True if successful
        """
        # Add directive as user_message with clear marking
        directive_text = f"<<<DIRECTOR'S INSTRUCTION: {instruction}>>>"

        direct_directive = user_message(
            self.__context.config,
            directive_text,
            player_name,
            is_system_generated_message=False  # Keep it in history for context
        )
        direct_directive.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
        self.__messages.add_message(direct_directive)

        logging.info(f"Added director's instruction: {instruction}")
        return True

    def __should_direct_radiant_npc(self) -> str | None:
        """Checks if radiant direction was provided via custom context

        Returns:
            str | None: the direction text, or None if not a radiant conversation or no direction
        """
        if not isinstance(self.__conversation_type, radiant):
            return None

        direction = self.__context.get_custom_context_value("radiant_direction")
        if direction and isinstance(direction, str) and direction.strip():
            return direction.strip()

        return None

    def __check_and_strip_nsfw_from_direction(self, direction: str) -> str:
        """Checks if direction text contains the NSFW keyword, enables NSFW mode if found, and returns cleaned text

        Args:
            direction (str): the direction text to check

        Returns:
            str: the direction text with the NSFW keyword removed (if found), or unchanged
        """
        import re
        nsfw_keyword = self.__context.config.nsfw_keyword.strip()
        if not nsfw_keyword:
            return direction
        pattern = rf"\b{re.escape(nsfw_keyword)}\b"
        if re.search(pattern, direction, re.IGNORECASE):
            cleaned = re.sub(pattern, "", direction, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"\s{2,}", " ", cleaned)
            self.__toggle_nsfw_mode(True)
            return cleaned
        return direction

    def __add_radiant_direction(self, direction: str) -> bool:
        """Adds a director's instruction for radiant conversation

        Args:
            direction (str): the direction for NPCs

        Returns:
            bool: True if successful
        """
        # Frame as out-of-character direction
        directive_text = f"<<<RADIANT DIRECTION: {direction}>>>"

        radiant_directive = user_message(
            self.__context.config,
            directive_text,
            "",  # No speaker name for radiant directions
            is_system_generated_message=False  # Keep in history for context
        )
        radiant_directive.is_multi_npc_message = False
        self.__messages.add_message(radiant_directive)

        logging.info(f"Added radiant direction: {direction}")
        return True

    def __load_last_conversation(self, character: Character) -> list[ChatCompletionMessageParam]:
        """Loads only the most recent conversation for a given character.

        The conversation log file contains an array of conversations:
        [
            [conversation1_messages],
            [conversation2_messages],
            [conversation3_messages]  <-- We want this one (the last)
        ]

        Args:
            character: The character whose conversation history to load

        Returns:
            list: The messages from the most recent conversation, or empty list if none exists
        """
        import json
        import os

        # Get the path to the character's conversation history file
        conversation_history_file = conversation_log._conversation_log__get_path_to_conversation_history_file(character, self.__context.world_id)

        if os.path.exists(conversation_history_file):
            try:
                with open(conversation_history_file, 'r', encoding='utf-8') as f:
                    conversation_history = json.load(f)

                # conversation_history is an array of conversations
                # Each conversation is an array of messages
                # We only want the LAST conversation
                if conversation_history and len(conversation_history) > 0:
                    last_conversation = conversation_history[-1]  # Get the last element
                    logging.info(f"Found {len(conversation_history)} total conversations for {character.name}, loading the most recent one with {len(last_conversation)} messages")
                    return last_conversation
                else:
                    return []
            except Exception as e:
                logging.error(f"Error loading conversation history for {character.name}: {e}")
                return []
        else:
            logging.info(f"No conversation history file found for {character.name}")
            return []

    @utils.time_it
    def __load_previous_conversation_history(self):
        """Loads the most recent conversation from disk into the current message thread.
        This allows resuming a conversation that was interrupted or ended prematurely.

        Note: Only loads the LAST conversation from the character's history file, not all conversations.
        """
        try:
            all_characters = self.__context.npcs_in_conversation.get_all_characters()

            # For multi-NPC conversations, we need to load and merge histories from all NPCs
            # For 1-on-1, there's typically just one NPC (plus player)
            loaded_message_count = 0

            for character in all_characters:
                if not character.is_player_character:
                    # Load ONLY the last conversation from the character's history
                    # The conversation log stores an array of conversations, we only want the most recent one
                    previous_messages = self.__load_last_conversation(character)

                    if previous_messages:
                        logging.info(f"Loading {len(previous_messages)} previous messages for {character.name}")

                        # Convert OpenAI format messages to Mantella message objects
                        for msg in previous_messages:
                            role = msg.get('role', '')
                            content = msg.get('content', '')

                            if role == 'user':
                                # Reconstruct user_message
                                player_char = self.__context.npcs_in_conversation.get_player_character()
                                player_name = player_char.name if player_char else ""
                                restored_msg = user_message(self.__context.config, content, player_name, False)
                                restored_msg.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
                                self.__messages.add_message(restored_msg)
                                loaded_message_count += 1
                            elif role == 'assistant':
                                # Reconstruct assistant_message
                                # Note: We create a simple assistant message with just the text
                                # Since assistant_message uses sentences internally, we need to override get_formatted_content
                                # to return the loaded content directly
                                restored_msg = assistant_message(self.__context.config, False)
                                restored_msg.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
                                restored_msg.text = content

                                # Override get_formatted_content to return the loaded text instead of building from sentences
                                # This is necessary because we're loading from saved text, not reconstructing full sentence objects
                                # Use default parameter to capture content value (avoids closure bug where all lambdas reference the last loop value)
                                restored_msg.get_formatted_content = lambda c=content: c

                                self.__messages.add_message(restored_msg)
                                loaded_message_count += 1

                        # For multi-NPC, we only need to load once since all NPCs share the same conversation
                        # The conversation_log saves the same messages for all participants
                        break

            if loaded_message_count > 0:
                logging.info(f"Successfully loaded {loaded_message_count} messages from previous conversation history")
            else:
                logging.info("No previous conversation history found to load")

        except Exception as e:
            logging.error(f"Failed to load previous conversation history: {e}")
            import traceback
            traceback.print_exc()

    @utils.time_it
    def __does_dismiss_npc_from_conversation(self, last_user_text: str) -> Character | None:
        """Checks if the last player text dismisses an NPC from the conversation

        Args:
            last_user_text (str): the text to check

        Returns:
            bool: true if the conversation has ended, false otherwise
        """
        transcript_cleaned = utils.clean_text(last_user_text)

        words = transcript_cleaned.split()
        for i, word in enumerate(words):
            if word in self.__end_conversation_keywords:
                if i < (len(words) - 1):
                    next_word = words[i + 1]
                    for npc_name in self.__context.npcs_in_conversation.get_all_names():
                        if next_word in npc_name.lower().split():
                            return self.__context.npcs_in_conversation.get_character_by_name(npc_name)
        return None
    
    @utils.time_it
    def __should_voice_player_input(self, player_character: Character) -> bool:
        game_value: Any = player_character.get_custom_character_value(comm_consts.KEY_ACTOR_PC_VOICEPLAYERINPUT)
        if game_value == None:
            return self.__context.config.voice_player_input
        return game_value