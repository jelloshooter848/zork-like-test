@echo off
echo Starting Zork-Like Game...
wsl bash -c "cd /home/lando/projects/zork-like-test && source venv/bin/activate && python generative_zork_like.py"
pause