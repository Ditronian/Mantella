# Dynamic Quest System - MVP Spec

## Overview

NPCs dynamically generate quests through natural Mantella conversations. The LLM selects from constrained quest templates, filling slots with validated game data. The Python backend tracks quest state (persisted as JSON). Papyrus handles world manipulation (item placement, follower management) and completion detection.

The key differentiator from vanilla radiant quests: **the NPC is an AI participant**, not a quest marker. Conversations drive quest creation, quest progression, and quest resolution.

---

## MVP Quest Types

### 1. Expedition

**Example:** *Arniel Gane asks you to escort him deep into Mzulft to find a Dwemer Convector.*

**What happens:**
- NPC asks player to accompany them to a dungeon
- NPC becomes a follower (via existing follow action or Nether's Follower Framework)
- Player and NPC travel to the dungeon together — NPC is a live Mantella companion the entire time
- The dungeon already has enemies (vanilla spawns) — no enemy spawning needed
- At/near the destination, the objective item is spawned into a container or placed in the space
- NPC reacts to the journey, combat, and discovery through natural conversation
- Quest completes when objective is met (item found, location reached, thing observed)

**Why it's good:** The NPC is a living companion with personality, opinions, and reactions. Every expedition is different because the AI drives the narrative. Arniel is nervous and academic. Mjoll is fearless and chatty. Same template, completely different experience.

### 2. Retrieval

**Example:** *Adrianne says bandits stole a shipment of weapons. They're at Redoran's Retreat. Get it back.*

**What happens:**
- NPC tells player to go to a location and retrieve an item
- When player enters the target location, the quest item is spawned into a container (or onto an enemy) in that location
- The dungeon's existing enemies provide the challenge
- Player retrieves item, returns to NPC
- NPC reacts to success (or player returning empty-handed)

**Why it's good:** Classic quest loop — go somewhere, fight through it, bring something back. Simple, satisfying, endlessly variable because the NPC's motivation and the target location change.

### 3. Persuasion Mission

**Example:** *Faralda asks you to talk to Nirya and convince her to stop reading through her lecture notes.*

**What happens:**
- NPC gives player a social objective involving another named NPC
- Player finds the target NPC and has a Mantella conversation
- The "challenge" is the conversation itself — the player must actually persuade, intimidate, negotiate, or deceive through dialogue
- The target NPC's AI decides whether they're convinced based on what the player says
- Player returns to quest giver — outcome determines reaction

**Why it's good:** This is uniquely Mantella. No other system can do this. The quest challenge IS an AI conversation. Success isn't a dice roll — it's whether you actually said the right things. The target NPC has their own personality, biases, and stubbornness.

**Completion detection:** When player returns to quest giver, the backend injects context: "You asked the player to convince Nirya to stop reading your notes. The player spoke to Nirya. Nirya's response was: [summary of that conversation]." The quest giver's AI reacts naturally.

### 4. Bounty Hunt

**Example:** *A tavern keeper says a dangerous mage has been terrorizing travelers near Falkreath.*

**What happens:**
- NPC identifies a target to kill and a location
- Target could be: a named NPC (from a curated safe-to-kill list), or a spawned unique enemy at the location
- Player travels to location, finds and kills target
- Returns to NPC for reward/acknowledgment

**Why it's good:** Straightforward combat quest. Satisfying loop. The NPC's personal stake in the bounty (revenge? fear? civic duty?) makes each one feel motivated rather than procedural.

**Open question:** If we spawn a bounty target, we can track their death directly. If we point at an existing named NPC, we need the safe-to-kill whitelist (significant curation work). For MVP, spawning a single leveled "boss" enemy at the location on player arrival may be simpler and safer.

---

## Architecture

### Quest Lifecycle

```
1. CREATION
   NPC conversation -> LLM outputs structured Quest action ->
   Server validates slots against game data ->
   Quest stored in JSON -> Papyrus notified (notification shown, item given if needed)

2. ACTIVE
   Quest context injected into relevant NPC prompts ->
   Player travels/acts in game world ->
   On location arrival: Papyrus spawns items/targets as needed ->
   Player completes objective

3. COMPLETION
   Player returns to quest giver (or completion auto-detected) ->
   Quest status injected into conversation context ->
   NPC reacts naturally via LLM -> Quest marked complete ->
   Reward delivered (gold via AddItem, or narrative reward via dialogue)

4. PERSISTENCE
   Quest state saved as JSON in Mantella user folder ->
   Restored on game/server restart ->
   Survives save/load cycles
```

### Where Things Live

| Component | Responsibility |
|-----------|---------------|
| **LLM** | Generates quest from template, picks slots from validated lists, drives NPC dialogue throughout |
| **Python Backend** | Validates quest parameters, tracks quest state, persists to JSON, injects quest context into prompts |
| **Papyrus** | Spawns items into containers, manages follower state, detects location arrival, detects completion conditions, delivers rewards |

### Quest State (JSON)

```json
{
  "active_quests": [
    {
      "id": "quest_20260322_001",
      "type": "retrieval",
      "giver": {
        "name": "Adrianne Avenicci",
        "base_id": "0001A67C",
        "ref_id": "...",
        "location": "Whiterun"
      },
      "objective": {
        "description": "Retrieve stolen weapons shipment",
        "target_location": "Redoran's Retreat",
        "target_location_id": "...",
        "item_to_spawn": "Iron Sword",
        "item_form_id": "00012EB7",
        "item_count": 1,
        "spawn_method": "container"
      },
      "reward": {
        "type": "gold",
        "amount": 500,
        "description": "I'll pay you 500 gold for the trouble"
      },
      "status": "active",
      "created_session": "2026-03-22T14:30:00",
      "completion_conditions": {
        "player_has_item": true,
        "talked_to_giver": false
      }
    }
  ],
  "completed_quests": []
}
```

---

## Open Problems

### 1. Location Data Table

**The problem:** The LLM needs to reference real locations by name, and Papyrus needs to detect when the player arrives. Currently, locations are just strings ("Dragonsreach") with no FormID mapping.

**What we need:** A curated data file mapping location names to:
- Location FormID (for `OnLocationChange` detection)
- Location type (dwemer ruin, nordic tomb, bandit camp, cave, fort, mine)
- Rough danger tier (so a Whiterun shopkeeper doesn't send you to Labyrinthian)
- Hold/region (so quests reference geographically sensible locations)

**Scope:** 50-100 dungeon/POI locations would provide enormous variety. Every Hold should have several options across danger tiers.

**How to build it:** Location FormIDs can be extracted from Skyrim.esm via xEdit or pulled from UESP wiki data. This is manual curation work but only needs to be done once.

**Format:**
```csv
name,form_id,type,danger_tier,hold,description
Embershard Mine,00009B2D,mine,1,Falkreath,Small iron mine occupied by bandits
Bleak Falls Barrow,00003432,nordic_tomb,2,Whiterun,Ancient Nordic ruin with draugr
Mzulft,0001A490,dwemer_ruin,4,Eastmarch,Massive Dwemer ruin
```

### 2. Item Spawning in Containers

**The problem:** When a quest requires the player to find an item at a location, we need to place it there. Ideally in a container (chest) that already exists in the dungeon. The player shouldn't find the item floating in midair.

**Sub-problems:**
- **Finding containers at runtime:** Can Papyrus find containers in a loaded cell? `Game.FindClosestReferenceOfAnyTypeInListFromRef` or similar functions could locate chests near the player. But cells only load when the player is nearby, so this must happen on arrival.
- **Which container:** Ideally the "boss chest" or end-of-dungeon chest, not the first chest the player sees. Without curated container FormIDs per location, we may need to find the container closest to a specific point, or just pick a random container in the cell.
- **Alternative: item on enemy:** `AddItem` to an existing NPC/enemy in the location. Harder because we need to find enemy actors in the loaded cell. Spawning a single enemy and putting the item on them might be more reliable.
- **Alternative: item on ground:** `PlaceAtMe` near the player when they reach the deepest part of the location. Less immersive but mechanically simple.

**Needs investigation:** What Papyrus functions are available for finding containers in a loaded cell? This determines whether "item in a random chest" is feasible or if we need a different approach.

### 3. Completion Detection

**The problem:** How does the system know the player completed the objective?

| Quest Type | Detection Method | Difficulty |
|------------|-----------------|------------|
| Retrieval | `GetItemCount` when player talks to quest giver | Easy — checked during conversation |
| Expedition | Player + NPC at target location, objective item found | Medium — need location check + item check |
| Persuasion | Player had conversation with target NPC | Medium — server tracks conversation history, needs to summarize outcome |
| Bounty Hunt | Target is dead | Easy if spawned (OnDeath event), harder for named NPCs |

**For retrieval/expedition:** Check during the return conversation. When the player talks to the quest giver, the backend checks quest conditions and injects status into the prompt.

**For persuasion:** The backend already stores conversation summaries. When the player spoke to the target NPC, that conversation was summarized. Inject that summary into the quest giver's context on return.

**For bounty:** If we spawn the target, register an `OnDeath` event on the spawned actor. If targeting a named NPC, poll `Actor.IsDead()` — but this requires maintaining a reference to the target actor.

### 4. LLM Structured Output and Validation

**The problem:** The LLM must output quest data in a parseable format, and every slot must be validated against real game data before the quest activates.

**Approach:** Extend the existing action system. Quest creation is an action with structured parameters:

```
Quest:expedition:Mzulft:Dwemer Convector:I need to find a specific Dwemer Convector for my research
Quest:retrieval:Redoran's Retreat:Iron Sword:Bandits stole my finest blade
Quest:persuasion:Nirya:stop reading my lecture notes:She's been going through my research
Quest:bounty:Falkreath Hold:bandit_chief:A bandit leader has been terrorizing the roads
```

**Validation pipeline:**
1. Parse structured output into template type + slots
2. Validate location exists in location data table
3. Validate item exists in item FormID list (for retrieval/expedition)
4. Validate target NPC exists in character CSV (for persuasion/bounty)
5. Check location danger tier is appropriate for quest giver's context
6. If any validation fails: quest silently doesn't activate, conversation continues normally

**The LLM prompt** must include the available locations, items, and NPCs as constrained lists. This could be a subset relevant to the quest giver's hold/region to keep the prompt manageable.

### 5. Quest-Aware NPC Context

**The problem:** NPCs involved in active quests need to "remember" them across conversations.

**Current state:** Mantella already stores conversation summaries per NPC. If the player discussed a quest with Arniel, that conversation's summary will mention it. This provides baseline continuity.

**Enhancement needed:** When a quest is active, inject explicit quest context into the NPC's system prompt:

For the quest giver:
> *You gave the player a task: retrieve your stolen sword from Redoran's Retreat. The quest is still active. If the player has returned with the sword, express gratitude and offer the promised reward. If they haven't completed it yet, ask about their progress.*

For the target NPC (persuasion):
> *Faralda asked the player to convince you to stop reading her lecture notes. You are defensive about this — you believe academic knowledge should be shared freely. The player may try to persuade you.*

This is just additional context appended to the existing character prompt. The infrastructure for injecting dynamic context already exists (location, time, weather, in-game events are all injected this way).

### 6. Reward Delivery

**The problem:** NPCs promise rewards. They need to deliver.

**Options by complexity:**
- **Gold:** `AddItem(Gold001, amount)` on the player. Requires adding `AddItem` to the Papyrus action handlers.
- **Items:** `AddItem(specificItem, count)`. Same mechanism, needs item FormID.
- **Services:** NPC offers to train you, gives you a discount, shares information. Pure dialogue — no game mechanic needed.
- **Relationship:** `SetRelationshipRank` to improve disposition. Already available in Papyrus.

**MVP:** Gold + relationship rank change. Both are simple `AddItem`/`SetRelationshipRank` calls triggered by a new quest completion action.

### 7. Preventing Impossible Quests

**The problem:** The LLM might generate quests that are technically valid (all slots pass validation) but practically impossible or nonsensical.

**Examples of bad quests:**
- NPC in Solitude sends you to a dungeon in Solstheim (too far, wrong worldspace)
- Quest giver asks you to persuade someone who is dead in the player's game
- Two active quests send you to the same location for contradicting reasons
- NPC offers 50,000 gold reward (lore-breaking for a shopkeeper)

**Mitigation strategies:**
- Region-lock quest locations to the quest giver's hold + adjacent holds
- Cap rewards based on NPC's apparent wealth/station (prompt engineering)
- Limit concurrent active quests (e.g., max 3)
- The LLM prompt should include active quest summaries to avoid conflicts
- Some of this is just good prompt engineering rather than hard validation

### 8. Follower Framework Integration (Expedition Quests)

**The problem:** Expedition quests require the NPC to follow the player reliably through a dungeon.

**Current state:** Mantella has a follow action (`mantella_npc_follow`) that uses faction-based following and `EvaluatePackage()`. Director Mode also has `KeepOffsetFromActor`.

**Better option:** The user has Nether's Follower Framework, which handles follower AI robustly (pathfinding, teleport catch-up, combat behavior). For expedition quests, making the NPC a follower through NFF would be more reliable than the built-in follow system.

**Integration approach:** The quest creation action triggers making the NPC a follower. This could be done via:
- The existing follow action (simplest, may have pathing issues in dungeons)
- Console command via SKSE to add to NFF (if NFF exposes an API)
- Manual player action (quest tells player to recruit the NPC — least elegant but most reliable)

**Needs investigation:** Does Nether's Follower Framework expose a Papyrus API or mod events that Mantella could call directly?

---

## Data Files Needed

| File | Contents | Estimated Size | Priority |
|------|----------|---------------|----------|
| `locations.csv` | Location name, FormID, type, danger tier, hold | 50-100 rows | **Critical** — needed for all location-based quests |
| `quest_items.csv` | Item name, FormID, value, category | 50-100 rows | **Critical** — needed for retrieval/expedition objectives |
| `safe_kill_npcs.csv` | NPC name, ref_id, base_id, location, reason safe | 20-50 rows | **Nice to have** — only needed for bounty quests targeting named NPCs |
| `quest_rewards.csv` | Reward type, FormID, typical value range | 10-20 rows | **Low priority** — can hardcode gold initially |

---

## Implementation Order

1. **Quest state tracker** (Python) — JSON persistence, quest lifecycle management
2. **Quest context injection** (Python) — Inject active quest state into NPC prompts
3. **Location data file** — Curate initial location table
4. **Item data file** — Curate quest item table
5. **LLM quest action** — New action type with structured output, validation pipeline
6. **Papyrus item spawning** — `AddItem` to containers, `PlaceAtMe` fallback
7. **Papyrus completion detection** — `GetItemCount` checks, location arrival detection
8. **Papyrus reward delivery** — `AddItem` gold/items to player
9. **Retrieval quest template** — End-to-end working quest type
10. **Persuasion quest template** — Conversation-based quest type
11. **Expedition quest template** — Follower integration + retrieval
12. **Bounty hunt template** — Kill target detection

Steps 1-3 are foundational. Step 9 is the first playable quest. Each subsequent template builds on the same infrastructure.

---

## Non-Goals for MVP

- Quest journal integration (ESP quest records)
- Map markers or waypoints
- Multi-step quest chains (sequences of objectives)
- Timed quests or deadlines
- Quest failure consequences beyond NPC disappointment
- Procedural dungeon generation
- New item creation (only spawn existing vanilla items)
- Voice-acted quest descriptions (NPC describes quest via normal Mantella TTS)
