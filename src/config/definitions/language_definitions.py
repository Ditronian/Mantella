from src.conversation.action import action
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString


class LanguageDefinitions:    
    @staticmethod
    def get_language_config_value() -> ConfigValue:
        return ConfigValueSelection("language","Language","The language used by Mantella (speech-to-text, LLM responses, and text-to-speech).","en",["en", "ar", "cs", "da", "de", "el", "es", "fi", "fr", "hi", "hu", "it", "ja", "ko", "nl", "pl", "pt", "ro", "ru", "sv", "sw", "uk", "ha", "tr", "vi", "yo", "zh"])
    
    @staticmethod
    def get_end_conversation_keyword_config_value() -> ConfigValue:
        description = """The keyword(s) Mantella will listen out for to end the conversation (lowercase / uppercase does not matter).
                        To add multiple options, you can split keywords using commas."""
        return ConfigValueString("end_conversation_keyword","End Conversation Keyword(s)",description,"goodbye, bye, good-bye, good bye, good-by, good by, good to buy")

    @staticmethod
    def get_resume_conversation_keyword_config_value() -> ConfigValue:
        description = """The exact keyword to restart a conversation from its previous history.
                        This must be typed exactly (case-insensitive) as the first player input to load the full conversation history.
                        If any other text is included, the keyword will not be recognized."""
        return ConfigValueString("resume_conversation_keyword","Resume Conversation Keyword",description,"restart")

    @staticmethod
    def get_redo_conversation_keyword_config_value() -> ConfigValue:
        description = """The keyword prefix to redo the last NPC response with guidance.
                        Format: 'redo: your guidance here' (case-insensitive).
                        Example: 'redo: Erdi should be more conflicted'
                        This will remove the previous NPC response and regenerate it with your guidance."""
        return ConfigValueString("redo_conversation_keyword","Redo Response Keyword",description,"redo")

    @staticmethod
    def get_direct_conversation_keyword_config_value() -> ConfigValue:
        description = """The keyword prefix to directly instruct NPCs with explicit directions.
                        Format: 'direct: your instruction here' (case-insensitive).
                        Example: 'direct: Tullius speaks and mentions reports from the front lines'
                        This allows you to guide NPC behavior without confusing it with in-game events."""
        return ConfigValueString("direct_conversation_keyword","Direct NPC Keyword",description,"direct")

    @staticmethod
    def get_goodbye_npc_response() -> ConfigValue:
        return ConfigValueString("goodbye_npc_response","NPC Response: Goodbye","The response the NPC gives at the end of the conversation.","Safe travels",tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_collecting_thoughts_npc_response() -> ConfigValue:
        return ConfigValueString("collecting_thoughts_npc_response", "NPC Response: Collecting Thoughts","The response the NPC gives when they need to summarise the conversation because the maximum token count has been reached.","I need to gather my thoughts for a moment", tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_action_keyword_override(action: action) -> ConfigValue:
        identifier = action.identifier.lstrip("mantella_").lstrip("npc_")
        return ConfigValueString(f"{identifier}_npc_response",f"NPC Response override: {action.name}",action.description, action.keyword, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
