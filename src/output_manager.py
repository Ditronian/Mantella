import asyncio
from threading import Lock
import wave
import logging
import time
import unicodedata
from openai import APIConnectionError
from src.config.definitions.llm_definitions import NarrationHandlingEnum
from src.llm.output.max_count_sentences_parser import max_count_sentences_parser
from src.llm.output.sentence_length_parser import sentence_length_parser
from src.llm.output.actions_parser import actions_parser
from src.llm.output.change_character_parser import change_character_parser
from src.llm.output.clean_sentence_parser import clean_sentence_parser
from src.llm.output.narration_parser import narration_parser
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.output.sentence_end_parser import sentence_end_parser
from src.llm.sentence_content import SentenceTypeEnum, sentence_content
from src.conversation.action import action
from src.llm.sentence_queue import sentence_queue
from src.config.config_loader import ConfigLoader
from src.llm.sentence import sentence as mantella_sentence #<- Do not collide with frequent and logical use of "sentence" when generating text from the LLM
import src.utils as utils
from src.characters_manager import Characters
from src.character_manager import Character
from src.llm.messages import message
from src.llm.message_thread import message_thread
from src.llm.ai_client import AIClient
from src.tts.ttsable import ttsable
from src.tts.tts_provider_registry import TTSProviderRegistry
from src.tts.synthesization_options import SynthesizationOptions

class ChatManager:
    def __init__(self, config: ConfigLoader, tts_registry: TTSProviderRegistry, client: AIClient):
        self.loglevel = 28
        self.__config: ConfigLoader = config
        self.__tts_registry: TTSProviderRegistry = tts_registry
        self.__client: AIClient = client
        self.__is_generating: bool = False
        self.__stop_generation = asyncio.Event()
        self.__tts_access_lock = Lock()
        self.__is_first_sentence: bool = False
        self.__end_of_sentence_chars = ['.', '?', '!', ';', '。', '？', '！', '；', '：']
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.__end_of_sentence_chars]

    @property
    def tts(self) -> ttsable:
        """Returns the default TTS provider for backward compatibility"""
        return self.__tts_registry.default_provider

    @property
    def tts_registry(self) -> TTSProviderRegistry:
        return self.__tts_registry
    
    @utils.time_it
    def generate_sentence(self, content: sentence_content) -> mantella_sentence:
        """Generates the audio for a text and returns the corresponding sentence

        Args:
            text (str): the text to be voices
            character_to_talk (Character): the character to say the sentence
            is_system_generated_sentence (bool, optional): Is this sentence system generated? Defaults to False.

        Returns:
            mantella_sentence | None: _description_
        """

        character_to_talk = content.speaker
        text = ' ' + content.text + ' '

        # Skip TTS if generation is being stopped
        if self.__stop_generation.is_set():
            return mantella_sentence(sentence_content(character_to_talk, text, content.sentence_type, True), "", 0)

        # Check for short voicelines before sending to TTS
        if len(content.text.strip()) < 3:
            logging.warning(f"Skipping TTS for voiceline that is too-short: '{content.text.strip()}'")
            # Return a sentence object without audio - skipping TTS entirely
            return mantella_sentence(sentence_content(character_to_talk, text, content.sentence_type, True), "", 0)

        with self.__tts_access_lock:
            # Retry TTS synthesis up to 3 times with exponential backoff
            max_retries = 3
            retry_delay = 1.0  # Start with 1 second delay
            audio_file = ""

            for attempt in range(max_retries):
                try:
                    if self.__config.narration_handling == NarrationHandlingEnum.USE_NARRATOR and content.sentence_type == SentenceTypeEnum.NARRATION:
                        synth_options = SynthesizationOptions(False, self.__is_first_sentence)
                        tts = self.__tts_registry.get_provider()
                        audio_file = tts.synthesize(self.__config.narrator_voice, text, self.__config.narrator_voice, self.__config.narrator_voice, "en", synth_options, self.__config.narrator_voice)
                    else:
                        synth_options = SynthesizationOptions(character_to_talk.is_in_combat, self.__is_first_sentence)
                        tts = self.__tts_registry.get_provider(character_to_talk.tts_provider)
                        audio_file = tts.synthesize(character_to_talk.tts_voice_model, text, character_to_talk.in_game_voice_model, character_to_talk.csv_in_game_voice_model, character_to_talk.voice_accent, synth_options, character_to_talk.advanced_voice_model)
                    # Success! Break out of retry loop
                    break
                except Exception as e:
                    utils.play_error_sound()
                    error_text = f"Text-to-Speech Error (attempt {attempt + 1}/{max_retries}): {e}"
                    logging.log(29, error_text)

                    if attempt < max_retries - 1:
                        # Not the last attempt, wait and retry
                        logging.log(29, f"Retrying TTS synthesis in {retry_delay} seconds...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        # All retries exhausted, return text-only sentence (no error_message to avoid conversation termination)
                        logging.error(f"TTS synthesis failed after {max_retries} attempts. Continuing with text-only.")
                        return mantella_sentence(sentence_content(character_to_talk, text, content.sentence_type, True), "", 0)

            self.__is_first_sentence = False
            return mantella_sentence(sentence_content(character_to_talk, text, content.sentence_type, content.is_system_generated_sentence, content.actions), audio_file, self.get_audio_duration(audio_file))

    @utils.time_it
    def generate_response(self, messages: message_thread, characters: Characters, blocking_queue: sentence_queue, actions: list[action]):
        """Starts generating responses by the LLM for the current state of the input messages

        Args:
            messages (message_thread): _description_
            characters (Characters): _description_
            blocking_queue (sentence_queue): _description_
            actions (list[action]): _description_
        """
        if(not characters.last_added_character):
            return
        self.__is_generating = True
        
        asyncio.run(self.process_response(characters.last_added_character, blocking_queue, messages, characters, actions))
    
    @utils.time_it
    def stop_generation(self):
        """Stops the current generation and only returns once this stop has been successful
        """
        self.__stop_generation.set()
        wait_start = time.time()
        while self.__is_generating:
            if time.time() - wait_start > 15.0:
                logging.warning("stop_generation: Timed out waiting for generation to stop after 15 seconds. Forcing state reset.")
                self.__is_generating = False
                break
            time.sleep(0.01)
        self.__stop_generation.clear()
        return

    @utils.time_it
    def get_audio_duration(self, audio_file: str):
        """Check if the external software has finished playing the audio file"""

        with wave.open(audio_file, 'r') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()

        # wait `buffer` seconds longer to let processes finish running correctly
        duration = frames / float(rate)
        return duration
 
    @utils.time_it
    async def process_response(self, active_character: Character, blocking_queue: sentence_queue, messages : message_thread, characters: Characters, actions: list[action]):
        """Stream response from LLM one sentence at a time"""

        raw_response: str = ''  # Track the raw response
        first_token = True
        parsed_sentence: sentence_content | None = None
        pending_sentence: sentence_content | None = None
        self.__is_first_sentence = True

        parser_chain: list[output_parser] = [
            clean_sentence_parser(),
            change_character_parser(characters)]
        if self.__config.narration_handling != NarrationHandlingEnum.DEACTIVATE_HANDLING_OF_NARRATIONS:
            parser_chain.append(narration_parser(self.__config.narration_start_indicators, self.__config.narration_end_indicators, 
                                                 self.__config.speech_start_indicators, self.__config.speech_end_indicators))
        parser_chain.extend([
            sentence_end_parser(),
            actions_parser(actions),
            sentence_length_parser(self.__config.number_words_tts),
            max_count_sentences_parser(self.__config.max_response_sentences, not characters.contains_player_character())
        ])
       
        try:
            current_sentence: str = ''
            settings: sentence_generation_settings = sentence_generation_settings(active_character)
            max_llm_retries = 3
            llm_retry_count = 0

            while llm_retry_count < max_llm_retries:
                try:
                    start_time = time.time()
                    async for content in self.__client.streaming_call(messages=messages, is_multi_npc=characters.contains_multiple_npcs()):
                        if self.__stop_generation.is_set():
                            break
                        if not content:
                            continue

                        if first_token:
                            logging.log(self.loglevel, f"LLM took {round(time.time() - start_time, 5)} seconds to respond")
                            first_token = False

                        current_sentence += content
                        raw_response += content
                        parsed_sentence: sentence_content | None = None
                        # Apply parsers
                        for parser in parser_chain:
                            if not parsed_sentence:  # Try to extract a complete sentence
                                parsed_sentence, current_sentence = parser.cut_sentence(current_sentence, settings)
                            if parsed_sentence:  # Apply modifications if we already have a sentence
                                parsed_sentence, pending_sentence = parser.modify_sentence_content(parsed_sentence, pending_sentence, settings)
                            if settings.stop_generation:
                                break
                        if settings.stop_generation:
                            break

                        # Process sentences from the parser chain
                        if parsed_sentence:
                            if self.__stop_generation.is_set():
                                break
                            if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or parsed_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                                new_sentence = self.generate_sentence(parsed_sentence)
                                blocking_queue.put(new_sentence)
                                parsed_sentence = None
                    break #if the streaming_call() completed without exception, break the while loop

                except Exception as e:
                    llm_retry_count += 1
                    utils.play_error_sound()
                    logging.error(f"LLM API Error (attempt {llm_retry_count}/{max_llm_retries}): {e}")

                    if llm_retry_count >= max_llm_retries:
                        logging.error(f"LLM failed after {max_llm_retries} attempts. Ending response generation.")
                        break

                    error_response = "I can't find the right words at the moment."
                    new_sentence = self.generate_sentence(sentence_content(active_character, error_response, SentenceTypeEnum.SPEECH, True))
                    blocking_queue.put(new_sentence)
                    if new_sentence.error_message:
                        logging.error("Error response TTS also failed. Stopping retries.")
                        break
                    # else:
                    #     for a in actions_in_sentence:
                    #         new_sentence.actions.append( a.identifier)
                    logging.log(self.loglevel, 'Retrying connection to API...')
                    time.sleep(5)

            # Drain any remaining text left in current_sentence after streaming ends
            while current_sentence.strip() and not settings.stop_generation and not self.__stop_generation.is_set():
                parsed_sentence = None
                for parser in parser_chain:
                    if not parsed_sentence:
                        parsed_sentence, current_sentence = parser.cut_sentence(current_sentence, settings)
                    if parsed_sentence:
                        parsed_sentence, pending_sentence = parser.modify_sentence_content(parsed_sentence, pending_sentence, settings)
                    if settings.stop_generation:
                        break
                if parsed_sentence:
                    if self.__stop_generation.is_set():
                        break
                    if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or parsed_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                        new_sentence = self.generate_sentence(parsed_sentence)
                        blocking_queue.put(new_sentence)
                        parsed_sentence = None
                else:
                    # No parser could extract a sentence — treat remainder as final sentence
                    remaining = current_sentence.strip()
                    if remaining:
                        if self.__stop_generation.is_set():
                            break
                        final_content = sentence_content(settings.current_speaker, remaining, SentenceTypeEnum.SPEECH, False)
                        for parser in parser_chain:
                            final_content, pending_sentence = parser.modify_sentence_content(final_content, pending_sentence, settings)
                        if final_content:
                            new_sentence = self.generate_sentence(final_content)
                            blocking_queue.put(new_sentence)
                    current_sentence = ''
                    break

        except Exception as e:
            utils.play_error_sound()
            if isinstance(e, APIConnectionError):
                if (hasattr(e, 'code')) and (e.code in [401, 'invalid_api_key']): # incorrect API key
                    logging.error(f"Invalid API key. Please ensure you have selected the right model for your service (OpenAI / OpenRouter) via the 'model' setting in MantellaSoftware/config.ini. If you are instead trying to connect to a local model, please ensure the service is running.")
                elif isinstance(e, UnboundLocalError):
                    logging.error('No voice file generated for voice line. Please check your TTS service for errors. The reason for this error is often because a voice model could not be found.')
                else:
                    logging.error(f"LLM API Error: {e}")
            else:
                logging.error(f"LLM API Error: {e}")
        finally:
            # Handle any remaining content
            if parsed_sentence:
                if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or parsed_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                    new_sentence = self.generate_sentence(parsed_sentence)
                    blocking_queue.put(new_sentence)
            
            if pending_sentence:
                if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or pending_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                    new_sentence = self.generate_sentence(pending_sentence)
                    blocking_queue.put(new_sentence)
            logging.log(23, f"Full raw response ({self.__client.get_count_tokens(raw_response)} tokens): {raw_response.strip()}")
            blocking_queue.is_more_to_come = False
            # This sentence is required to make sure there is one in case the game is already waiting for it
            # before the ChatManager realises there is not another message coming from the LLM
            blocking_queue.put(mantella_sentence(sentence_content(active_character,"",SentenceTypeEnum.SPEECH, True),"",0))
            self.__is_generating = False