#!/bin/bash

# Zork-Like Game Launcher
echo "🎮 Starting Zork-Like Game..."

# Get the directory where this script is located
GAME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$GAME_DIR"

# Check if we're being run from a file manager (no terminal)
if [ ! -t 1 ]; then
    # Running from file manager - open in new terminal
    if command -v gnome-terminal > /dev/null; then
        gnome-terminal -- bash "$0"
        exit 0
    elif command -v xterm > /dev/null; then
        xterm -e bash "$0"
        exit 0
    fi
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Setting up game environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "🔧 Checking dependencies..."
pip install pygame colorama > /dev/null 2>&1

# Launch game in current terminal (since we handled new terminal above)
echo "🎵 Starting game with music support..."
python generative_zork_like.py

# Keep window open after game ends
echo ""
echo "Game ended. Press Enter to close..."
read