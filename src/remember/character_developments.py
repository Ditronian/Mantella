import logging
import os
from src.games.gameable import gameable
from src.character_manager import Character
from src.characters_manager import Characters
from src import utils


class CharacterDevelopments:
    """Manages player-authored character developments — permanent, per-character facts
    that override the base bio. Stored as plain text files, one development per line.
    """

    def __init__(self, game: gameable) -> None:
        self.__game: gameable = game

    def _get_character_folder_path(self, character: Character, world_id: str) -> str:
        """Resolve the character's conversation folder, matching the same logic as summaries."""
        base_name: str = utils.remove_trailing_number(character.name)
        name_ref: str = f'{base_name} - {character.ref_id}'

        def get_folder_path(folder_name: str) -> str:
            return os.path.join(self.__game.conversation_folder_path, world_id, folder_name).replace(os.sep, '/')

        name_ref_path = get_folder_path(name_ref)
        name_path = get_folder_path(base_name)

        if os.path.exists(name_ref_path):
            return name_ref_path
        elif os.path.exists(name_path):
            return name_path
        else:
            return name_ref_path

    def _get_developments_file_path(self, character: Character, world_id: str) -> str:
        base_name: str = utils.remove_trailing_number(character.name)
        folder = self._get_character_folder_path(character, world_id)
        return f"{folder}/{base_name}_developments.txt"

    def load(self, character: Character, world_id: str) -> list[str]:
        file_path = self._get_developments_file_path(character, world_id)
        if not os.path.exists(file_path):
            return []
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f]
        return [line for line in lines if line]

    def save(self, character: Character, world_id: str, development_text: str):
        file_path = self._get_developments_file_path(character, world_id)
        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(development_text.strip() + '\n')
        logging.info(f"Character development saved for {character.name}: {development_text.strip()}")

    def get_prompt_text(self, npcs_in_conversation: Characters, world_id: str) -> str:
        """Build the developments prompt section for all NPCs in the conversation."""
        sections = []
        for character in npcs_in_conversation.get_all_characters():
            if character.is_player_character:
                continue
            developments = self.load(character, world_id)
            if not developments:
                continue
            bullet_list = '\n'.join(f'- {d}' for d in developments)
            section = (
                f"{character.name}'s Character Developments:\n"
                f"The following are confirmed developments to {character.name}'s character that have occurred "
                f"during gameplay. These represent permanent changes and TAKE PRECEDENCE over the "
                f"background information above wherever they conflict. Treat each as an established "
                f"fact about who {character.name} is NOW:\n"
                f"{bullet_list}\n\n"
                f"[End of character developments]"
            )
            sections.append(section)
        return '\n\n'.join(sections)
