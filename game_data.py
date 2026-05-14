"""
game_data.py — Vault Zero room/puzzle/item definitions
Language: Python  |  Loaded by: game_engine.py
Rooms   : storage → lab → server → vault → reactor (new)
"""
import json, os

# ── Difficulty settings ───────────────────────────────────────────────────────
# ── XP economy (inflated so ranks feel earned) ───────────────────────────────
# Full easy run  = 500 escape + 17×20 puzzle + 5×30 room  =  990  XP → ~Agent
# Full normal    = 1500 escape + 17×60 puzzle + 5×80 room  = 3,020 XP → ~Breaker/Ghost
# Full hard      = 4000 escape + 17×150 puzzle + 5×200 room = 7,550 XP → ~Specter
# Full nightmare = 10000 escape + 17×400 puzzle + 5×600 room= 19,800 XP → beyond Cipher
# Rank thresholds are also inflated — see RANK_TABLE in main_menu.py

DIFFICULTIES = {
    "easy": {
        "label":       "EASY",
        "desc":        "Full hints shown. 20 minutes. Good for learning the puzzles.",
        "time_limit":  1200,
        "xp_escape":   500,
        "xp_per_puzzle": 20,
        "xp_per_room": 30,
        "hint_level":  "full",
        "color":       "#4a8a4a",
    },
    "normal": {
        "label":       "NORMAL",
        "desc":        "Partial hints. 15 minutes. Balanced XP. Recommended.",
        "time_limit":  900,
        "xp_escape":   1500,
        "xp_per_puzzle": 60,
        "xp_per_room": 80,
        "hint_level":  "partial",
        "color":       "#d4a853",
    },
    "hard": {
        "label":       "HARD",
        "desc":        "Minimal hints. 10 minutes. High XP — figure it out.",
        "time_limit":  600,
        "xp_escape":   4000,
        "xp_per_puzzle": 150,
        "xp_per_room": 200,
        "hint_level":  "minimal",
        "color":       "#aa4a4a",
    },
    "nightmare": {
        "label":       "NIGHTMARE",
        "desc":        "No hints. 7 minutes. Maximum XP. You are alone.",
        "time_limit":  420,
        "xp_escape":   10000,
        "xp_per_puzzle": 400,
        "xp_per_room": 600,
        "hint_level":  "none",
        "color":       "#7a5ab0",
    },
}

DEFAULT_DIFFICULTY = "normal"

def get_difficulty(key):
    return DIFFICULTIES.get(key, DIFFICULTIES[DEFAULT_DIFFICULTY])

def get_hint(puzzle: dict, level: str) -> str:
    """Return the appropriate hint string for the current difficulty level."""
    hints = puzzle.get("hints", {})
    if level == "full":
        return hints.get("full", puzzle.get("hint", "No hint available."))
    if level == "partial":
        return hints.get("partial", hints.get("full", "Think carefully about the clues."))
    if level == "minimal":
        return hints.get("minimal", "Look closer at the room.")
    return "No hints on Nightmare mode. Good luck."


# ── Room definitions ──────────────────────────────────────────────────────────
ROOMS = {

    # ══════════════════════════════════════════════════════════════════════════
    # ROOM 1 — STORAGE
    # Puzzles: toolbox (3-digit), cabinet (word), fusebox (sequence), lockbox (math)
    # ══════════════════════════════════════════════════════════════════════════
    "storage": {
        "id": "storage", "name": "Storage Room — Level B2",
        "db_indicator": "arena.db | rooms.json | inventory.csv",
        "desc": [
            "A concrete storage room. Industrial shelving lines the west wall. "
            "A workbench dominates the centre. Filing cabinet in the northeast corner.",
            "The fluorescent light flickers. A steel door to the north — locked. "
            "A ventilation grate in the floor. A fusebox on the east wall, panel ajar.",
        ],
        "look": (
            "West: metal shelving — toolbox (3-digit lock), coil of rope, maintenance log.\n"
            "Centre: workbench with papers, sticky note, and a small locked lockbox.\n"
            "NE corner: filing cabinet (4-letter word lock).\n"
            "East wall: fusebox — panel ajar, four breakers with symbols.\n"
            "Floor: ventilation grate — flathead screws.\n"
            "North: steel door (keycard locked)."
        ),
        "objects": {
            "shelving":       "Three shelves. Bottom: toolbox (3-digit combo), rope, maintenance log.",
            "toolbox":        "Metal toolbox — 3-digit combo. Only digits 1, 4, 8 remain visible.",
            "workbench":      "Scattered papers. Circuit diagram. Sticky note and a small lockbox bolted to the bench.",
            "papers":         "Circuit diagram with symbols: star=2, circle=1, diamond=3. Margin: 'floor vent key behind panel'.",
            "sticky note":    "The sticky note reads: 'Fusebox sequence = the shape order on the wall chart. Check the poster.'",
            "filing cabinet": "4-drawer cabinet. Top drawer locked — 4-letter word. Label: 'HVAC MAINTENANCE LOG'.",
            "lockbox":        "Small steel lockbox bolted to the workbench. 2-digit combination. Label: 'EMERGENCY SUPPLY'.",
            "fusebox":        "Four breakers labelled with shapes: Triangle(1), Circle(2), Square(3), Star(4). A wall chart nearby shows the sequence: Circle, Triangle, Star, Square.",
            "wall chart":     "Laminated safety chart. At the bottom in red: 'Emergency reset sequence: Circle→Triangle→Star→Square. Numeric: 2-1-4-3'.",
            "grate":          "Ventilation grate — flathead screws. Would need a flathead screwdriver.",
            "rope":           "About 6 metres of nylon rope. Sturdy enough to hold weight.",
            "log":            "Maintenance log. Entry: 'Sealed shaft B2-V4. Word code = name of shaft: VENT'. Last line: 'Lockbox code = breaker count (active only)'.",
            "door":           "Reinforced steel door. Electronic keypad reads LOCKED. Needs a keycard.",
            "light":          "Fluorescent tube flickering: 3 short, 1 long. Could be Morse for S.",
            "poster":         "Safety poster. Emergency reset sequence diagram: Circle(2) → Triangle(1) → Star(4) → Square(3).",
        },
        "puzzles": {
            "toolbox": {
                "label": "Toolbox combo lock",
                "type": "number", "length": 3,
                "hints": {
                    "full":    "Only digits 1, 4, 8 are on the dial. Arrange in ascending order: 1, 4, 8.",
                    "partial": "Three digits are visible on the dial. Think about ascending order.",
                    "minimal": "The dial has three digits. What's the most logical arrangement?",
                },
                "hint": "Digits 1, 4, 8. Ascending order: 1, 4, 8.",
                "answer": "148",
                "on_solve": {
                    "msg": "The toolbox clicks open!\nInside: a FLATHEAD SCREWDRIVER and a note — '2nd digit of lockbox = number of active breakers'.",
                    "items": [{"name": "Flathead Screwdriver", "type": "item", "key": "screwdriver"}],
                    "clues": ["Toolbox: 2nd digit of lockbox = count of active breakers in fusebox"],
                },
            },
            "cabinet": {
                "label": "Filing cabinet word lock",
                "type": "text", "length": 4,
                "hints": {
                    "full":    "The label says HVAC MAINTENANCE LOG. The log mentions 'shaft B2-V4' — word code = name of shaft: VENT.",
                    "partial": "The cabinet label mentions HVAC. The maintenance log has the exact word somewhere inside.",
                    "minimal": "HVAC systems move air. What do they move it through?",
                },
                "hint": "HVAC shaft name. The log says word = name of shaft: VENT.",
                "answer": "vent",
                "on_solve": {
                    "msg": "Top drawer slides open! Inside: the full maintenance log and a KEYCARD labelled 'B2 ACCESS — LEVEL 1'.",
                    "items": [{"name": "Keycard B2", "type": "key", "key": "keycard"}],
                    "clues": ["Keycard B2 obtained — opens the north storage door"],
                },
            },
            "fusebox": {
                "label": "Fusebox reset sequence",
                "type": "number", "length": 4,
                "hints": {
                    "full":    "Wall chart shows: Circle(2)→Triangle(1)→Star(4)→Square(3). Sequence = 2143.",
                    "partial": "The wall chart has the emergency reset order. Match each shape to its number label on the fusebox.",
                    "minimal": "The fusebox and the wall chart are connected. Read both carefully.",
                },
                "hint": "Wall chart: Circle→Triangle→Star→Square = 2→1→4→3.",
                "answer": "2143",
                "on_solve": {
                    "msg": "The fusebox resets with a clunk! A panel behind it swings open.\nInside the panel: a sticky note — 'Lockbox 1st digit = 3. Activated breakers = 3'.",
                    "items": [{"name": "Fusebox Panel Note", "type": "clue", "key": "fusebox_note"}],
                    "clues": ["Fusebox panel: lockbox 1st digit = 3. Active breakers = 3"],
                },
            },
            "lockbox": {
                "label": "Emergency lockbox",
                "type": "number", "length": 2,
                "hints": {
                    "full":    "Fusebox panel note: 1st digit = 3. Toolbox note: 2nd digit = active breakers = 3. Code = 33.",
                    "partial": "Two notes give you the two digits separately. One is in the toolbox, one behind the fusebox panel.",
                    "minimal": "Both digits come from notes hidden in this room. Have you found them all?",
                },
                "hint": "1st digit from fusebox panel note (3). 2nd digit = active breakers (3). Code = 33.",
                "answer": "33",
                "on_solve": {
                    "msg": "The lockbox pops open! Inside: a SECURITY BADGE (Level 2) and a folded map of Level B2.\nThe map shows a room not on any directory — marked only as 'REACTOR'.",
                    "items": [
                        {"name": "Security Badge Lv2", "type": "key",  "key": "badge_lv2"},
                        {"name": "B2 Floor Map",       "type": "clue", "key": "b2_map"},
                    ],
                    "clues": ["B2 map shows a hidden Reactor room — accessible from the vault"],
                },
            },
        },
        "use_interactions": {
            ("screwdriver", "grate"): {
                "msg": "You unscrew the grate. Under it, taped to the frame: 'Filing cabinet word = VENT'.",
                "clue": "Grate: cabinet combo = VENT",
            },
        },
        "solve_condition": ["toolbox", "cabinet", "fusebox", "lockbox"],
        "exit_key": "keycard",
        "next_room": "lab",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ROOM 2 — RESEARCH LAB
    # Puzzles: specimenCabinet (4-digit), centrifuge (sequence), chem_safe (formula)
    # ══════════════════════════════════════════════════════════════════════════
    "lab": {
        "id": "lab", "name": "Research Lab — Level B2",
        "db_indicator": "lab.json | puzzles.csv | clues.csv",
        "desc": [
            "A sterile research laboratory. Long benches with chemical apparatus. "
            "A server rack hums in the corner. A centrifuge sits idle on the bench.",
            "On the whiteboard: a partially erased equation. "
            "A locked specimen cabinet displays coloured vials. A wall-mounted chemical safe.",
        ],
        "look": (
            "West: lab bench — centrifuge (sequence lock), beakers labelled 3/9/5, glowing green flask.\n"
            "Centre: whiteboard (V=R×I equation) and a periodic table poster.\n"
            "East wall: specimen cabinet (4-digit lock), chemical safe (formula lock).\n"
            "NE corner: server rack with blinking LEDs.\n"
            "North: exit door — access chip required."
        ),
        "objects": {
            "lab bench":        "Stainless bench. Centrifuge with a sequence lock. Beakers: 3, 9, 5. Note: 'Sequence = ascending prime filter'.",
            "centrifuge":       "A centrifuge with a 3-digit sequence lock. A label: 'Load order = prime vials only, ascending'. A sticky: 'Prime beakers go in slots 1-2-3 in ascending order'.",
            "beakers":          "Beaker A: 3 (prime ✓)  Beaker B: 9 (not prime — 3×3 ✗)  Beaker C: 5 (prime ✓). Ascending primes: 3 then 5.",
            "whiteboard":       "V = R × I. Below (half-erased): R=4Ω, I=2A. Sticky: 'V is the first 2 digits of the cabinet code'.",
            "periodic table":   "Standard periodic table. Someone has circled three elements in red pen: Fe(26), Cu(29), Zn(30). Note below: 'Chemical safe = sum of atomic numbers, mod 100'.",
            "specimen cabinet": "Five vials: Red=8, Blue=1, Green=6, Yellow=3, White=0. 4-digit lock.",
            "chemical safe":    "Wall-mounted steel safe. 2-digit combination. Label: 'REAGENT STORAGE — FORMULA CODE'.",
            "server rack":      "LED blink pattern: 3 blinks … 6 blinks … repeating. Last 2 digits of cabinet code.",
            "flask":            "Flask 7-ALPHA — glowing green. Smells faintly of pine. The number 7 might matter.",
            "vials":            "Five coloured vials: R=8, B=1, G=6, Y=3, W=0. Cabinet still locked.",
            "door":             "Exit door. Panel: ACCESS CHIP REQUIRED. No chip, no exit.",
            "journal":          "Open lab journal on the bench. Entry: 'Centrifuge slot 1=lowest prime, slot 2=next prime. Third slot = slot1+slot2'. Page is dog-eared.",
        },
        "puzzles": {
            "specimenCabinet": {
                "label": "Specimen cabinet lock",
                "type": "number", "length": 4,
                "hints": {
                    "full":    "Whiteboard: V=4×2=8, pad to 2 digits → 08. Server rack blinks 3 then 6 → last 2 digits = 36. Full code: 0836.",
                    "partial": "Whiteboard gives the first 2 digits. Server rack blink pattern gives the last 2.",
                    "minimal": "Two separate clues in the room each give 2 digits of the 4-digit code.",
                },
                "hint": "V=R×I=08 (first 2 digits). Server blinks 3,6 (last 2 digits). Code=0836.",
                "answer": "0836",
                "on_solve": {
                    "msg": "Cabinet unlocks!\nInside: an ACCESS OVERRIDE CHIP.\nLab journal entry: 'Vault 3 code fragment: _9_1 — Hargreaves took the other half.'",
                    "items": [{"name": "Access Override Chip", "type": "key", "key": "chip"}],
                    "clues": ["Lab journal: vault code fragment = _9_1"],
                },
            },
            "centrifuge": {
                "label": "Centrifuge sequence lock",
                "type": "number", "length": 3,
                "hints": {
                    "full":    "Prime beakers ascending: 3 then 5. Slot 3 = slot1 + slot2 = 3+5 = 8. Code = 358.",
                    "partial": "The journal says slots 1 and 2 are the prime beakers in ascending order. Slot 3 is a calculation.",
                    "minimal": "Which beakers are prime? What does the journal say about slot 3?",
                },
                "hint": "Primes ascending: 3, 5. Slot 3 = 3+5 = 8. Sequence = 3, 5, 8.",
                "answer": "358",
                "on_solve": {
                    "msg": "The centrifuge whirrs to life! A hidden drawer pops out from its base.\nInside: a REAGENT KEY CARD and a note — 'Chemical safe: Fe+Cu+Zn atomic numbers, mod 100'.",
                    "items": [{"name": "Reagent Key Card", "type": "item", "key": "reagent_card"}],
                    "clues": ["Chemical safe code = (Fe26 + Cu29 + Zn30) mod 100 = 85"],
                },
            },
            "chemSafe": {
                "label": "Chemical safe formula lock",
                "type": "number", "length": 2,
                "hints": {
                    "full":    "Periodic table: Fe=26, Cu=29, Zn=30. Sum=85. Mod 100 = 85. Code = 85.",
                    "partial": "Three elements are circled on the periodic table. Add their atomic numbers, then apply mod 100.",
                    "minimal": "The periodic table and the centrifuge note are connected.",
                },
                "hint": "Fe(26)+Cu(29)+Zn(30)=85. Mod 100 = 85.",
                "answer": "85",
                "on_solve": {
                    "msg": "The chemical safe swings open!\nInside: a vial labelled COMPOUND X-7 and a data card — 'Reactor coolant override = compound index × prime index = 7×3 = 21'.",
                    "items": [
                        {"name": "Compound X-7",    "type": "item", "key": "compound_x7"},
                        {"name": "Reactor Data Card","type": "clue", "key": "reactor_card"},
                    ],
                    "clues": ["Reactor coolant override = 7×3 = 21 (needed in Reactor room)"],
                },
            },
        },
        "use_interactions": {},
        "solve_condition": ["specimenCabinet", "centrifuge", "chemSafe"],
        "exit_key": "chip",
        "next_room": "server",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ROOM 3 — SERVER ROOM
    # Puzzles: terminal (sum), network_switch (pattern), encrypted_drive (cipher)
    # ══════════════════════════════════════════════════════════════════════════
    "server": {
        "id": "server", "name": "Server Room — Level B2",
        "db_indicator": "arena.db | config.ini | event.lua",
        "desc": [
            "A cold room humming with server racks. Blue and red LEDs blink in staggered rhythms.",
            "A central terminal glows in the corner — password protected. "
            "A network switch panel and an encrypted drive reader sit on the side bench.",
        ],
        "look": (
            "West: Rack A (ALPHA/BETA/GAMMA/DELTA LEDs) and Rack B (ROW1–4 LEDs).\n"
            "Centre bench: network switch panel (8 ports, pattern lock) and an encrypted drive reader.\n"
            "East corner: admin terminal (password locked).\n"
            "Cork board: pinned notes and a cipher key chart.\n"
            "North: vault door (terminal must be unlocked first)."
        ),
        "objects": {
            "rack a":          "4 LED rows: ALPHA=on, BETA=on, GAMMA=off, DELTA=on. Binary: 1101 = decimal 13.",
            "rack b":          "4 LED rows: ROW1=on, ROW2=off, ROW3=on, ROW4=on. Binary: 1011 = decimal 11.",
            "terminal":        "Login prompt. Sticky: 'pwd = decimal(RackA) + decimal(RackB)'.",
            "network switch":  "8-port panel. Ports: ON/OFF/ON/OFF/ON/ON/OFF/ON. Label: 'Active port count = switch code'.",
            "drive reader":    "Encrypted drive reader with a 3-digit cipher lock. A cipher key chart is taped to the side.",
            "cipher chart":    "Chart maps letters to numbers: A=1,B=2...Z=26. A sticky note: 'Drive code = initials of the three server rack labels: Alpha, Beta, Delta'.",
            "cork board":      "Note 1: 'Binary→decimal'. Note 2: 'Final vault = override + fragment _9_1'. Note 3: 'Drive unlocks Reactor access token'.",
            "wiring panel":    "Breakers. VAULT DOOR LOCK breaker is ON. Note: 'Do not cut power — triggers lockdown'.",
            "door":            "Vault door. 4-digit override slot plus biometric pad.",
            "sticky note":     "Taped to the terminal: 'After terminal unlock, check drive reader for Reactor token'.",
        },
        "puzzles": {
            "terminal": {
                "label": "Admin terminal password",
                "type": "number", "length": 2,
                "hints": {
                    "full":    "Rack A: 1101 binary = 13. Rack B: 1011 binary = 11. Password = 13+11 = 24.",
                    "partial": "Convert both rack LED patterns from binary to decimal, then add them.",
                    "minimal": "Binary. Two racks. One password.",
                },
                "hint": "RackA=1101=13, RackB=1011=11. Sum=24.",
                "answer": "24",
                "on_solve": {
                    "msg": "Terminal unlocks!\nScreen: 'OVERRIDE CODE: 24'\n'Final vault = override fills _9_1 → 2941'\nGreen light above vault door.",
                    "items": [{"name": "Override Code: 24", "type": "key", "key": "override"}],
                    "clues": ["Override = 24. Vault code = 2941"],
                },
            },
            "networkSwitch": {
                "label": "Network switch pattern",
                "type": "number", "length": 1,
                "hints": {
                    "full":    "Ports ON/OFF/ON/OFF/ON/ON/OFF/ON = 5 active ports. Switch code = 5.",
                    "partial": "Count the active (ON) ports on the network switch panel.",
                    "minimal": "Count carefully. Each port is either on or off.",
                },
                "hint": "ON/OFF/ON/OFF/ON/ON/OFF/ON = 5 active ports. Code = 5.",
                "answer": "5",
                "on_solve": {
                    "msg": "The switch panel clicks. A locked drawer beneath it opens.\nInside: a USB DRIVE labelled 'REACTOR ACCESS — ENCRYPTED'.",
                    "items": [{"name": "Encrypted USB Drive", "type": "item", "key": "usb_drive"}],
                    "clues": ["USB drive found — needs cipher code from drive reader"],
                },
            },
            "encryptedDrive": {
                "label": "Encrypted drive cipher",
                "type": "number", "length": 3,
                "hints": {
                    "full":    "Cipher chart: A=1, B=2, D=4. Rack labels: Alpha, Beta, Delta → initials A,B,D → 1,2,4. Code = 124.",
                    "partial": "The cipher chart converts letters to numbers. The cork board note says 'initials of the three rack labels'.",
                    "minimal": "Look at the cipher chart and the rack labels. Initials.",
                },
                "hint": "Alpha→A=1, Beta→B=2, Delta→D=4. Code = 124.",
                "answer": "124",
                "on_solve": {
                    "msg": "Drive decrypted!\nScreen shows: 'REACTOR ACCESS TOKEN: 7749'\nA secondary door indicator lights up green — Reactor Core is now accessible from the Vault.",
                    "items": [{"name": "Reactor Access Token", "type": "key", "key": "reactor_token"}],
                    "clues": ["Reactor Access Token: 7749 — use at Reactor Core entrance"],
                },
            },
        },
        "use_interactions": {},
        "solve_condition": ["terminal", "networkSwitch", "encryptedDrive"],
        "exit_key": "override",
        "next_room": "vault",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ROOM 4 — VAULT ZERO
    # Puzzles: briefcase (4-digit), deposit_box (combination), safecracker (sound)
    # ══════════════════════════════════════════════════════════════════════════
    "vault": {
        "id": "vault", "name": "Vault Zero — Classified Storage",
        "db_indicator": "arena.db | vault.db | scores.csv",
        "desc": [
            "You're inside. Vault Zero. Rows of safety deposit boxes line every wall.",
            "In the centre: a steel table with the target briefcase. "
            "A side alcove has a safecracker panel and a marked deposit box. "
            "A sealed door on the east wall is marked REACTOR CORE — RESTRICTED.",
        ],
        "look": (
            "Walls: deposit boxes 001–200. Box 047 has a red tag — unusual.\n"
            "Centre table: steel briefcase (4-digit final lock).\n"
            "Side alcove: safecracker panel (listen for clicks) and a wall dial.\n"
            "East door: REACTOR CORE — needs Reactor Access Token.\n"
            "Cameras blink red. Clock counts down above the main door."
        ),
        "objects": {
            "briefcase":    "Steel briefcase — the objective. 4-digit combination lock.",
            "boxes":        "Deposit boxes 001–200. Box 047 has a red tag and a separate 3-digit combo.",
            "box 047":      "Box 047 — red tag reads 'PRIORITY ACCESS'. 3-digit combo. The tag number is a clue: 0+4+7=11. Box code = digits of sum reversed: 11 → code uses 1,1. Third digit = count of red-tagged boxes (just this one) = 1. Code = 111.",
            "safecracker":  "A mechanical dial with a pointer and a click counter. A note: 'Turn to resistance points. Sequence: first click at 15, second at 32, third at 08. Enter as 6 digits: 153208'.",
            "wall dial":    "The main dial for the safecracker. Markings 00–39. A technician note: 'Resistance at 15, 32, 08 — in that order'.",
            "camera":       "Security cameras sweep every 90 seconds. You have a window.",
            "clock":        "Counting down. Every second matters.",
            "east door":    "REACTOR CORE door. Slot for an access token — 4-digit code.",
            "table":        "Steel table. The briefcase is on it.",
        },
        "puzzles": {
            "briefcase": {
                "label": "Briefcase final lock",
                "type": "number", "length": 4,
                "hints": {
                    "full":    "Lab fragment: _9_1. Override: 24. Fill blanks with override digits: 2_9_1 → 2941.",
                    "partial": "The lab journal gave a code fragment. The server terminal gave an override number. Combine them.",
                    "minimal": "You have two partial codes from earlier rooms. Put them together.",
                },
                "hint": "Fragment _9_1 + override 24 → 2941.",
                "answer": "2941",
                "on_solve": {
                    "msg": "VAULT ZERO — OPENED.\n\nThe briefcase springs open. Inside: PROJECT ECHO — hard drive, classified.\nA note: 'If you found this, they were right about you. Get out before cameras cycle.'\n\nYOU ESCAPED VAULT ZERO.",
                    "items": [{"name": "PROJECT ECHO Drive", "type": "key", "key": "victory"}],
                    "clues": ["PRIMARY OBJECTIVE COMPLETE — Escaped Vault Zero"],
                },
            },
            "depositBox": {
                "label": "Deposit box 047",
                "type": "number", "length": 3,
                "hints": {
                    "full":    "Tag number 047: 0+4+7=11. Reverse=11. Count red boxes=1. Code = 111.",
                    "partial": "The red tag number itself is a clue. Do some math with its digits.",
                    "minimal": "Box 047. The red tag. And how many red-tagged boxes are there?",
                },
                "hint": "0+4+7=11, reversed=11, red box count=1. Code=111.",
                "answer": "111",
                "on_solve": {
                    "msg": "Box 047 opens! Inside: a MASTER KEYCARD and a note — 'Reactor entry panel: token + coolant code. Token from server drive, coolant from lab safe'.",
                    "items": [{"name": "Master Keycard", "type": "key", "key": "master_card"}],
                    "clues": ["Reactor panel needs: Reactor token (from server) + coolant override (from lab = 21)"],
                },
            },
            "safecracker": {
                "label": "Safecracker dial sequence",
                "type": "number", "length": 6,
                "hints": {
                    "full":    "Wall dial note: resistance at 15, then 32, then 08. Enter all three as 6 digits: 153208.",
                    "partial": "The technician note on the wall dial tells you the three resistance points. Enter them in order.",
                    "minimal": "Three numbers. In order. On the dial markings.",
                },
                "hint": "Resistance points: 15, 32, 08 → enter as 153208.",
                "answer": "153208",
                "on_solve": {
                    "msg": "The safecracker panel clicks three times and a hidden wall compartment swings open!\nInside: a BIOMETRIC OVERRIDE FOB — needed for the Reactor Core secondary lock.",
                    "items": [{"name": "Biometric Override Fob", "type": "key", "key": "bio_fob"}],
                    "clues": ["Biometric fob unlocks Reactor Core secondary lock"],
                },
            },
        },
        "use_interactions": {},
        "solve_condition": ["briefcase", "depositBox", "safecracker"],
        "exit_key": None,
        "next_room": "reactor",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ROOM 5 — REACTOR CORE (NEW)
    # Puzzles: entry_panel, coolant_valve, control_rods, meltdown_override
    # Theme: nuclear facility, time pressure, multi-step chain
    # ══════════════════════════════════════════════════════════════════════════
    "reactor": {
        "id": "reactor", "name": "Reactor Core — Level B3",
        "db_indicator": "reactor.db | coolant.csv | override.ini",
        "desc": [
            "A vast circular chamber. The ceiling rises thirty feet above you. "
            "Thick conduit pipes snake along the walls, some leaking steam.",
            "At the centre: the reactor housing — a steel cylinder ten feet across, "
            "humming with controlled fission. Warning lights flash amber. "
            "A meltdown countdown has started: 8 minutes.",
        ],
        "look": (
            "North wall: entry control panel (token + coolant code, 6-digit lock).\n"
            "West: coolant valve array — four valves labelled A/B/C/D, each with a pressure gauge.\n"
            "East: control rod console — 3 rods, each with a position dial (0–9).\n"
            "Centre: reactor housing. Warning: DO NOT APPROACH WITHOUT COOLANT ACTIVE.\n"
            "South: meltdown override terminal — master shutdown, biometric + 4-digit code.\n"
            "Ceiling: radiation warning lights — currently AMBER (elevated)."
        ),
        "objects": {
            "entry panel":     "North wall panel. Two slots: token reader (4-digit) and coolant code (2-digit). A display: 'TOKEN + COOLANT = ACCESS'. Accepts 6 digits total.",
            "coolant valves":  "Four valves: A (pressure 4.2), B (pressure 1.7), C (pressure 8.9), D (pressure 3.1). A placard: 'Target total pressure = 18.0. Adjust until sum equals target'. Current sum = 17.9. Valve B needs one click up (+0.1 increment). Each valve click = +0.1. B needs 1 click.",
            "valve a":         "Valve A — pressure gauge reads 4.2. Target contribution not marked.",
            "valve b":         "Valve B — pressure gauge reads 1.7. Increment button on side. One click = +0.1 bar.",
            "valve c":         "Valve C — pressure gauge reads 8.9. This valve is sealed — do not adjust.",
            "valve d":         "Valve D — pressure gauge reads 3.1. This valve is sealed — do not adjust.",
            "pressure placard":"Placard: 'Total coolant pressure must equal 18.0 bar. Current: 17.9. Valve B increment count = 2nd digit of coolant code. 1st digit = always 2'. Coolant code = 2 followed by B clicks needed.",
            "control rods":    "Three control rods: Rod 1, Rod 2, Rod 3. Each has a dial 0–9. A log book nearby.",
            "rod logbook":     "Log book — last calibration entry: 'Rod 1 = reactor temp / 100 (round down). Rod 2 = Rod1 + 2. Rod 3 = Rod2 - Rod1'. Reactor temp display reads 412°C.",
            "reactor housing": "The reactor cylinder. Status light: AMBER — elevated but stable. A digital display shows 412°C core temperature. DO NOT TOUCH.",
            "temp display":    "Digital display: CORE TEMP 412°C. COOLANT STATUS: INSUFFICIENT. TARGET: 18.0 BAR.",
            "override terminal":"South wall terminal. Label: 'MELTDOWN OVERRIDE — AUTHORISED PERSONNEL ONLY'. Two inputs: biometric fob slot and a 4-digit emergency code.",
            "emergency manual": "Thick binder on the override terminal desk. Page 47 is bookmarked. It reads: 'Emergency shutdown code = Rod1 × Rod2 × Rod3, last 4 digits. If product < 4 digits, pad with leading zeros'.",
            "warning lights":  "Amber warning lights. The placard says: 'AMBER = coolant pressure below target. RED = meltdown imminent. GREEN = stable'.",
            "steam pipes":     "Thick conduit pipes. Several leak steam at the joints. Labels show pressure readings consistent with the valve array.",
        },
        "puzzles": {
            "entryPanel": {
                "label": "Reactor entry panel",
                "type": "number", "length": 6,
                "hints": {
                    "full":    "Token from server drive = 7749. Coolant code: 1st digit=2, B clicks needed=1, so coolant=21. Combined: 774921.",
                    "partial": "You need two codes: the Reactor Access Token (found in server room) and the coolant code (related to valve B pressure adjustment).",
                    "minimal": "Two codes combined. One from the server room. One from the coolant valves.",
                },
                "hint": "Token=7749 (from server USB). Coolant code: 2+B_clicks(1)=21. Entry=774921.",
                "answer": "774921",
                "on_solve": {
                    "msg": "ENTRY GRANTED. The north panel retracts.\nA status screen lights up: 'Coolant pressure: INSUFFICIENT. Activate coolant valves before approaching reactor'.\nWarning lights shift from amber to pulsing.",
                    "items": [],
                    "clues": ["Entry granted — must fix coolant pressure before control rods"],
                },
            },
            "coolantValve": {
                "label": "Coolant valve calibration",
                "type": "number", "length": 2,
                "hints": {
                    "full":    "Current total = 17.9. Target = 18.0. Need +0.1. Valve B: 1 click = +0.1. Click count = 1. Coolant code = 21.",
                    "partial": "Current pressure sum is 17.9, target is 18.0. Only valve B can be adjusted. How many clicks?",
                    "minimal": "The gap between current and target pressure tells you how many valve B clicks are needed.",
                },
                "hint": "Need +0.1 bar. Valve B = 1 click. Coolant code = 2 (fixed) + 1 (clicks) = 21.",
                "answer": "21",
                "on_solve": {
                    "msg": "Coolant pressure reaches 18.0 bar! Warning lights shift to GREEN.\nA status screen: 'Coolant STABLE. Control rods may now be calibrated safely'.",
                    "items": [{"name": "Coolant Stable Badge", "type": "clue", "key": "coolant_ok"}],
                    "clues": ["Coolant stable — control rod calibration unlocked"],
                },
            },
            "controlRods": {
                "label": "Control rod calibration",
                "type": "number", "length": 3,
                "hints": {
                    "full":    "Temp=412. Rod1=412/100=4 (floor). Rod2=4+2=6. Rod3=6-4=2. Dial settings: 4,6,2. Enter as 462.",
                    "partial": "The log book formula uses the core temperature reading. Floor division, then arithmetic.",
                    "minimal": "The log book and the temperature display. Do the math.",
                },
                "hint": "Temp=412. Rod1=4, Rod2=6, Rod3=2. Enter: 462.",
                "answer": "462",
                "on_solve": {
                    "msg": "Control rods lock into position. The reactor hum deepens and stabilises.\nCore temp drops to 380°C. Status: CONTROLLED.\nThe meltdown countdown pauses. Override terminal activates.\nA message: 'Meltdown averted — final override required for full shutdown'.",
                    "items": [{"name": "Reactor Stable Token", "type": "clue", "key": "reactor_stable"}],
                    "clues": ["Reactor stable — meltdown override terminal now active"],
                },
            },
            "meltdownOverride": {
                "label": "Meltdown override shutdown",
                "type": "number", "length": 4,
                "hints": {
                    "full":    "Rod1=4, Rod2=6, Rod3=2. Product=4×6×2=48. Pad to 4 digits: 0048.",
                    "partial": "Emergency manual says: product of all three rod values, last 4 digits, zero-padded.",
                    "minimal": "The manual on the desk. Rod values. Multiplication.",
                },
                "hint": "Rod1×Rod2×Rod3=4×6×2=48. Padded to 4 digits: 0048.",
                "answer": "0048",
                "on_solve": {
                    "msg": "REACTOR SHUTDOWN INITIATED.\n\nAll warning lights extinguish. The hum fades to silence.\nA PA system crackles: 'Reactor Core secured. Meltdown averted. Facility lockdown lifting in T-60 seconds.'\n\nYou did it. The drive. The reactor. All of it.\nProject Echo is yours, and the facility is safe.\n\n★ VAULT ZERO — FULL COMPLETION ★",
                    "items": [{"name": "Facility Shutdown Token", "type": "key", "key": "full_victory"}],
                    "clues": ["FULL COMPLETION — Reactor shutdown. You escaped and saved the facility."],
                },
            },
        },
        "use_interactions": {
            ("reactor_token", "entry panel"): {
                "msg": "You slot the Reactor Access Token into the entry panel reader. One of two inputs accepted.",
                "clue": "Token accepted — still need coolant code",
            },
            ("bio_fob", "override terminal"): {
                "msg": "The biometric fob is accepted. The override terminal now only needs the 4-digit emergency code.",
                "clue": "Biometric accepted — enter emergency code from rod product formula",
            },
            ("compound_x7", "coolant valves"): {
                "msg": "You add Compound X-7 to the coolant line. A gauge shows pressure stabilising faster.",
                "clue": "Compound X-7 added — coolant pressurises more efficiently",
            },
        },
        "solve_condition": ["entryPanel", "coolantValve", "controlRods", "meltdownOverride"],
        "exit_key": None,
        "next_room": None,
    },
}

ROOM_ORDER = ["storage", "lab", "server", "vault", "reactor"]


def export_quests_json():
    """Write quests.json for the Lua scripting layer to read."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quests.json")
    export = {
        rid: {
            "name":    r["name"],
            "puzzles": list(r["puzzles"].keys()),
            "difficulty_sensitive": True,
        }
        for rid, r in ROOMS.items()
    }
    with open(path, "w") as f:
        json.dump(export, f, indent=2)