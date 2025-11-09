# Direct Directive Feature

## Overview

The Direct Directive provides explicit, out-of-character control over NPC behavior and conversation flow. Unlike normal dialogue where players interact in-character, the Direct directive allows players to issue instructions to NPCs as if directing actors in a scene, enabling precise narrative control and creative storytelling.

## How It Works

### Basic Usage

**Format**: `direct: your instruction here`

**Examples:**
- `direct: Lydia speaks and mentions she heard rumors about dragons`
- `direct: Tullius looks concerned and asks about my loyalty`
- `direct: Serana changes the subject to her family`
- `direct: everyone becomes suspicious of the player`

### What Happens

1. **Player types the direct command** in text input
2. **Instruction is extracted** and marked as out-of-character
3. **Directive is added to conversation** as guidance for the LLM
4. **NPCs respond** following the instruction while maintaining their character
5. **Original "direct: ..." message is removed** from saved history

### Instruction Clarity

The directive is framed to the LLM as an explicit instruction from a director/narrator, making it clear this is **not** in-character dialogue but rather a **scene direction**.

**Framing:**
```
[Out-of-character instruction from the director]: {your instruction}
```

This ensures the LLM treats it as authoritative guidance rather than player dialogue to respond to.

## Use Cases

### Narrative Control
```
Player: direct: Ulfric speaks and expresses doubt about the player's intentions
Ulfric: I've heard your words, but words are cheap. What proof do I have
         that you're truly committed to our cause?
```

### Topic Introduction
```
Player: direct: Farengar mentions he found something interesting about dragon magic
Farengar: Ah, perfect timing! I've just uncovered a fascinating passage about
          the Thu'um in this ancient text. You should hear this.
```

### Multi-NPC Scenes
```
Player: direct: Lydia and Irileth start arguing about security protocols
Lydia: With all due respect, Irileth, your patrols aren't covering the western gate.
Irileth: My patrols are exactly where they need to be. Perhaps you should focus
         on your own duties, housecarl.
```

### Emotional Shifts
```
Player: direct: everyone in the conversation becomes worried about an approaching storm
Balgruuf: Do you hear that? The wind is picking up. This doesn't feel natural.
Farengar: I sense something... magical about this storm. We should take precautions.
```

### Scene Setup
```
Player: direct: Delphine acts secretive and leads the player to a hidden room
Delphine: Follow me. And keep quiet - we can't talk here. *glances around nervously*
```

## Design Philosophy

The direct directive is designed to:
- **Maximize creative control** for storytelling and roleplay
- **Bypass AI limitations** when NPCs aren't understanding context
- **Enable complex scenarios** that require specific NPC behaviors
- **Maintain character voices** while following instructions
- **Support dynamic narratives** beyond simple question-answer dialogue

The feature treats instructions as **authoritative scene directions** while still allowing NPCs to express them naturally within their established personalities.

## Implementation Architecture

**Detection:**
- Player input is checked for `direct` keyword prefix (case-insensitive)
- Format: `direct: instruction text` (instruction is required)
- Original "direct: ..." message is marked as system-generated (not saved)

**Processing:**
1. Parse player input for keyword and instruction
2. Extract instruction text after the colon
3. Frame instruction as out-of-character director guidance
4. Add directive to conversation thread with appropriate framing
5. Trigger LLM generation with the directive included
6. NPCs respond following the instruction

**Message Handling:**
- Direct command itself is NOT saved to conversation logs
- Directive instruction IS saved to maintain context of why NPCs behaved this way
- Future summaries will reflect the behavior but not the meta-command
- NPCs retain awareness of what they said/did under directive influence

## Instruction Flexibility

### What Works Well

**Specific NPC Actions:**
- `direct: Lydia draws her weapon`
- `direct: Balgruuf stands up and paces`
- `direct: Serana reveals a secret about her past`

**Emotional States:**
- `direct: everyone becomes more relaxed`
- `direct: Tullius grows suspicious`
- `direct: Aela shows pride in the player's accomplishments`

**Topic Control:**
- `direct: the conversation shifts to discussing the Thieves Guild`
- `direct: Farengar brings up the topic of Dwemer technology`
- `direct: someone mentions hearing strange noises at night`

**Scene Progression:**
- `direct: an argument breaks out between the NPCs`
- `direct: the mood becomes tense`
- `direct: everyone agrees to help the player`

### What's Less Effective

**Overly Specific Dialogue:**
- `direct: Lydia says exactly "I will protect you with my life"` - Too rigid, LLM may paraphrase
- Better: `direct: Lydia pledges her protection` - Achieves the same goal naturally

**Contradicting Core Personality:**
- `direct: Jarl Balgruuf acts cowardly and weak` - Contradicts established character
- LLM may resist or interpret this in a character-appropriate way

**Multiple Complex Instructions:**
- `direct: Lydia talks about dragons while Farengar discusses magic and Balgruuf worries about politics and someone mentions the weather`
- Better: Break into multiple separate directives

## Comparison to Other Features

### Direct vs. Redo

**Direct Directive:**
- Proactive - guides FUTURE responses
- Adds new instruction
- Creates new narrative direction
- Best for: Scene control, topic introduction

**Redo Directive:**
- Reactive - fixes PREVIOUS response
- Removes and regenerates last message
- Corrects unwanted outcomes
- Best for: Corrections, iterations

### Direct vs. Normal Dialogue

**Direct Directive:**
- Out-of-character instruction
- Controls NPC behavior explicitly
- Bypasses natural conversation flow
- NPCs know to follow the direction

**Normal Dialogue:**
- In-character interaction
- NPCs interpret and respond naturally
- Organic conversation flow
- NPCs may misunderstand or disagree

## Best Practices

### Effective Instructions

**Clear and Concise:**
- `direct: Serana mentions her mother`
- Not: `direct: Serana should maybe possibly talk about her mother if it makes sense`

**Character-Appropriate:**
- `direct: Ulfric speaks passionately about Skyrim's independence`
- Not: `direct: Ulfric suddenly loves the Empire`

**Single Focus:**
- `direct: Lydia offers to accompany the player`
- Not: `direct: Lydia offers help and also discusses the weather and asks about dragons`

### When to Use

**Use Direct When:**
- Need specific NPC behavior for storytelling
- Want to introduce a new topic organically
- NPCs aren't picking up on subtle player cues
- Creating a complex scene with multiple NPCs
- Testing character responses to specific scenarios

**Avoid Direct When:**
- Normal dialogue would work fine
- Trying to force completely out-of-character behavior
- Micromanaging every response (kills spontaneity)
- Could use Redo to fix the last response instead

## Privacy and Immersion

The direct command is **intentionally hidden** from conversation logs and summaries to preserve immersion. When reviewing conversation history, players and NPCs see the natural flow of dialogue and events, not the meta-instructions that guided them.

**What's Saved:**
- NPC responses following the directive
- Natural-seeming conversation flow
- Character behaviors and decisions

**What's NOT Saved:**
- The "direct: ..." command itself
- Meta-awareness of being directed
- Out-of-character framing

---

**Status**: ✅ Implemented and Ready for Use
**Version**: 1.0
**Keyword**: `direct` (case-insensitive)
**Configuration**: Keyword customizable in `config.ini` under `[Language]` → `direct_conversation_keyword`
