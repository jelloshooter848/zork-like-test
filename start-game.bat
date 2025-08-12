@echo off
echo Starting Zork-Like Game...
wsl bash -c "cd \"$(wslpath '%~dp0')\" && source venv/bin/activate && python generative_zork_like.py"
pause