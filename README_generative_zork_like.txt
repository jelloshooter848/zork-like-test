
Generative Zork-like Adventure
==============================

A complete text adventure game featuring AI-powered NPCs, turn-based combat, 
quest progression, and an immersive fantasy world.

## Setup & Running

```bash
# Easy Setup - Use the Launcher (Recommended)
./launch-game.sh

# OR Manual Setup
python3 -m venv venv
source venv/bin/activate
pip install pygame colorama anthropic

# Create API key file
mkdir -p secrets
echo "YOUR-ANTHROPIC-KEY" > secrets/anthropic.key

# Run the game
python generative_zork_like.py
```

## Game Features

**🎮 Modern Interface:**
- **Context Menus**: Smart numbered options based on current situation
- **Color-Coded Display**: NPCs (cyan), items (yellow), combat (red), quests (green) 
- **ASCII Art Headers**: Beautiful visual representations for all locations
- **Save/Load System**: JSON-based saves with timestamps and multiple slots
- **Auto-Save**: Automatic progress saving on quest completions
- **Background Music**: Dynamic soundtrack that changes with locations and events

**🗡️ Adventure Elements:**
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

**Save & Utility:**
- `save [name]` - Save game (default: quicksave)
- `load [name]` - Load saved game
- `saves` - List available save files
- `help` - Show command list
- `quit` - Exit game

**Music:**
- `music` - Toggle background music on/off
- `volume <0-10>` - Adjust music volume (0=off, 10=max)

**Modern Features:**
- **Numbered Menu**: Type 1-9 to select context menu options
- **Auto-Save**: Game saves automatically on major events
- **Color Display**: Enhanced visual experience with colored text
- **Dynamic Music**: Atmospheric soundtrack with 8+ music categories

## Launcher Options

**Option 1: Simple Launcher (Recommended)**
```bash
./launch-game.sh
```
- Automatically sets up virtual environment
- Installs all dependencies (pygame, colorama, anthropic)
- Launches game in new terminal window
- Cross-platform terminal detection

**Option 2: Desktop Shortcut**
- Double-click `Zork-Like Game.desktop` file
- Integrates with Linux desktop environments
- Uses the launcher script automatically

**Option 3: GUI Desktop App**
```bash
python3 create-desktop-app.py
```
- Full GUI interface with tkinter
- Terminal-like game window
- Built-in command input and scrollable output

**Option 4: Standalone Executable**
```bash
./build-executable.sh
```
- Creates completely portable executable
- Includes all dependencies and music files
- No Python installation required

## Music System

The game features a comprehensive background music system:

**Music Categories:**
- 🏘️ **Village** - Peaceful town themes for safe areas
- 🌲 **Forest** - Ambient nature sounds for exploration
- ⛰️ **Cave** - Dark, atmospheric dungeon music
- 🏛️ **Ruins** - Mysterious ancient themes
- ⚔️ **Combat** - Intense battle music during fights
- 👑 **Boss** - Epic themes for major encounters
- 🎉 **Victory** - Triumphant music for successful battles
- 💀 **Defeat** - Somber themes for game over

**Audio Support:**
- Multi-backend support (pygame, playsound, winsound)
- Supports .ogg, .mp3, and .wav audio files
- Graceful fallback when audio libraries unavailable
- Threaded playback for smooth gameplay