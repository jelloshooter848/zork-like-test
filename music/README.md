# Music System for Zork-Like Game

This directory contains background music files for the text adventure game.

## Music Categories

The game supports different music categories that play automatically based on location and situation:

### **Location Music** (Loops)
- **Village**: `village_theme.wav`, `peaceful_town.wav`
  - Plays in: village_square, blacksmith_shop, healer_tent, elder_hut
- **Forest**: `forest_ambient.wav`, `woodland_mystery.wav` 
  - Plays in: forest_path
- **Cave**: `cave_echo.wav`, `underground_depths.wav`
  - Plays in: iron_mine, hidden_cave
- **Ruins**: `ancient_ruins.wav`, `forgotten_temples.wav`
  - Plays in: deep_ruins, sealed_tower

### **Combat Music** (Loops)  
- **Regular Combat**: `battle_theme.wav`, `combat_intense.wav`
  - Random encounters (forest wolves, cave spiders, etc.)
- **Boss Combat**: `boss_battle.wav`, `epic_confrontation.wav`
  - Major bosses (Cave Beast, Ancient Guardian, Tower Guardian)

### **Event Music** (One-shot)
- **Victory**: `victory_fanfare.wav`, `triumph.wav`
  - Plays after winning combat
- **Defeat**: `game_over.wav`, `defeat_theme.wav` 
  - Plays when player dies

## Audio Requirements

### **Supported Formats**
- Primary: `.wav` files (recommended)
- Alternative: `.mp3`, `.ogg` (depending on pygame installation)

### **Audio Libraries** (Auto-detected)
1. **pygame** (preferred) - Full feature support, looping, volume control
2. **playsound** (fallback) - Basic playback, limited looping
3. **winsound** (Windows only) - System sounds

### **Installation**
```bash
# For full audio support
pip install pygame

# Alternative (basic support)  
pip install playsound
```

## Game Commands

- `music` - Show current music status
- `music on` - Enable background music
- `music off` - Disable background music  
- `volume 0.5` - Set volume (0.0 to 1.0)

## File Structure

```
music/
├── README.md
├── village_theme.wav
├── peaceful_town.wav
├── forest_ambient.wav
├── woodland_mystery.wav
├── cave_echo.wav
├── underground_depths.wav
├── ancient_ruins.wav
├── forgotten_temples.wav
├── battle_theme.wav
├── combat_intense.wav
├── boss_battle.wav
├── epic_confrontation.wav
├── victory_fanfare.wav
├── triumph.wav
├── game_over.wav
└── defeat_theme.wav
```

## Music Behavior

- **Automatic**: Music changes based on location and game state
- **Smart Transitions**: Won't restart same category music
- **Combat Override**: Combat music takes priority over location music
- **Graceful Fallback**: Works without audio libraries (silent mode)
- **Threaded Playback**: Non-blocking, won't affect game performance

## Adding Custom Music

1. Place `.wav` files in this directory with the exact names listed above
2. Game will randomly select from available tracks in each category
3. Missing files are silently skipped - no errors
4. Restart game to detect new music files

The music system enhances immersion but is completely optional - the game works perfectly without any audio files!