# Redo Directive Feature

## Overview

The Redo Directive allows players to regenerate the last NPC response with optional guidance, enabling on-the-fly conversation correction and direction. This feature is invaluable when an NPC says something out-of-character, misunderstands context, or the conversation takes an unwanted direction.

## How It Works

### Basic Usage

**Format**: `redo` or `redo: your guidance here`

**Examples:**
- `redo` - Regenerate the last response with no changes
- `redo: Lydia should sound more enthusiastic`
- `redo: Balgruuf should mention his concerns about the Imperials`
- `redo: be less formal`

### What Happens

1. **Player types the redo command** in text input
2. **Last NPC message is removed** from conversation history
3. **Optional guidance is added** as context for the LLM
4. **New response is generated** incorporating the guidance
5. **Conversation continues** from the new response

### Guidance Flexibility

**Without Guidance** (`redo`):
- Simply regenerates with the same context
- Useful for low-quality TTS, misheard responses, or random LLM variation

**With Guidance** (`redo: ...`):
- Directs the LLM on how to change the response
- Can adjust tone, content, character behavior, or topic focus
- Guidance is temporary - only affects this regeneration

## Use Cases

### Character Consistency
```
NPC: "Yeah, whatever. I don't care about honor."
Player: redo: Farkas values honor and loyalty
NPC: "Honor means everything. It's what separates us from bandits."
```

### Tone Adjustment
```
NPC: "I suppose I could help you with that trivial matter."
Player: redo: be more friendly and helpful
NPC: "I'd be happy to help! Let me know what you need."
```

### Content Correction
```
NPC: "I've never been to Whiterun before."
Player: redo: you've lived in Whiterun your whole life
NPC: "Growing up in Whiterun, I've seen a lot of changes over the years."
```

### Topic Redirection
```
NPC: "Anyway, let's talk about something else."
Player: redo: stay focused on the dragon threat
NPC: "These dragons... we need to prepare. The city isn't ready for this."
```

## Design Philosophy

The redo directive is designed to:
- **Empower players** to shape conversations without breaking immersion
- **Maintain narrative control** while preserving AI flexibility
- **Correct mistakes** gracefully without restarting conversations
- **Iterate on responses** until the desired outcome is achieved

The feature treats guidance as **contextual hints** rather than rigid commands, allowing the LLM to interpret and apply them naturally within the character's voice.

## Implementation Architecture

**Detection:**
- Player input is checked for the `redo` keyword (case-insensitive)
- Supports format: `redo: guidance text` or just `redo`
- Original redo message is marked as system-generated (not saved to history)

**Processing:**
1. Parse player input for keyword and optional guidance
2. Remove the last assistant message from conversation thread
3. If guidance provided, inject it as a user message with clear directive framing
4. Trigger new LLM generation with updated context
5. Continue conversation normally from new response

**Message Handling:**
- Redo command itself is NOT saved to conversation logs
- Guidance (if provided) IS saved to maintain context
- Previous NPC response is permanently removed
- New response replaces it in conversation flow

## Limitations

**Cannot Redo:**
- Player messages (only NPC responses)
- Messages from multiple turns ago (only the most recent NPC response)
- System messages or conversation summaries

**Guidance Constraints:**
- Guidance is interpreted by the LLM, not guaranteed to be followed exactly
- Complex or contradictory guidance may be ignored or misinterpreted
- Character personality and existing context still influence the response

## Best Practices

### Effective Guidance

**Good:**
- `redo: mention the civil war`
- `redo: be more sympathetic`
- `redo: Serana should be conflicted about this`

**Less Effective:**
- `redo: say exactly "I will help you"` (too rigid)
- `redo: completely change your personality` (contradicts character)
- `redo: talk about seventeen different topics` (too complex)

### When to Use

**Use Redo When:**
- NPC response breaks character
- LLM misunderstood player intent
- Tone or content is slightly off
- Want to explore alternative conversation paths

**Don't Use Redo When:**
- Player made a mistake (just respond normally)
- Multiple turns ago (conversation has moved on)
- Trying to force OOC behavior (use Direct directive instead)

## Comparison to Direct Directive

**Redo Directive:**
- Modifies the LAST response
- Removes and regenerates previous NPC message
- Guidance is optional
- Best for corrections and iterations

**Direct Directive:**
- Adds NEW instructions for NEXT response
- Doesn't remove anything
- Instruction is required
- Best for proactive direction

---

**Status**: ✅ Implemented and Ready for Use
**Version**: 1.0
**Keyword**: `redo` (case-insensitive)
**Configuration**: Keyword customizable in `config.ini` under `[Language]` → `redo_conversation_keyword`
