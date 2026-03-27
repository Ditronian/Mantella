import io
import logging
import numpy as np
import soundfile as sf
import requests
from src.config.config_loader import ConfigLoader
from src.tts.ttsable import ttsable
from src.tts.synthesization_options import SynthesizationOptions
import src.utils as utils


class fish_audio(ttsable):
    """Fish.audio TTS provider for custom/cloned voices via REST API"""

    @utils.time_it
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config)
        self.__api_key: str = config.fish_audio_api_key
        if not self.__api_key:
            logging.warning("Fish Audio API key is not set. Fish Audio TTS will fail until configured.")
        self.__reference_id: str = ""
        self.__api_url: str = "https://api.fish.audio/v1/tts"

    @utils.time_it
    def change_voice(self, voice: str, in_game_voice: str | None = None, csv_in_game_voice: str | None = None,
                     advanced_voice_model: str | None = None, voice_accent: str | None = None,
                     voice_gender: int | None = None, voice_race: str | None = None):
        # For Fish.audio, advanced_voice_model holds the reference_id (UUID)
        # Falls back to voice (tts_voice_model) if no advanced_voice_model is set
        self.__reference_id = advanced_voice_model or voice or ""
        self._last_voice = self.__reference_id

    @utils.time_it
    def tts_synthesize(self, voiceline: str, final_voiceline_file: str, synth_options: SynthesizationOptions):
        max_chunk_length = self._config.tts_max_chunk_length if self._config.tts_max_chunk_length > 0 else 250
        chunks = self._split_voiceline(voiceline, max_length=max_chunk_length)

        if len(chunks) <= 1:
            self._synthesize_line(voiceline, final_voiceline_file)
        else:
            audio_chunks: list[io.BytesIO] = []
            for chunk in chunks:
                chunk_bytes = self._synthesize_line_to_bytes(chunk)
                audio_chunks.append(chunk_bytes)
            self._merge_audio_chunks(audio_chunks, final_voiceline_file)

    def _synthesize_line(self, text: str, save_path: str):
        """Synthesize a single line and save to file"""
        audio_bytes = self._synthesize_line_to_bytes(text)
        data, samplerate = sf.read(audio_bytes)
        if np.issubdtype(data.dtype, np.floating):
            data = np.int16(data * 32767)
        sf.write(save_path, data, samplerate, subtype='PCM_16')

    def _synthesize_line_to_bytes(self, text: str) -> io.BytesIO:
        """Synthesize a single line and return as BytesIO"""
        if not self.__api_key:
            raise ValueError("Fish Audio API key is not configured. Please set it in Mantella settings.")
        if not self.__reference_id:
            raise ValueError("No Fish Audio reference_id set for this character. Set advanced_voice_model in the character CSV.")

        logging.log(self._loglevel, f"Fish Audio: synthesizing with reference_id={self.__reference_id[:8]}...")

        response = requests.post(
            self.__api_url,
            headers={
                'Authorization': f'Bearer {self.__api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'text': text,
                'reference_id': self.__reference_id,
                'format': 'wav',
                'sample_rate': 44100,
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Fish Audio API error {response.status_code}: {response.text[:200]}")

        return io.BytesIO(response.content)

    def _merge_audio_chunks(self, audio_chunks: list[io.BytesIO], save_path: str):
        """Merge multiple audio chunks into a single file"""
        merged_audio = np.array([])
        target_samplerate = None
        for chunk_bytes in audio_chunks:
            data, samplerate = sf.read(chunk_bytes)
            if target_samplerate is None:
                target_samplerate = samplerate
            merged_audio = np.concatenate((merged_audio, data))
        if target_samplerate and len(merged_audio) > 0:
            if np.issubdtype(merged_audio.dtype, np.floating):
                merged_audio = np.int16(merged_audio * 32767)
            sf.write(save_path, merged_audio, target_samplerate, subtype='PCM_16')
