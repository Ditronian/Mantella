# Feature Spec: Selective Radiant Dialogue

## Problem Statement

The current radiant dialogue system randomly selects NPCs for conversations, which leads to:
- Same NPCs being picked repeatedly while others are ignored
- No player agency in determining which NPCs should converse
- Missed opportunities for interesting character interactions

## Solution Overview

Allow players to manually select two specific NPCs via in-game hotkeys to initiate a targeted radiant dialogue between them.

---

## Backend Changes (Mantella .exe - This Repository)

### Summary

The Mantella backend already fully supports targeted radiant dialogues. **No code changes are required on the backend side.**

### Why No Changes Are Needed

The radiant conversation system determines conversation type dynamically based on the actors sent in the HTTP request:

```python
# src/conversation/conversation.py:44-47
if not self.__context.npcs_in_conversation.contains_player_character():
    self.__conversation_type = radiant(context_for_conversation.config)
```

When the game mod sends a `start_conversation` request with exactly two NPCs (neither being the player), Mantella automatically:
1. Detects this as a radiant conversation
2. Loads both character bios and histories
3. Uses radiant-specific prompts
4. Manages the conversation lifecycle appropriately

### Existing API Contract

The mod can already send any specific pair of NPCs. Here's the exact request format:

**Endpoint**: `POST /mantella`

**Request Body**:
```json
{
    "mantella_request_type": "mantella_start_conversation",
    "mantella_worldid": "selective_radiant_<npc1_refid>_<npc2_refid>",
    "mantella_actors": [
        {
            "mantella_actor_baseid": "<hex_baseid>",
            "mantella_actor_refid": "<hex_refid>",
            "mantella_actor_name": "NPC Name 1",
            "mantella_actor_gender": 0,
            "mantella_actor_race": "Nord",
            "mantella_actor_voicetype": "MaleNord",
            "mantella_actor_is_in_combat": false,
            "mantella_actor_is_enemy": false,
            "mantella_actor_relationshiprank": 0,
            "mantella_actor_is_player": false
        },
        {
            "mantella_actor_baseid": "<hex_baseid>",
            "mantella_actor_refid": "<hex_refid>",
            "mantella_actor_name": "NPC Name 2",
            "mantella_actor_gender": 1,
            "mantella_actor_race": "Breton",
            "mantella_actor_voicetype": "FemaleCommoner",
            "mantella_actor_is_in_combat": false,
            "mantella_actor_is_enemy": false,
            "mantella_actor_relationshiprank": 0,
            "mantella_actor_is_player": false
        }
    ],
    "mantella_context": {
        "mantella_location": "Whiterun",
        "mantella_time": 14,
        "mantella_weather": "Clear",
        "mantella_ingame_events": [],
        "mantella_custom_context_values": {}
    }
}
```

**Critical Requirements**:
- Both actors MUST have `"mantella_actor_is_player": false`
- Exactly 2 actors should be sent for a two-person radiant dialogue
- All actor fields are required (baseid, refid, name, gender, race, voicetype, etc.)

**Expected Response**:
```json
{
    "mantella_reply_type": "mantella_start_conversation_completed",
    "mantella_use_narrator": false
}
```

After this, the mod should call `continue_conversation` to get NPC dialogue lines, just like normal radiant conversations.

---

## Frontend/Mod Changes Required (MantellaMod Repository)

### Overview for Mod Developer

You need to implement a two-step NPC selection system using hotkeys that stores selected NPCs and then initiates a radiant conversation with those specific actors.

### Required Implementation

#### 1. New Hotkey System

Implement two new hotkeys (or a single toggle hotkey with state):

| Hotkey | Function | Visual Feedback |
|--------|----------|-----------------|
| **Select NPC 1** | While looking at NPC, press to store as first participant | Show message: "Selected [NPC Name] as first speaker" |
| **Select NPC 2** | While looking at NPC, press to store as second participant and start conversation | Show message: "Starting radiant dialogue between [NPC1] and [NPC2]" |

**Alternative UX**: Single hotkey that cycles through states:
1. First press: Select NPC 1
2. Second press: Select NPC 2 + auto-start conversation
3. (Optional) Third press or cancel key: Clear selection

#### 2. State Management

You'll need to store:
```papyrus
; Pseudo-code structure
Actor selectedNPC1 = None
Actor selectedNPC2 = None
bool isSelectingFirstNPC = true
```

#### 3. NPC Validation

Before storing an NPC, validate:
- Target is a valid Actor (not object/container)
- Target is not the player
- Target is not already selected as the other NPC
- Target is alive and not disabled

#### 4. Start Conversation Logic

When both NPCs are selected:

1. **Build actor data** for both NPCs using existing `GetActorData()` function (or equivalent)
2. **Ensure neither actor has `is_player = true`**
3. **Generate unique world ID**: Use format like `"selective_radiant"` or include ref IDs
4. **Send HTTP request** with both actors
5. **Clear stored selections** after sending
6. **Position NPCs** to face each other (optional but nice UX)

#### 5. MCM Configuration (Optional but Recommended)

Add to Mod Configuration Menu:
- Hotkey binding for "Select NPC 1"
- Hotkey binding for "Select NPC 2" (or single toggle key)
- Option to auto-position NPCs to face each other
- Timeout to auto-clear selection (e.g., 30 seconds)

### Integration Points

The mod already has:
- HTTP communication with Mantella (`/mantella` endpoint)
- Actor data gathering (baseid, refid, name, gender, race, voicetype, etc.)
- Radiant dialogue handling (you're just changing NPC selection, not the dialogue flow)

You're essentially creating a new "spell" or hotkey action that:
1. Gets crosshair target
2. Stores actor reference
3. On second selection, calls existing `StartRadiantConversation()` but with your stored actors instead of random selection

### Example Papyrus Flow

```papyrus
; On hotkey press
Event OnKeyDown(int keyCode)
    if keyCode == SelectNPCKey
        Actor target = Game.GetCurrentCrosshairRef() as Actor

        if !target || target == PlayerRef
            Debug.Notification("Invalid target")
            return
        endif

        if selectedNPC1 == None
            selectedNPC1 = target
            Debug.Notification("Selected " + target.GetDisplayName() + " as first speaker")
        elseif selectedNPC2 == None && target != selectedNPC1
            selectedNPC2 = target
            Debug.Notification("Starting dialogue: " + selectedNPC1.GetDisplayName() + " & " + selectedNPC2.GetDisplayName())

            ; Start the radiant conversation with these specific NPCs
            StartSelectiveRadiantDialogue(selectedNPC1, selectedNPC2)

            ; Clear selections
            selectedNPC1 = None
            selectedNPC2 = None
        endif
    endif
EndEvent

Function StartSelectiveRadiantDialogue(Actor npc1, Actor npc2)
    ; Build actor arrays with both NPCs
    ; Call existing HTTP request logic but with these specific actors
    ; Ensure is_player = false for both
EndFunction
```

### Error Handling

Provide feedback for:
- "Cannot select player character"
- "Cannot select same NPC twice"
- "Target is not a valid NPC"
- "Selection cleared" (on timeout or cancel)
- "NPC is too far away" (optional distance check)

---

## Testing Checklist

### Backend (Mantella)
- [x] Receives 2-actor request with no player → creates radiant conversation (already works)
- [x] Conversation uses radiant prompts and lifecycle (already works)
- [x] Both NPC bios loaded correctly (already works)

### Frontend (Mod)
- [ ] Hotkey correctly captures crosshair target
- [ ] First NPC stored with visual feedback
- [ ] Second NPC stored and triggers conversation
- [ ] Player character rejected with message
- [ ] Same NPC twice rejected with message
- [ ] HTTP request sent with both actor data
- [ ] `is_player = false` for both actors
- [ ] Selections cleared after conversation starts
- [ ] MCM hotkey configuration works

---

## Future Enhancements

1. **Selection Preview**: Show floating markers above selected NPCs
2. **NPC History Display**: Show brief summary of past conversations between selected pair
3. **Group Radiant**: Extend to 3+ NPCs for group radiant conversations
4. **Quick-Select Menu**: SkyUI-style menu showing nearby NPCs for selection
5. **Favorites System**: Save NPC pairs for quick re-selection

---

## Communication Protocol Reference

See `src/http/communication_constants.py` for all field names:

**Actor fields** (all required):
- `mantella_actor_baseid` - Hex base ID
- `mantella_actor_refid` - Hex reference ID
- `mantella_actor_name` - Display name
- `mantella_actor_gender` - 0=male, 1=female
- `mantella_actor_race` - Race string
- `mantella_actor_voicetype` - Voice type with gender suffix
- `mantella_actor_is_in_combat` - Boolean
- `mantella_actor_is_enemy` - Boolean
- `mantella_actor_relationshiprank` - Integer
- `mantella_actor_is_player` - **Must be false for radiant**
- `mantella_actor_custom_values` - Optional object

**Context fields**:
- `mantella_location` - Location name
- `mantella_time` - Hour (0-23)
- `mantella_weather` - Weather string
- `mantella_ingame_events` - Array of event strings
- `mantella_custom_context_values` - Optional object
