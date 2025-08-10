
Generative Zork-like Adventure
==============================

A complete text adventure game featuring AI-powered NPCs, turn-based combat, 
quest progression, and an immersive fantasy world.

## Setup & Running

```bash
# Setup virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install anthropic

# Create API key file
mkdir -p secrets
echo "YOUR-ANTHROPIC-KEY" > secrets/anthropic.key

# Run the game
python generative_zork_like.py
```

## Game Features

- **6-Quest Story Campaign**: Complete quest chain from village newcomer to hero
- **AI-Powered NPCs**: Dynamic conversations using Claude AI with persistent memories
- **Turn-based Combat**: Strategic battles with attack/defend/flee options
- **Weapon Progression**: Rusty sword → Broad sword (crafted from iron ore)
- **Multiple NPCs**: Blacksmith, Elder Theron (cursed), Mira the Healer
- **8 Locations**: Village, mine, cave, ruins, tower, and NPC dwellings
- **Quest System**: Track progress with `quests` command
- **Character Growth**: Gain HP through magical amulet (+5 max HP)
- **Economic System**: Gold, shop, healing services

## Quest Progression

1. **Prove Your Worth** - Get iron ore, forge broad sword
2. **Clear the Cave** - Defeat Cave Beast, obtain gem
3. **Heal the Elder** - Trade gem for magical amulet
4. **Retrieve the Scroll** - Need broad sword for Ancient Guardian
5. **Forge the Key** - Trade scroll for master key
6. **Claim Ancient Treasure** - Use key on sealed tower

## Commands

**Exploration:**
- `look` / `l` - Examine current location
- `go <place>` - Move to connected areas
- `inventory` / `i` - Check items and gold
- `stats` - View HP and combat status
- `quests` / `q` - Track quest progress

**Interaction:**
- `talk to <npc> <message>` - Converse with NPCs
- `ask <npc> about <topic>` - Ask specific questions
- `shop` - View items for sale
- `buy <item>` - Purchase from merchants
- `take <item>` / `drop <item>` - Manage items

**Combat:**
- `attack` - Strike enemies
- `defend` - Reduce incoming damage
- `flee` - Attempt to escape battle

**Other:**
- `help` - Show command list
- `quit` - Exit game