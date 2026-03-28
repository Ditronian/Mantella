import logging
import os
from src.games.gameable import gameable


class WorldEvents:
    """Manages player-authored world events — persistent, global facts about the game world
    that apply to every conversation. Stored as a single plain text file per playthrough,
    with entries separated by a delimiter line.
    """

    SEPARATOR = "---WORLD_EVENT---"

    def __init__(self, game: gameable) -> None:
        self.__game: gameable = game

    def _get_world_events_file_path(self, world_id: str) -> str:
        return os.path.join(self.__game.conversation_folder_path, world_id, "world_events.txt").replace(os.sep, '/')

    def load(self, world_id: str) -> list[str]:
        file_path = self._get_world_events_file_path(world_id)
        if not os.path.exists(file_path):
            return []
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        entries = content.split(self.SEPARATOR)
        return [entry.strip() for entry in entries if entry.strip()]

    def save(self, world_id: str, event_text: str):
        file_path = self._get_world_events_file_path(world_id)
        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(event_text.strip() + '\n' + self.SEPARATOR + '\n')
        logging.info(f"World event saved: {event_text.strip()}")

    def get_prompt_text(self, world_id: str) -> str:
        events = self.load(world_id)
        if not events:
            bullet_list = "- None"
        else:
            bullet_list = '\n'.join(f'- {e}' for e in events)
        return (
            "Custom World Context:\n"
            "The following is context about the game world that differs from normal lore.\n"
            "These are critical game events that should be accounted for in responses.\n"
            f"{bullet_list}"
        )
