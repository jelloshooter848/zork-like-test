!pip -q install anthropic
import os, getpass
os.environ["ANTHROPIC_API_KEY"] = "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"

# generative_zork_like_claude_shop_combat.py
"""
Claude-only text adventure with:
- Gold + shop + buy (start with 15 gold; buy 'rusty_sword' from blacksmith)
- Turn-based cave combat (Cave Beast ambushes in hidden_cave)
- Quest completion + 'THE END' when you take the gem

Key loading order:
  1) ANTHROPIC_API_KEY env var
  2) ./anthropic.key (text file next to this script)
  3) ~/.anthropic/anthropic.key

Commands (non-combat):
  look / l
  go <place>                 (e.g., go forest_path  or  go forest path)
  talk to <npc> <text>
  ask <npc> about <topic>
  shop
  buy <item>
  take <item> / drop <item>
  inventory / i
  stats
  quit

Commands (while in combat):
  attack
  defend
  flee
"""

import os, random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------- Key loading ----------
def load_anthropic_key() -> str:
    k = os.getenv("ANTHROPIC_API_KEY")
    if k: return k.strip()
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        p = os.path.join(here, "anthropic.key")
        if os.path.isfile(p): return open(p, "r", encoding="utf-8").read().strip()
    except Exception:
        pass
    try:
        p = os.path.expanduser("~/.anthropic/anthropic.key")
        if os.path.isfile(p): return open(p, "r", encoding="utf-8").read().strip()
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
            description="Village Square — smithy smoke curls into the sky. A forest path leads north.",
            exits=["blacksmith_shop","forest_path"],
            npcs=["blacksmith"]
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
            exits=["village_square","hidden_cave"]
        ),
        "hidden_cave": Location(
            key="hidden_cave",
            description="Hidden Cave — your footsteps echo; the air is cool and still.",
            exits=["forest_path"]
        ),
    }
    npcs = {
        "blacksmith": NPC(
            key="blacksmith",
            name="Rogan the Blacksmith",
            personality="Gruff but helpful, secretly fond of gossip.",
            memory=["Met the player in the village square.","Heard rumors of a lost gem in the cave."]
        )
    }
    player = Player(
        location="village_square",
        inventory=[],                    # start with no sword
        quests={"find_the_gem":"not_started"},
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
                hp=25,
                attack_min=2,
                attack_max=5
            )
            w.flags["in_combat"] = True
            loc.visited = True
            return (loc.description + 
                    "\nA Cave Beast lunges from the shadows! You are in combat."
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
    w.player.location = dest_key
    return describe_location(w)

def take_item(w: World, item: str) -> str:
    if w.flags.get("in_combat"):
        return "No time to snatch items mid-fight!"
    loc = w.locations[w.player.location]
    if item not in loc.items: return f"You don't see a '{item}' here."
    loc.items.remove(item)
    w.player.inventory.append(item)
    if item == "glimmering_gem" and w.player.quests.get("find_the_gem") != "completed":
        w.player.quests["find_the_gem"] = "completed"
        return f"You take the {item}.\nQuest complete! You return to the village as a hero. THE END."
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
    base = random.randint(2, 4)
    if "rusty_sword" in w.player.inventory:
        base += 2
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
    mdmg = max(0, monster_attack_damage(mon) - 2)  # reduced damage while defending
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
    if npc_key == "blacksmith" and any(k in text.lower() for k in ("gem","cave")):
        if w.player.quests.get("find_the_gem") == "not_started":
            w.player.quests["find_the_gem"] = "started"
            npc.memory.append("Mentioned rumors of a gem in the cave.")
            return out + "\n(New quest started: Find the Gem)"
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

    # inventory / stats
    if low in ("inventory","inv","i"): return inventory(w)
    if low == "stats": return stats(w)

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
        if parts[1] == "to":
            npc_key = parts[2]
            text = s.split(parts[2],1)[1]
        else:
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
    print("Welcome to the Generative Zork-like (Claude, shop, combat).")
    print("Type 'help' for commands. Type 'quit' to exit.\n")
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
