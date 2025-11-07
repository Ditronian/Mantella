# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Mantella is a mod for Skyrim and Fallout 4 that enables natural AI-powered NPC conversations using Whisper (STT), LLMs, and xVASynth/XTTS (TTS). The software runs as a FastAPI HTTP server that communicates with game plugins.

## Development Setup

Python 3.11 is required.

```bash
# Create virtual environment
py -3.11 -m venv MantellaEnv

# Activate environment
.\MantellaEnv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Create API key file
# Create GPT_SECRET_KEY.txt and paste your OpenAI key

# Run Mantella
python main.py
```

## Architecture

### Core Flow

1. **HTTP Server** (`src/http/http_server.py`) - FastAPI server running on configurable port (default 4999)
2. **Routes** (`src/http/routes/mantella_route.py`) - Main route handles game requests at `/mantella` endpoint
3. **Game State Manager** (`src/game_manager.py`) - Orchestrates conversation lifecycle and manages game state
4. **Conversation** (`src/conversation/conversation.py`) - Controls conversation flow, handles turn-taking
5. **Output Manager** (`src/output_manager.py`) - Generates sentences and manages TTS
6. **LLM Client** (`src/llm/llm_client.py`) - Handles LLM API calls using OpenAI-compatible interface

### Request Flow

Game sends JSON → mantella_route → GameStateManager → conversation → LLM/TTS → response JSON → Game

Request types: `init`, `start_conversation`, `continue_conversation`, `player_input`, `end_conversation`

### Key Components

**Game Abstraction** (`src/games/`)
- `gameable.py` - Abstract base class for game-specific implementations
- `skyrim.py` / `fallout4.py` - Game-specific character loading, paths, voice models
- `external_character_info.py` - Character data from game mods
- Character data loaded from CSV files in `data/Skyrim/` and `data/Fallout4/`

**Characters** (`src/character_manager.py`, `src/characters_manager.py`)
- `Character` - Individual character with bio, voice model, combat state, equipment, etc.
- `Characters` - Manages multiple characters in a conversation

**Configuration** (`src/config/`)
- `config_loader.py` - Loads and manages settings from config.ini
- `definitions/` - Typed config value definitions for game, LLM, TTS, STT, prompts, etc.
- `types/` - Visitor pattern for different config value types (bool, int, float, string, path, selection)
- Config stored in `Documents/My Games/Mantella/config.ini` (or custom folder via `custom_user_folder.ini`)

**LLM Processing** (`src/llm/`)
- `message_thread.py` - Manages conversation message history with token limits
- `messages.py` - Message types (system, user, assistant)
- `output/` - Chain of parsers for processing LLM output:
  - `clean_sentence_parser.py` - Removes formatting artifacts
  - `sentence_end_parser.py` - Detects sentence boundaries
  - `actions_parser.py` - Extracts character actions
  - `narration_parser.py` - Separates narration from dialogue
  - `change_character_parser.py` - Detects speaker changes in multi-NPC conversations
  - `sentence_length_parser.py` - Validates sentence length
  - `max_count_sentences_parser.py` - Limits sentence count
- `sentence_queue.py` - Thread-safe queue for streaming sentences to game

**TTS Abstraction** (`src/tts/`)
- `ttsable.py` - Abstract interface for TTS services
- `xvasynth.py` - xVASynth integration (local character voice synthesis)
- `xtts.py` - XTTS integration (AI voice cloning)
- `piper.py` - Piper TTS integration
- Audio files temporarily stored and sent to game's voice folder

**STT** (`src/stt.py`)
- Supports faster-whisper (local), OpenAI Whisper API, Azure, moonshine
- `Transcriber` class handles mic input with VAD (voice activity detection)

**Memory/Context** (`src/remember/`)
- `remembering.py` - Abstract interface for conversation memory
- `summaries.py` - Creates and manages conversation summaries to stay within token limits
- Conversation logs stored per-character in `Documents/My Games/Mantella/data/{game}/conversations/`

**UI** (`src/ui/`)
- `start_ui.py` - Gradio web UI route at `/ui` endpoint for configuration

### Important Patterns

**Async LLM Generation**: LLM responses stream into sentence_queue which are consumed by game in real-time. Generation happens on background thread with interruption support.

**Token Management**: Conversations reload messages when approaching token limits (90% threshold). Old messages summarized and replaced with summary to maintain context.

**Character Voice Mapping**: Characters map to voice models via CSV files. TTS implementations use `tts_voice_model`, `in_game_voice_model`, `csv_in_game_voice_model`, `advanced_voice_model` fields.

**Actions System**: NPCs can perform actions (loaded from `data/actions/`) which are parsed from LLM output and sent to game for execution.

**Conversation Types**: `pc_to_npc` (player talking to NPC), `multi_npc` (group conversations), `radiant` (NPC-to-NPC without player)

## File Paths

- User data/config: `Documents/My Games/Mantella/` (Windows) or custom via `custom_user_folder.ini`
- Character CSVs: `data/Skyrim/skyrim_characters.csv`, `data/Fallout4/fallout4_characters.csv`
- Character overrides: Can be placed in mod folder or user folder under `data/{game}/character_overrides/`
- Conversation histories: `{user_folder}/data/{game}/conversations/{character_id}.json`
- Language support: `data/language_support.csv`

## Communication with Game Mods

Game mods communicate via HTTP POST to `/mantella` endpoint:
- Mantella Spell (Skyrim): https://github.com/art-from-the-machine/Mantella-Spell
- Mantella Gun (Fallout 4): https://github.com/YetAnotherModder/Fallout-4-VR-Mantella-Mod

JSON protocol defined in `src/http/communication_constants.py`

## Logging

Custom logging levels:
- 21-23: Player/NPC transcription and info
- 24: Startup messages
- 27: STT (Speech-to-Text)
- 28: LLM (Large Language Model)
- 29: TTS (Text-to-Speech)
- 41-43: HTTP debugging

Logs written to `{user_folder}/logging.log`

## Common Issues

**Short voicelines**: Voicelines shorter than 3 characters are skipped (see output_manager.py:65)

**Colons in text**: Colons are NOT treated as sentence endings to preserve actions (see recent commits)

**Token limits**: Both LLM API limits and custom token count settings affect conversation length

**Voice model mismatches**: Check character CSV entries match available TTS voice models
