import logging
from src.config.config_loader import ConfigLoader
from src.games.gameable import gameable
from src.tts.ttsable import ttsable


class TTSProviderRegistry:
    """Lazy-initialized registry that maps provider names to TTS instances.

    Providers are only created when a character actually needs them.
    If nobody uses Fish.audio in a session, it's never instantiated.
    """

    def __init__(self, config: ConfigLoader, game: gameable):
        self._config: ConfigLoader = config
        self._game: gameable = game
        self._default_provider_name: str = config.tts_service
        self._providers: dict[str, ttsable] = {}

    def get_provider(self, provider_name: str = "") -> ttsable:
        """Get TTS provider by name. Empty string returns the default."""
        name = provider_name.strip().lower() if isinstance(provider_name, str) and provider_name else self._default_provider_name
        if name not in self._providers:
            self._providers[name] = self._create_provider(name)
        return self._providers[name]

    def _create_provider(self, name: str) -> ttsable:
        logging.log(29, f"Initializing TTS provider: {name}")
        if name == "xvasynth":
            from src.tts.xvasynth import xvasynth
            return xvasynth(self._config)
        elif name == "xtts":
            from src.tts.xtts import xtts
            return xtts(self._config, self._game)
        elif name == "piper":
            from src.tts.piper import piper
            return piper(self._config, self._game)
        elif name == "fish audio" or name == "fish_audio":
            from src.tts.fish_audio import fish_audio
            return fish_audio(self._config)
        else:
            raise ValueError(f"Unknown TTS provider: '{name}'. Valid options: xvasynth, xtts, piper, fish audio")

    @property
    def default_provider(self) -> ttsable:
        return self.get_provider(self._default_provider_name)
