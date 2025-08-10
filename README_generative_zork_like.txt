
Generative Zork-like Prototype
==============================

Run interactively:
    source venv/bin/activate
    python generative_zork_like.py

Core ideas:
- Structured world state + NPC memories
- Replace `llm_npc_reply` with a real LLM call to make dialogue fully generative
- Dynamic content seed on first visit (e.g., cave spawns goblin + gem)
- Save/Load via JSON

Basic Commands (non-combat):
  look
  go <place>                 (e.g., go forest_path  or  go forest path)
  talk to <npc> <text>
  ask <npc> about <topic>
  shop
  buy <item>
  take <item> / drop <item>
  inventory
  stats
  quit

Commands (while in combat):
  attack
  defend
  flee