from abc import ABC, abstractmethod
from src.character_manager import Character
from src.characters_manager import Characters
from src.llm.message_thread import message_thread


class remembering(ABC):
    @abstractmethod
    def get_prompt_text(self, npcs_in_conversation: Characters, world_id: str) -> str:
        """ Generates a text that explains the previous interactions of the npcs with the player. 
            Text is passed as part of the prompt to the LLM

        Args:
            npcs_in_conversation (Characters): the NPCs in question

        Returns:
            str: a single text
        """
        pass

    @abstractmethod
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False):
        """Saves the current state of the conversation.

        Args:
            messages (message_thread): The messages in the conversation
            npcs_in_conversation (Characters): the NPCs to save for
        """
        pass

    @abstractmethod
    def remove_last_summary(self, npcs_in_conversation: Characters, world_id: str):
        """Removes the last saved summary for the given NPCs.
        Used when restarting a conversation to undo the summary generated at end of the previous conversation.
        """
        pass

    @abstractmethod
    def redo_summary_for_character(self, character: Character, world_id: str, user_notes: str = ""):
        """Regenerates the last summary for a character using the last conversation log.
        Optionally appends user notes to the summarization prompt for guidance.
        Old summary is only removed after new one is successfully generated.
        """
        pass