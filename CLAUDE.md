# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a generative text adventure game (Zork-like) that uses Claude AI for dynamic NPC dialogue. The game features turn-based combat, a shop system, quests, and AI-powered conversations.

## Setup and Running

**Dependencies:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install anthropic
```

**API Key Setup:**
Create `./secrets/anthropic.key` with your Anthropic API key, or set `ANTHROPIC_API_KEY` environment variable.

**Run the game:**
```bash
python generative_zork_like.py
```

## Code Architecture

**Core Data Models:**
- `World` - Contains player, locations, NPCs, flags, and active monster
- `Player` - Tracks location, inventory, quests, gold, and HP
- `Location` - Has description, exits, NPCs, items, and visited state
- `NPC` - Has personality and persistent memory list
- `Monster` - Combat stats for turn-based fighting

**Key Systems:**

**Combat System** (`do_attack`, `do_defend`, `do_flee`):
- Turn-based with player damage calculation based on inventory (sword bonus)
- Monster spawning triggered by location visits (see `describe_location`)
- Combat state managed via `w.flags["in_combat"]`

**NPC Dialogue** (`npc_reply_claude`):
- Uses Claude API for dynamic conversations
- NPCs maintain persistent memory of interactions
- Quest triggering based on conversation keywords (e.g., "gem" or "cave" with blacksmith)

**Shop System** (`buy_item`, `show_shop`):
- Items defined in `SHOP` dictionary
- Gold-based transactions with inventory updates

**Dynamic Content Seeding**:
- Cave items and monsters spawn on first visit (see `describe_location` cave seeding logic)
- Uses `w.flags` to track one-time events

**Quest System**:
- Simple state tracking in `w.player.quests`
- Quest completion triggers game ending (taking the gem)

## Important Implementation Details

- All locations, NPCs, and items use underscore-separated keys internally
- Combat prevents most other actions (movement, item interaction)
- API key loading has multiple fallback paths (env var, local secrets, home directory)
- Game uses dataclasses for clean state management
- Parser handles various command formats (e.g., "go forest path" → "forest_path")