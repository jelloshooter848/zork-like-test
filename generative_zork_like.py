# generative_zork_like.py
"""
Claude-only text adventure with:
- Gold + shop + buy (start with 15 gold; buy 'rusty_sword')
- Turn-based cave combat (Cave Beast ambush on first cave entry)
- Quest completion + 'THE END' when you take the gem

API key loading order:
  1) ANTHROPIC_API_KEY env var
  2) ./secrets/anthropic.key
  3) ~/.anthropic/anthropic.key

Run:
  # recommended: use a virtual environment
  python3 -m venv venv
  source venv/bin/activate
  pip install anthropic
  mkdir -p secrets
  echo "YOUR-ANTHROPIC-KEY" > secrets/anthropic.key

  python generative_zork_like.py
"""

import os
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------- API key loading ----------
def load_anthropic_key() -> str:
    """
    Returns the Anthropic API key as a string, or '' if not found.
    Priority:
      1) ANTHROPIC_API_KEY environment variable
      2) ./secrets/anthropic.key (next to this script)
      3) ~/.anthropic/anthropic.key
    """
    # 1) env var
    k = os.getenv("ANTHROPIC_API_KEY")
    if k:
        return k.strip()

    # 2) ./secrets/anthropic.key (preferred local path)
    try:
        p = Path(__file__).parent / "secrets" / "anthropic.key"
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass

    # 3) ~/.anthropic/anthropic.key (home fallback)
    try:
        p = Path.home() / ".anthropic" / "anthropic.key"
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass

    return ""

# ---------- Data models ----------
@dataclass
class NPC:
    key: str
    name: str
    personality: str
    memory: List[str] = field(default_factory=list)

@dataclass
class Location:
    key: str
    description: str
    exits: List[str]
    npcs: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    visited: bool = False

@dataclass
class Player:
    location: str
    inventory: List[str] = field(default_factory=list)
    quests: Dict[str, str] = field(default_factory=dict)
    gold: int = 0
    hp: int = 20
    max_hp: int = 20

@dataclass
class Monster:
    key: str
    name: str
    hp: int
    attack_min: int
    attack_max: int

@dataclass
class World:
    player: Player
    locations: Dict[str, Location]
    npcs: Dict[str, NPC]
    flags: Dict[str, bool] = field(default_factory=dict)
    monster: Optional[Monster] = None     # active monster (in combat)

# ---------- Shop ----------
SHOP = {
    "blacksmith": {
        "rusty_sword": 10,
    }
}

# ---------- Build world ----------
def build_world() -> World:
    locations = {
        "village_square": Location(
            key="village_square",
            description="Village Square — smithy smoke curls into the sky. A forest path leads north. An ancient tower looms to the east.",
            exits=["blacksmith_shop","forest_path","elder_hut","sealed_tower","healer_tent"]
        ),
        "blacksmith_shop": Location(
            key="blacksmith_shop",
            description="Blacksmith Shop — heat and hammering. Tools line the walls.",
            exits=["village_square"],
            npcs=["blacksmith"]
        ),
        "forest_path": Location(
            key="forest_path",
            description="Forest Path — tall pines, damp earth. A narrow track disappears into darker woods.",
            exits=["village_square","hidden_cave","iron_mine"]
        ),
        "iron_mine": Location(
            key="iron_mine",
            description="Iron Mine — abandoned shafts echo with your footsteps. Rusty ore glints in the dim light.",
            exits=["forest_path"],
            items=["iron_ore"]
        ),
        "healer_tent": Location(
            key="healer_tent",
            description="Healer's Tent — soft candlelight illuminates shelves of herbs and potions. The scent of healing oils fills the air.",
            exits=["village_square"],
            npcs=["healer"]
        ),
        "elder_hut": Location(
            key="elder_hut",
            description="Elder's Hut — a modest dwelling filled with ancient books and herbs. The Elder lies pale in bed.",
            exits=["village_square"],
            npcs=["elder"]
        ),
        "hidden_cave": Location(
            key="hidden_cave",
            description="Hidden Cave — your footsteps echo; the air is cool and still.",
            exits=["forest_path","deep_ruins"]
        ),
        "deep_ruins": Location(
            key="deep_ruins",
            description="Deep Ruins — ancient stone corridors carved with mysterious symbols. The air hums with old magic.",
            exits=["hidden_cave"],
            items=["ancient_scroll"]
        ),
        "sealed_tower": Location(
            key="sealed_tower",
            description="Sealed Tower — a massive door blocks your way, covered in arcane locks. Beyond lies untold treasure.",
            exits=["village_square"],
        ),
    }
    npcs = {
        "blacksmith": NPC(
            key="blacksmith",
            name="Rogan the Blacksmith",
            personality="Gruff but helpful, secretly fond of gossip.",
            memory=["Met the player in the village square.","Heard rumors of a lost gem in the cave."]
        ),
        "elder": NPC(
            key="elder",
            name="Elder Theron",
            personality="Wise but weakened by a mysterious curse. Speaks in riddles and ancient wisdom.",
            memory=["Has been cursed for weeks, growing weaker.","Knows ancient magic and village history."]
        ),
        "healer": NPC(
            key="healer",
            name="Mira the Healer",
            personality="Kind and gentle, devoted to helping wounded adventurers. Charges fair prices for healing.",
            memory=["Runs the village healing tent.","Knows herbal remedies and basic healing magic."]
        )
    }
    player = Player(
        location="village_square",
        inventory=[],                    # start with no sword
        quests={
            "prove_worth": "not_started",        # Quest 1: Get iron ore for blacksmith
            "clear_cave": "not_started",         # Quest 2: Defeat Cave Beast, get gem
            "heal_elder": "not_started",         # Quest 3: Trade gem to heal elder
            "retrieve_scroll": "not_started",    # Quest 4: Get ancient scroll from ruins
            "forge_key": "not_started",          # Quest 5: Get materials, forge master key
            "final_treasure": "not_started"      # Quest 6: Use key to claim treasure
        },
        gold=15,
        hp=20, max_hp=20
    )
    return World(player=player, locations=locations, npcs=npcs, flags={})

# ---------- Engine helpers ----------
def describe_location(w: World) -> str:
    loc = w.locations[w.player.location]
    if not loc.visited:
        if loc.key == "hidden_cave" and not w.flags.get("cave_seeded"):
            # seed gem + start combat
            if "glimmering_gem" not in loc.items:
                loc.items.append("glimmering_gem")
            w.flags["cave_seeded"] = True
            # spawn monster on first entry
            w.monster = Monster(
                key="cave_beast",
                name="Cave Beast",
                hp=25,             # tweak difficulty here (HP)
                attack_min=2,      # min damage
                attack_max=5       # max damage
            )
            w.flags["in_combat"] = True
            loc.visited = True
            return (loc.description +
                    "\nA Cave Beast lunges from the shadows! You are in combat."
                    "\nCommands: attack, defend, flee")
        elif loc.key == "deep_ruins" and not w.flags.get("ruins_seeded"):
            # spawn tougher monster in ruins
            w.flags["ruins_seeded"] = True
            if "broad_sword" not in w.player.inventory:
                loc.visited = True
                return (loc.description + 
                        "\nAn Ancient Guardian blocks your path to the scroll! Its stone armor looks impervious to weak weapons. You need a stronger blade to face this foe."
                        "\nYou retreat wisely.")
            w.monster = Monster(
                key="ancient_guardian",
                name="Ancient Guardian",
                hp=35,             # much tougher - needs broad sword
                attack_min=4,
                attack_max=8
            )
            w.flags["in_combat"] = True
            loc.visited = True
            return (loc.description +
                    "\nAn Ancient Guardian awakens from its slumber! Your broad sword gleams as it senses the worthy foe. You are in combat."
                    "\nCommands: attack, defend, flee")
        loc.visited = True

    lines = [loc.description]
    if loc.exits: lines.append("Exits: " + ", ".join(e.replace("_"," ") for e in loc.exits))
    if loc.npcs: lines.append("You see: " + ", ".join(w.npcs[n].name for n in loc.npcs))
    if loc.items: lines.append("On the ground: " + ", ".join(loc.items))
    if w.flags.get("in_combat"):
        lines.append(f"🗡 In combat with {w.monster.name}! (HP {w.monster.hp})")
    return "\n".join(lines)

def move_player(w: World, dest_key: str) -> str:
    if w.flags.get("in_combat"):
        return "You can't move while in combat! Try: attack, defend, or flee."
    cur = w.locations[w.player.location]
    if dest_key not in cur.exits:
        return "You can't go that way."
    
    # Special case: sealed tower requires master key
    if dest_key == "sealed_tower":
        if "master_key" not in w.player.inventory:
            return "The tower door is sealed with arcane locks. You need a special key to enter."
        elif w.player.quests.get("final_treasure") == "started":
            w.player.quests["final_treasure"] = "completed"
            return "The master key glows as you approach! The seals dissolve and the tower door swings open. Inside, you find an ancient treasure vault filled with gold and magical artifacts! You have completed your hero's journey! THE END."
    
    w.player.location = dest_key
    return describe_location(w)

def take_item(w: World, item: str) -> str:
    if w.flags.get("in_combat"):
        return "No time to snatch items mid-fight!"
    loc = w.locations[w.player.location]
    if item not in loc.items: return f"You don't see a '{item}' here."
    loc.items.remove(item)
    w.player.inventory.append(item)
    if item == "glimmering_gem" and w.player.quests.get("clear_cave") != "completed":
        w.player.quests["clear_cave"] = "completed"
        return f"You take the {item}. The gem pulses with mysterious energy. Perhaps Elder Theron knows its purpose."
    if item == "iron_ore" and w.player.quests.get("prove_worth") != "completed":
        w.player.quests["prove_worth"] = "completed"
        return f"You take the {item}. This should prove your worth to the blacksmith."
    if item == "ancient_scroll" and w.player.quests.get("retrieve_scroll") != "completed":
        w.player.quests["retrieve_scroll"] = "completed"
        return f"You take the {item}. Ancient runes cover its surface - the blacksmith might understand these."
    return f"You take the {item}."

def drop_item(w: World, item: str) -> str:
    if w.flags.get("in_combat"):
        return "Not wise to drop things mid-battle."
    if item not in w.player.inventory: return f"You're not carrying a '{item}'."
    w.player.inventory.remove(item)
    w.locations[w.player.location].items.append(item)
    return f"You drop the {item}."

def inventory(w: World) -> str:
    inv = ", ".join(w.player.inventory) if w.player.inventory else "nothing"
    return f"You are carrying: {inv}\nGold: {w.player.gold}"

def stats(w: World) -> str:
    return f"HP: {w.player.hp}/{w.player.max_hp}" + (f" | Foe: {w.monster.name} HP {w.monster.hp}" if w.flags.get("in_combat") else "")

def quests(w: World) -> str:
    lines = ["Quest Status:"]
    quest_names = {
        "prove_worth": "1. Prove Your Worth (Get iron ore, forge broad sword)",
        "clear_cave": "2. Clear the Cave (Defeat Cave Beast, get gem)", 
        "heal_elder": "3. Heal the Elder (Trade gem for amulet)",
        "retrieve_scroll": "4. Retrieve the Scroll (Need broad sword for Ancient Guardian)",
        "forge_key": "5. Forge the Key (Trade scroll for master key)",
        "final_treasure": "6. Claim the Ancient Treasure (Use key on sealed tower)"
    }
    for quest_key, quest_name in quest_names.items():
        status = w.player.quests.get(quest_key, "not_started")
        if status == "completed":
            lines.append(f"  ✓ {quest_name}")
        elif status == "started":
            lines.append(f"  → {quest_name} (Active)")
        else:
            lines.append(f"  - {quest_name}")
    return "\n".join(lines)

# ---------- Shop ----------
def show_shop(w: World) -> str:
    if w.flags.get("in_combat"): return "Busy fighting!"
    loc = w.locations[w.player.location]
    if "blacksmith" not in loc.npcs:
        return "There's no shop here."
    stock = SHOP.get("blacksmith", {})
    if not stock: return "The shop is closed."
    lines = ["For sale:"]
    for item, price in stock.items():
        lines.append(f"  {item} — {price} gold")
    return "\n".join(lines)

def buy_item(w: World, npc_key: str, item: str) -> str:
    if w.flags.get("in_combat"): return "Finish the fight first!"
    loc = w.locations[w.player.location]
    if npc_key not in loc.npcs:
        return f"There's no one named '{npc_key}' here."
    
    stock = SHOP.get(npc_key, {})
    if item not in stock:
        return f"'{item}' isn't for sale."
    price = stock[item]
    if w.player.gold < price:
        return f"You don't have enough gold (need {price})."
    
    w.player.gold -= price
    w.player.inventory.append(item)
    w.npcs[npc_key].memory.append(f"Sold {item} to player for {price} gold at {w.player.location}")
    return f"You buy the {item} for {price} gold."

# ---------- Combat ----------
def player_attack_damage(w: World) -> int:
    base = random.randint(2, 4)  # adjust to tune player damage
    if "broad_sword" in w.player.inventory:
        base += 8                 # broad sword gives much bigger bonus
    elif "rusty_sword" in w.player.inventory:
        base += 2                 # rusty sword gives smaller bonus
    return base

def monster_attack_damage(mon: Monster) -> int:
    return random.randint(mon.attack_min, mon.attack_max)

def do_attack(w: World) -> str:
    if not w.flags.get("in_combat"): return "There's nothing to attack."
    mon = w.monster
    dmg = player_attack_damage(w)
    mon.hp -= dmg
    lines = [f"You strike the {mon.name} for {dmg} damage. (Foe HP {max(mon.hp,0)})"]
    if mon.hp <= 0:
        w.flags["in_combat"] = False
        w.monster = None
        lines.append(f"The {mon.name} collapses. You are victorious!")
        return "\n".join(lines)
    # monster turn
    mdmg = monster_attack_damage(mon)
    w.player.hp -= mdmg
    lines.append(f"The {mon.name} hits you for {mdmg}. (Your HP {max(w.player.hp,0)})")
    if w.player.hp <= 0:
        lines.append("You fall to the ground. Darkness closes in. GAME OVER.")
        w.flags["in_combat"] = False
    return "\n".join(lines)

def do_defend(w: World) -> str:
    if not w.flags.get("in_combat"): return "You're not in combat."
    mon = w.monster
    mdmg = max(0, monster_attack_damage(mon) - 2)  # defending reduces damage by 2 (tune here)
    w.player.hp -= mdmg
    out = f"You brace yourself and reduce the blow. You take {mdmg}. (Your HP {max(w.player.hp,0)})"
    if w.player.hp <= 0:
        out += "\nYou collapse. GAME OVER."
        w.flags["in_combat"] = False
    return out

def do_flee(w: World) -> str:
    if not w.flags.get("in_combat"): return "You're not in combat."
    # 60% success to flee to forest_path
    if random.random() < 0.6:
        w.flags["in_combat"] = False
        w.monster = None
        w.player.location = "forest_path"
        return "You sprint for the exit and escape to the forest path!\n" + describe_location(w)
    # fail: take a hit
    mon = w.monster
    mdmg = monster_attack_damage(mon)
    w.player.hp -= mdmg
    out = f"You try to flee but stumble! The {mon.name} hits you for {mdmg}. (Your HP {max(w.player.hp,0)})"
    if w.player.hp <= 0:
        out += "\nYou collapse. GAME OVER."
        w.flags["in_combat"] = False
    return out

# ---------- Claude NPC ----------
def npc_reply_claude(npc: NPC, player_text: str, w: World) -> str:
    if w.flags.get("in_combat"):
        return f"{npc.name} shouts over the clash, 'Focus on the fight!'"
    api_key = load_anthropic_key()
    if not api_key:
        # Silent fallback if no key found
        return f"{npc.name} shrugs. '{player_text.strip().capitalize()}… right. Keep your wits.'"
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    loc = w.locations[w.player.location]
    recent = " | ".join(npc.memory[-3:]) if npc.memory else "None"
    system = ("You are an NPC in a text adventure. Stay in character. "
              "Reply in ≤60 words. Do NOT change game state, give items, or move the player.")
    persona = (f"Character: {npc.name}\nPersonality: {npc.personality}\n"
               f"Location: {loc.key} — {loc.description}\nRecent memories: {recent}")
    try:
        resp = client.messages.create(
            model=os.getenv("CLAUDE_MODEL","claude-3-haiku-20240307"),
            system=system,
            max_tokens=120,
            temperature=0.6,
            messages=[
                {"role":"user","content":persona},
                {"role":"user","content":f"Player says: {player_text}"},
            ],
        )
        parts = [b.text for b in resp.content if hasattr(b,"text")]
        text = " ".join(parts).strip() if parts else ""
        return text or f"{npc.name} nods. 'Fair enough.'"
    except Exception:
        return f"{npc.name} frowns. 'Can't talk right now.'"

def talk_to(w: World, npc_key: str, text: str) -> str:
    if w.flags.get("in_combat"):
        return "No time to chat—you're in a fight!"
    loc = w.locations[w.player.location]
    if npc_key not in loc.npcs: return f"There's no one named '{npc_key}' here."
    npc = w.npcs[npc_key]
    npc.memory.append(f"Player said: {text.strip()} at {w.player.location}")
    out = npc_reply_claude(npc, text, w)
    
    # Quest interactions with blacksmith
    if npc_key == "blacksmith":
        # Give iron ore to get broad sword
        if "iron_ore" in w.player.inventory and any(k in text.lower() for k in ("ore", "iron", "forge", "sword", "weapon", "craft", "make")):
            w.player.inventory.remove("iron_ore")
            w.player.inventory.append("broad_sword")
            w.player.quests["prove_worth"] = "completed"
            npc.memory.append("Forged broad sword from iron ore for player.")
            return "The blacksmith's eyes light up as he examines the ore. 'Fine quality iron! Let me forge you a proper weapon.' He works the metal with expert skill, creating a gleaming broad sword. \n(Quest completed: Prove Your Worth) \n(Received: Broad Sword - A superior weapon!)"
        # Start first quest
        elif w.player.quests.get("prove_worth") == "not_started" and any(k in text.lower() for k in ("work", "help", "sword", "weapon")):
            w.player.quests["prove_worth"] = "started"
            npc.memory.append("Asked player to prove their worth by bringing iron ore.")
            return out + "\n(New quest started: Prove Your Worth - Get iron ore from the mine)"
        # Start cave quest after buying sword
        elif "rusty_sword" in w.player.inventory and w.player.quests.get("clear_cave") == "not_started" and any(k in text.lower() for k in ("gem","cave","danger")):
            w.player.quests["clear_cave"] = "started"
            npc.memory.append("Mentioned rumors of a gem in the cave.")
            return out + "\n(New quest started: Clear the Cave - Find the shimmering gem)"
        # Forge key quest
        elif "ancient_scroll" in w.player.inventory and w.player.quests.get("forge_key") == "not_started" and any(k in text.lower() for k in ("scroll", "runes", "forge", "key")):
            w.player.inventory.remove("ancient_scroll")
            w.player.inventory.append("master_key") 
            w.player.quests["forge_key"] = "completed"
            w.player.quests["final_treasure"] = "started"
            npc.memory.append("Forged master key from ancient scroll for player.")
            return "The blacksmith studies the ancient runes carefully. 'Aye, I know these symbols! This speaks of a master key.' He works for hours at his forge, creating an ornate key that hums with power. \n(Quest completed: Forge the Key) \n(New quest started: Claim the Ancient Treasure - Use the key on the sealed tower!)"
    
    # Quest interactions with healer
    elif npc_key == "healer":
        # Healing service
        if any(k in text.lower() for k in ("heal", "help", "hurt", "wounded", "hp", "health", "potion")):
            if w.player.hp >= w.player.max_hp:
                return out + "\n'You look perfectly healthy to me, dear.'"
            elif w.player.gold >= 5:
                w.player.gold -= 5
                w.player.hp = w.player.max_hp
                npc.memory.append("Healed the player for 5 gold.")
                return out + f"\n'Let me tend to those wounds.' Mira's magic flows through you, restoring your health! \n(Fully healed for 5 gold. HP: {w.player.hp}/{w.player.max_hp})"
            else:
                return out + "\n'I'd love to help, but healing costs 5 gold. Come back when you have enough.'"
    
    # Quest interactions with elder
    elif npc_key == "elder":
        # Heal elder quest
        if "glimmering_gem" in w.player.inventory and w.player.quests.get("heal_elder") == "not_started":
            w.player.quests["heal_elder"] = "started"
            npc.memory.append("Player has the gem that could break the curse.")
            return out + "\n(New quest started: Heal the Elder - The gem might break his curse)"
        # Give gem to heal elder
        elif w.player.quests.get("heal_elder") == "started" and "glimmering_gem" in w.player.inventory and any(k in text.lower() for k in ("heal", "gem", "curse", "help")):
            w.player.inventory.remove("glimmering_gem")
            w.player.inventory.append("magical_amulet")
            w.player.max_hp += 5
            w.player.hp += 5  # also heal current HP
            w.player.quests["heal_elder"] = "completed"
            w.player.quests["retrieve_scroll"] = "started"
            npc.memory.append("Healed by the gem, gave magical amulet to player.")
            return "Elder Theron's color returns as the gem's power breaks his curse! 'Take this amulet, brave one. Now seek the ancient scroll in the deep ruins beyond the cave.' \n(Quest completed: Heal the Elder) \n(New quest started: Retrieve the Scroll) \n(+5 Max HP from magical amulet!)"
    
    return out

# ---------- Parser ----------
HELP = (
"Commands:\n"
"  look / l\n"
"  go <place>\n"
"  talk to <npc> <text>\n"
"  ask <npc> about <topic>\n"
"  shop\n"
"  buy <item>\n"
"  take <item> / drop <item>\n"
"  inventory / i\n"
"  stats\n"
"  quests\n"
"  quit\n"
"While in combat: attack, defend, flee"
)

def parse_and_exec(w: World, raw: str) -> str:
    s = raw.strip()
    if not s: return "Say or do something."
    low = s.lower()

    # combat-only commands
    if w.flags.get("in_combat"):
        if low == "attack": return do_attack(w)
        if low == "defend": return do_defend(w)
        if low == "flee":   return do_flee(w)
        if low in ("look","l"): return describe_location(w)
        if low in ("inventory","inv","i","stats"): return stats(w)
        return "You're in combat! Try: attack, defend, or flee."

    # movement
    if low.startswith(("go ","move ","walk ")):
        target = low.split(maxsplit=1)[1].replace(" ","_")
        return move_player(w, target)

    # look
    if low in ("look","l"): return describe_location(w)

    # inventory / stats / quests
    if low in ("inventory","inv","i"): return inventory(w)
    if low == "stats": return stats(w)
    if low in ("quests","quest","q"): return quests(w)

    # take / drop
    if low.startswith("take "): return take_item(w, s.split(" ",1)[1].strip().replace(" ","_"))
    if low.startswith("drop "): return drop_item(w, s.split(" ",1)[1].strip().replace(" ","_"))

    # shop / buy
    if low == "shop": return show_shop(w)
    if low.startswith("buy "):
        item = s.split(" ",1)[1].strip().replace(" ","_")
        return buy_item(w, "blacksmith", item)

    # talk
    if low.startswith(("talk to ","talk ")):
        parts = low.split()
        if len(parts) >= 2 and parts[1] == "to":
            if len(parts) < 3:
                return "Talk to whom?"
            npc_key = parts[2]
            text = s.split(parts[2],1)[1]
        else:
            if len(parts) < 2:
                return "Talk to whom?"
            npc_key = parts[1]
            text = s.split(parts[1],1)[1]
        return talk_to(w, npc_key, text.strip() or "Hello.")

    # ask
    if low.startswith("ask "):
        parts = low.split()
        if len(parts)>=4 and parts[2]=="about":
            npc_key = parts[1]
            topic = s.split("about",1)[1].strip()
            return talk_to(w, npc_key, f"Tell me about {topic}.")
        return "Try: ask <npc> about <topic>."

    # quit
    if low in ("quit","exit"): return "__QUIT__"

    # name-first talk
    first = low.split()[0]
    if first in w.npcs and first in w.locations[w.player.location].npcs:
        return talk_to(w, first, s[len(first):].strip())

    return "I don't understand. Type 'help' for commands."

# ---------- REPL ----------
def repl():
    w = build_world()
    # one-time note if key missing (we'll fall back to stub NPC lines)
    if not load_anthropic_key():
        print("[warn] No Anthropic API key found (using offline stub replies).")
        print("       Set ANTHROPIC_API_KEY or create ./secrets/anthropic.key\n")

    print("=" * 60)
    print("WELCOME TO THE VILLAGE OF THERON")
    print("=" * 60)
    print("You are a wandering adventurer who has arrived in this small village.")
    print("The locals speak of ancient treasures and growing dangers.")
    print("Elder Theron lies cursed and weak, while the blacksmith seeks worthy")
    print("heroes. An ominous sealed tower looms over the village square.")
    print("\nYour journey begins now. Seek work, prove yourself, and uncover")
    print("the mysteries that await. Talk to the villagers to learn more.")
    print("\nType 'help' for commands, 'quests' to track progress, or 'quit' to exit.")
    print("=" * 60)
    print()
    print(describe_location(w))
    while True:
        try:
            raw = input("> ")
        except EOFError:
            print("\nGoodbye."); break
        if raw.strip().lower() in ("help","h","?"):
            print(HELP); continue
        out = parse_and_exec(w, raw)
        if out == "__QUIT__":
            print("Goodbye."); break
        print(out)

if __name__ == "__main__":
    repl()
