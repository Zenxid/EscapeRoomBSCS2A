"""
game_data.py — Vault Zero room/puzzle/item definitions
Language: Python  |  Loaded by: game_engine.py
Also written to quests.json for the Lua layer to read
"""
import json, os

ROOMS = {
    "storage": {
        "id": "storage", "name": "Storage Room — Level B2",
        "db_indicator": "arena.db | rooms.json | inventory.csv",
        "desc": [
            "A concrete storage room. Industrial shelving lines the west wall. "
            "A workbench dominates the centre. Filing cabinet in the northeast corner.",
            "The fluorescent light flickers. A steel door to the north — locked. "
            "A ventilation grate in the floor.",
        ],
        "look": (
            "West: metal shelving with a toolbox (3-digit lock), coil of rope, maintenance log.\n"
            "Centre: workbench with scattered papers and a sticky note.\n"
            "NE corner: filing cabinet (4-letter word lock).\n"
            "Floor: ventilation grate — screws look loose.\n"
            "North: steel door (locked). No other exits."
        ),
        "objects": {
            "shelving": "Three shelves. Bottom: toolbox (3-digit combo lock), rope, maintenance log.",
            "toolbox":  "A metal toolbox — 3-digit combo lock. Digits 1, 4, 8 are still visible on the dial.",
            "workbench": "Scattered papers. Circuit diagram. Sticky note: 'override seq: star-circle-diamond'.",
            "papers":   "Circuit diagram: star=2, circle=1, diamond=3. Margin note: 'floor vent key behind panel'.",
            "filing cabinet": "4-drawer cabinet. Top drawer locked with a 4-letter word. Label: 'HVAC MAINTENANCE LOG'.",
            "grate":    "Ventilation grate — FLATHEAD screws. You'd need a flathead screwdriver.",
            "rope":     "About 6 metres of nylon rope. Sturdy.",
            "log":      "Maintenance log. Entry: 'Override panel behind north grate. Word code = name of shaft: VENT'.",
            "door":     "Reinforced steel door. Electronic keypad: LOCKED. Needs a keycard.",
            "light":    "Fluorescent tube flickering: 3 short, 1 long. Three short. One long.",
        },
        "puzzles": {
            "toolbox": {
                "label": "Toolbox combo lock",
                "type": "number", "length": 3,
                "hint": "Digits 1, 4, 8 are visible. What order?\n"
                        "Clue: the maintenance log entry date was the 1st of August (8th month) — 1/4/8? No...\n"
                        "Look at the dial markings — ascending order: 1, 4, 8.",
                "answer": "148",
                "on_solve": {
                    "msg": "The toolbox clicks open! Inside: a FLATHEAD SCREWDRIVER and a note — '2nd digit of safe = 7'.",
                    "items": [{"name": "Flathead Screwdriver", "type": "item", "key": "screwdriver"}],
                    "clues": ["Toolbox note: 2nd digit of safe = 7"],
                },
            },
            "cabinet": {
                "label": "Filing cabinet word lock",
                "type": "text", "length": 4,
                "hint": "Label says HVAC MAINTENANCE LOG. Code is the name of the ventilation shaft.\n"
                        "The maintenance log says: 'sealed shaft B2-V4. Word code = name of shaft: ____'.\n"
                        "The shaft is a HVAC duct. What do ducts carry? Air — through a VENT.",
                "answer": "vent",
                "on_solve": {
                    "msg": "The top drawer slides open! Inside: full maintenance log and a KEYCARD labelled 'B2 ACCESS'.",
                    "items": [{"name": "Keycard B2", "type": "key", "key": "keycard"}],
                    "clues": ["Keycard B2 obtained — opens the north door"],
                },
            },
        },
        "use_interactions": {
            ("screwdriver", "grate"): {
                "msg": "You unscrew the grate with the flathead screwdriver.\n"
                       "Under the grate, taped to the frame: 'Filing cabinet word = VENT'.",
                "clue": "Grate reveal: cabinet combo = VENT",
            },
        },
        "solve_condition": ["toolbox", "cabinet"],
        "exit_key": "keycard",
        "next_room": "lab",
    },

    "lab": {
        "id": "lab", "name": "Research Lab — Level B2",
        "db_indicator": "lab.json | puzzles.csv | clues.csv",
        "desc": [
            "A sterile research laboratory. Long benches with chemical apparatus. "
            "A server rack hums in the corner.",
            "On the whiteboard: a partially erased equation. "
            "A locked specimen cabinet displays coloured vials on the east wall.",
        ],
        "look": (
            "West: lab bench — centrifuge, beakers (labelled 3, 9, 5), one glowing green flask.\n"
            "Centre: whiteboard with equation V = R × I, R=4Ω, I=2A.\n"
            "East wall: specimen cabinet (4-digit lock) with 5 coloured vials.\n"
            "NE corner: server rack with blinking LEDs.\n"
            "North: exit door (4-digit vault code required)."
        ),
        "objects": {
            "lab bench":  "Stainless bench. Beakers etched: 3, 9, 5. Note: 'Sequence = ascending prime filter'.",
            "beakers":    "Beaker 1: 3 (prime ✓)  Beaker 2: 9 (not prime — 3×3)  Beaker 3: 5 (prime ✓). Ascending primes: 3, 5.",
            "whiteboard": "V = R × I. Below (half-erased): R=4Ω, I=2A. Sticky: 'V = first 2 digits of cabinet code'.",
            "specimen cabinet": "Five vials: Red=8, Blue=1, Green=6, Yellow=3, White=0. 4-digit lock.",
            "server rack":      "LED blink pattern: 3 blinks … 6 blinks … repeating. Last 2 digits of cabinet code.",
            "flask":            "Flask 7-ALPHA — glowing green. Label has the number 7. Probably don't drink.",
            "vials":            "R=8, B=1, G=6, Y=3, W=0. The cabinet is still locked.",
            "door":             "Exit door. Panel reads: VAULT CODE REQUIRED — 4 DIGITS.",
        },
        "puzzles": {
            "specimenCabinet": {
                "label": "Specimen cabinet lock",
                "type": "number", "length": 4,
                "hint": "Whiteboard: V = R × I = 4 × 2 = 8. But the sticky says V = first 2 digits.\n"
                        "V=8 but that's only 1 digit. Maybe it's 08?\n"
                        "Server rack blinks: 3 … 6 … → last 2 digits are 3 and 6.\n"
                        "Full code: 0 8 3 6",
                "answer": "0836",
                "on_solve": {
                    "msg": "Cabinet unlocks! Inside: an ACCESS OVERRIDE CHIP.\n"
                           "Lab journal entry: 'Vault 3 code fragment: _9_1 — Hargreaves took the other half.'",
                    "items": [{"name": "Access Override Chip", "type": "key", "key": "chip"}],
                    "clues": ["Lab journal: vault code fragment = _9_1"],
                },
            },
        },
        "use_interactions": {},
        "solve_condition": ["specimenCabinet"],
        "exit_key": "chip",
        "next_room": "server",
    },

    "server": {
        "id": "server", "name": "Server Room — Level B2",
        "db_indicator": "arena.db | config.ini | event.lua",
        "desc": [
            "A cold room humming with server racks. Blue and red LEDs blink in staggered rhythms.",
            "A central terminal glows in the corner — password protected. "
            "A cork board on the wall has pinned notes.",
        ],
        "look": (
            "West wall: Server Rack A — 4 rows (ALPHA green, BETA green, GAMMA red, DELTA green).\n"
            "           Server Rack B — 4 rows (ROW1 green, ROW2 red, ROW3 green, ROW4 green).\n"
            "East corner: admin terminal (password locked).\n"
            "Cork board: several pinned notes.\n"
            "North: vault door (terminal must be unlocked first)."
        ),
        "objects": {
            "rack a":    "4 LED rows: ALPHA=on, BETA=on, GAMMA=off, DELTA=on. Binary 1101 = decimal 13.",
            "rack b":    "4 LED rows: ROW1=on, ROW2=off, ROW3=on, ROW4=on. Binary 1011 = decimal 11.",
            "terminal":  "Login prompt. Sticky note: 'pwd = decimal(RackA) + decimal(RackB)'.",
            "cork board": "Note 1: 'Binary → decimal, remember it.'\n"
                          "Note 2: 'Final vault = override + fragment. Fragment from lab.'\n"
                          "Note 3 (torn): 'My code is _9_1 — fill blanks with override digits.'",
            "wiring panel": "Breakers. One labelled VAULT DOOR LOCK. Note: 'Do not cut power — lockdown.'",
            "door":      "Vault door. Biometric pad AND 4-digit override slot.",
        },
        "puzzles": {
            "terminal": {
                "label": "Admin terminal password",
                "type": "number", "length": 2,
                "hint": "Rack A: 1101 in binary. 1×8 + 1×4 + 0×2 + 1×1 = 13.\n"
                        "Rack B: 1011 in binary. 1×8 + 0×4 + 1×2 + 1×1 = 11.\n"
                        "Password = 13 + 11 = ?",
                "answer": "24",
                "on_solve": {
                    "msg": "Terminal unlocks! Screen reads:\n"
                           "'OVERRIDE CODE: 24'\n"
                           "'Final vault access = override fills blanks in fragment _9_1'\n"
                           "'Vault code = 2941'\n"
                           "A green light blinks above the vault door.",
                    "items": [{"name": "Override Code: 24", "type": "key", "key": "override"}],
                    "clues": ["Override = 24. Final vault code = 2941"],
                },
            },
        },
        "use_interactions": {},
        "solve_condition": ["terminal"],
        "exit_key": "override",
        "next_room": "vault",
    },

    "vault": {
        "id": "vault", "name": "Vault Zero — Classified Storage",
        "db_indicator": "arena.db | vault.db | scores.csv",
        "desc": [
            "You're inside. Vault Zero. Rows of safety deposit boxes line every wall.",
            "In the centre: a single table with a steel briefcase — the objective. "
            "A clock counts down above the door.",
        ],
        "look": (
            "Walls: rows of numbered safety deposit boxes (001–200), all sealed.\n"
            "Centre table: steel briefcase — FINAL 4-DIGIT LOCK.\n"
            "Above door: countdown clock.\n"
            "Cameras: blinking red in every corner."
        ),
        "objects": {
            "briefcase":  "Steel briefcase. Final 4-digit combination lock.",
            "boxes":      "Numbered boxes 001–200. All sealed. Not what you're here for.",
            "camera":     "Security cameras. They will cycle back. You have minutes.",
            "clock":      "The clock is not on your side.",
            "table":      "The briefcase is on it. That's all that matters.",
        },
        "puzzles": {
            "briefcase": {
                "label": "Briefcase final lock",
                "type": "number", "length": 4,
                "hint": "Lab fragment: _9_1\n"
                        "Override from server terminal: 24\n"
                        "Fill the blanks: 2 _ 9 _ → wait, blanks are positions 1 and 3.\n"
                        "_9_1 with override=24: first blank=2, second blank=4 → 2 9 4 1",
                "answer": "2941",
                "on_solve": {
                    "msg": "VAULT ZERO — OPENED.\n\n"
                           "The briefcase springs open. Inside: a hard drive labelled PROJECT ECHO — CLASSIFIED.\n"
                           "A folded note reads:\n"
                           "'If you found this, they were right about you.\n"
                           " Get out before the cameras cycle back.'\n\n"
                           "YOU ESCAPED VAULT ZERO.",
                    "items": [{"name": "PROJECT ECHO Drive", "type": "key", "key": "victory"}],
                    "clues": ["ESCAPED"],
                },
            },
        },
        "use_interactions": {},
        "solve_condition": ["briefcase"],
        "exit_key": None,
        "next_room": None,
    },
}

ROOM_ORDER = ["storage", "lab", "server", "vault"]

def export_quests_json():
    """Write quests.json for the Lua scripting layer to read."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quests.json")
    export = {rid: {"name": r["name"], "puzzles": list(r["puzzles"].keys())} for rid, r in ROOMS.items()}
    with open(path, "w") as f:
        json.dump(export, f, indent=2)
