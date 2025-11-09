# NPC Auto-Continuation Feature

## Overview

The NPC Auto-Continuation feature allows NPCs to naturally continue conversations after a period of player silence, creating more dynamic and realistic interactions. Instead of waiting indefinitely for player input, NPCs will autonomously elaborate, ask questions, or make observations when the player hasn't responded within a configurable time window.

## How It Works

### Player Experience

1. **NPC speaks** and finishes their dialogue line
2. **Timer starts** counting down (configurable, e.g., 8-16 seconds)
3. **Player has options:**
   - Respond before timer expires → Normal conversation flow
   - Open text input window → Timer pauses
   - Wait silently → NPC automatically continues speaking
4. **NPC continuation** happens naturally based on context

### Timer Behavior

**Timer Starts:**
- After the NPC finishes speaking their last line
- Only when waiting for player input
- Only if feature is enabled in MCM menu

**Timer Pauses/Stops:**
- Player opens text input or menu
- Player provides voice/text input
- Conversation ends

**Timer Resets:**
- When player cancels text input (gives full delay again)

### Configuration

**In-Game (MCM Menu):**
- Navigate to: Mod Configuration Menu → Mantella → General → NPC Auto-Continuation
- **Enabled**: Toggle the feature on/off (default: OFF)
- **Delay (seconds)**: Set how long to wait before NPC continues (1-60 seconds, default: 10)

**Mantella Web UI (Prompts Tab):**
- **NPC Auto-Continuation Prompt**: Customize the directive sent to the LLM when timer expires
- Default prompt guides the NPC to elaborate, ask questions, change topics, or comment on surroundings

## Design Philosophy

The feature is designed to:
- **Reduce awkward silence** in conversations
- **Maintain immersion** by keeping NPCs active and engaged
- **Respect player agency** by giving sufficient time to respond
- **Feel natural** - NPCs behave like real people who don't just stop talking mid-conversation

The timer deliberately starts **after** the NPC finishes speaking (not during), ensuring the full configured delay is available for the player to think and respond.

## Implementation Architecture

**Game Mod (Papyrus):**
- Uses a single-fire timer (`RegisterForSingleUpdate`) when PLAYERTALK response is received
- Waits for NPC to finish speaking (`_isTalking` flag) before starting countdown
- Sends auto-continuation request to Mantella when timer expires
- Manages timer lifecycle (start, stop, restart) based on player actions

**Mantella Backend (Python):**
- Receives `mantella_auto_continue` flag in HTTP request
- Injects continuation directive from config into conversation context
- LLM generates natural continuation based on conversation history + directive
- Continuation prompt is NOT saved to conversation logs (marked as system-generated)

**Communication Flow:**
```
1. NPC finishes speaking → Papyrus starts timer
2. Timer expires → Papyrus sends auto-continue request
3. Mantella injects directive → LLM generates response
4. Response sent back → NPC speaks continuation
5. Timer starts again (if still waiting for player input)
```

## Use Cases

**Exploration/Investigation:**
- Player is examining surroundings while talking to a quest-giver
- NPC elaborates on quest details or lore while player explores

**Thoughtful Decisions:**
- Player is considering dialogue options
- NPC adds pressure, clarification, or changes approach

**Multi-NPC Conversations:**
- Player takes a backseat role
- NPCs engage in back-and-forth dialogue naturally

**Immersive Roleplay:**
- Player character is silent/stoic
- NPCs react to silence realistically (concern, frustration, continued explanation)

## Benefits

- **More Natural Conversations**: NPCs feel alive and engaged
- **Reduced Pressure**: Players don't feel rushed by instant silence
- **Increased Immersion**: Conversations flow like real discussions
- **Flexible Pacing**: Configurable delay accommodates different playstyles
- **Seamless Integration**: Works with all existing Mantella features

## Customization

The continuation prompt can be customized to guide NPC behavior:
- Make NPCs more/less patient about silence
- Encourage specific behaviors (asking questions vs elaborating)
- Add personality-specific reactions to silence
- Adjust formality/informality of continuations

Example custom prompts:
- Impatient: *"The player hasn't responded. Show mild impatience and ask if they're listening."*
- Patient: *"The player is silent. Continue explaining your point or ask a gentle question."*
- Lore-focused: *"The player hasn't spoken. Share relevant lore or elaborate on your previous statement."*

---

**Status**: ✅ Implemented and Ready for Use
**Version**: 1.0
**Configuration Required**: Enable in MCM menu and optionally customize prompt in Mantella Web UI
