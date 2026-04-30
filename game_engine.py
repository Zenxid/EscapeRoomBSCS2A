"""
game_engine.py — Vault Zero game state machine
Language: Python
No GUI code here — driven by CLI commands OR GUI button calls.
Both interfaces call the same engine methods and get the same state back.
"""
import time
from game_data import ROOMS, ROOM_ORDER


class GameEngine:
    def __init__(self, player: dict):
        self.player     = player
        self.room_id    = "storage"
        self.inventory  = []          # [{"name":..,"type":..,"key":..}]
        self.clues      = []          # list of strings
        self.solved     = {rid: [] for rid in ROOMS}  # {room_id: [puzzle_keys]}
        self.start_time = time.time()
        self.finished   = False
        self.escaped    = False

    # ── Helpers ────────────────────────────────────────────────────────────────
    @property
    def room(self):
        return ROOMS[self.room_id]

    @property
    def elapsed(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def remaining(self) -> int:
        return max(0, 900 - self.elapsed)

    def has_item(self, key: str) -> bool:
        return any(i["key"] == key for i in self.inventory)

    def add_item(self, item: dict):
        if not self.has_item(item["key"]):
            self.inventory.append(item)

    def room_solved(self) -> bool:
        return all(p in self.solved[self.room_id] for p in self.room["solve_condition"])

    def puzzle_solved(self, puzzle_key: str) -> bool:
        return puzzle_key in self.solved[self.room_id]

    # ── CLI command parser ─────────────────────────────────────────────────────
    def parse(self, raw: str) -> dict:
        """
        Parse a CLI command string.
        Returns {"lines": [(style, text), ...], "state_changed": bool}
        style: "normal" | "system" | "error" | "warn" | "gold" | "dim"
        """
        cmd = raw.strip().lower()
        if not cmd:
            return self._r([])

        if cmd == "help":
            return self._help()
        if cmd in ("look", "l"):
            return self._look()
        if cmd in ("inv", "inventory", "i"):
            return self._inv()
        if cmd in ("clues", "notes"):
            return self._clues()
        if cmd in ("stats", "status"):
            return self._stats()
        if cmd in ("map", "rooms"):
            return self._map()

        for prefix in ("examine ", "exam ", "x ", "inspect ", "look at ", "read "):
            if cmd.startswith(prefix):
                return self._examine(cmd[len(prefix):].strip())

        for prefix in ("take ", "grab ", "get ", "pick up "):
            if cmd.startswith(prefix):
                return self._take(cmd[len(prefix):].strip())

        for prefix in ("open ", "unlock ", "solve ", "crack "):
            if cmd.startswith(prefix):
                return self._open(cmd[len(prefix):].strip())

        # use X on Y
        for sep in (" on ", " with ", " at "):
            if " on " in cmd or " with " in cmd or " at " in cmd:
                parts = cmd.replace(" with ", " on ").replace(" at ", " on ").split(" on ", 1)
                if len(parts) == 2:
                    item_part = parts[0].replace("use ", "").strip()
                    obj_part  = parts[1].strip()
                    return self._use(item_part, obj_part)

        if cmd.startswith("enter ") or cmd.startswith("code ") or cmd.startswith("type "):
            code = cmd.split(" ", 1)[1].strip()
            return self._enter_code(code)

        if cmd in ("go", "go n", "go north", "north", "n", "forward", "next", "proceed"):
            return self._go()

        # number shortcut
        if cmd.isdigit():
            return self._number_shortcut(int(cmd))

        return self._r([("warn", f"Unknown command '{raw}'. Type 'help' for a list.")])

    # ── Actions ────────────────────────────────────────────────────────────────
    def _help(self):
        lines = [
            ("gold",   "─── VAULT ZERO COMMANDS ───────────────────────"),
            ("dim",    "  look / l              survey the room"),
            ("dim",    "  examine [object]      inspect something closely"),
            ("dim",    "  take [item]           pick up an item"),
            ("dim",    "  use [item] on [obj]   use item on object"),
            ("dim",    "  open [object]         attempt to unlock something"),
            ("dim",    "  enter [code]          submit a code when prompted"),
            ("dim",    "  inv / i               show inventory"),
            ("dim",    "  clues                 review clue log"),
            ("dim",    "  stats                 character stats"),
            ("dim",    "  map                   room order"),
            ("dim",    "  go n / next           proceed to next room"),
            ("dim",    "  [1/2/3]               quick-select GUI action"),
            ("gold",   "────────────────────────────────────────────────"),
        ]
        return self._r(lines)

    def _look(self):
        r = self.room
        lines = [
            ("gold",   f"── {r['name']} ──"),
            ("normal", r["look"]),
            ("dim",    ""),
            ("system", f"[db] {r['db_indicator']}"),
        ]
        unsolved = [k for k in r["puzzles"] if not self.puzzle_solved(k)]
        if unsolved:
            lines.append(("warn", f"Unsolved puzzles: {', '.join(unsolved)}"))
        return self._r(lines)

    def _examine(self, target: str):
        objects = self.room["objects"]
        key = self._find_obj(target, objects)
        if not key:
            return self._r([("warn", f"You don't see '{target}' here. Type 'look' for a list.")])
        lines = [("gold", f"── {key} ──"), ("normal", objects[key])]
        # hint about takeable items
        takeable = {"rope": "rope", "log": "maintenance log copy"}
        if key in takeable and not self.has_item(key):
            lines.append(("dim", f"(You can take this — type 'take {key}')"))
        return self._r(lines)

    def _take(self, target: str):
        takeables = {
            "rope": {"name": "Rope", "type": "item", "key": "rope"},
            "log":  {"name": "Maintenance Log", "type": "clue", "key": "log"},
            "flask":{"name": "Flask 7-ALPHA",   "type": "item", "key": "flask"},
        }
        key = self._find_obj(target, takeables)
        if not key:
            return self._r([("warn", "You can't take that.")])
        item = takeables[key]
        if self.has_item(item["key"]):
            return self._r([("dim", "You already have that.")])
        self.add_item(item)
        return self._r([("system", f"[ITEM] Obtained: {item['name']}")], changed=True)

    def _open(self, target: str):
        puzzles = self.room["puzzles"]
        # find puzzle matching target
        pkey = None
        for pk in puzzles:
            if target in pk.lower() or pk.lower() in target:
                pkey = pk
                break
        # also match object names that have puzzles
        obj_puzzle_map = {
            "toolbox": "toolbox", "cabinet": "cabinet",
            "filing cabinet": "cabinet", "specimen cabinet": "specimenCabinet",
            "terminal": "terminal", "briefcase": "briefcase",
        }
        if not pkey:
            for obj_name, pk in obj_puzzle_map.items():
                if obj_name in target or target in obj_name:
                    if pk in puzzles:
                        pkey = pk
                        break
        if not pkey:
            return self._r([("warn", f"Nothing to unlock called '{target}'. Try: " +
                             ", ".join(obj_puzzle_map.keys()))])
        puzzle = puzzles[pkey]
        if self.puzzle_solved(pkey):
            return self._r([("dim", "Already unlocked.")])
        lines = [
            ("gold",   f"── Puzzle: {puzzle['label']} ──"),
            ("normal", puzzle["hint"]),
            ("dim",    ""),
            ("warn",   f"Enter your answer: type  enter <code>  or use the GUI input."),
            ("dim",    f"[puzzle_key={pkey}]"),
        ]
        return self._r(lines, puzzle_key=pkey)

    def _enter_code(self, code: str):
        # find the first unsolved puzzle
        for pkey, puzzle in self.room["puzzles"].items():
            if not self.puzzle_solved(pkey):
                return self._submit_code(pkey, code)
        return self._r([("warn", "No active puzzle. Try 'open [object]' first.")])

    def submit_puzzle(self, puzzle_key: str, code: str) -> dict:
        """Called by both CLI 'enter' and GUI submit button."""
        return self._submit_code(puzzle_key, code)

    def _submit_code(self, pkey: str, code: str) -> dict:
        puzzles = self.room["puzzles"]
        if pkey not in puzzles:
            return self._r([("error", "Puzzle not found.")])
        puzzle = puzzles[pkey]
        if self.puzzle_solved(pkey):
            return self._r([("dim", "Already solved.")])

        if code.lower().strip() == puzzle["answer"].lower().strip():
            self.solved[self.room_id].append(pkey)
            sol = puzzle["on_solve"]
            lines = [("system", "[CORRECT] " + sol["msg"])]
            for item in sol.get("items", []):
                self.add_item(item)
                lines.append(("system", f"[ITEM] Obtained: {item['name']}"))
            for clue in sol.get("clues", []):
                self.clues.append(clue)
                lines.append(("system", f"[CLUE] {clue}"))
            if self.room_solved():
                lines.append(("gold", "ALL PUZZLES SOLVED — type 'go n' or click PROCEED to advance."))
            if pkey == "briefcase":
                self.finished = True
                self.escaped  = True
                lines.append(("gold", "═══════════════════════════════════════"))
                lines.append(("gold", "         VAULT ZERO — ESCAPED          "))
                lines.append(("gold", "═══════════════════════════════════════"))
            return self._r(lines, changed=True, solved=pkey)
        else:
            return self._r([("error", f"[WRONG] Incorrect code. Try again.")], wrong=True)

    def _use(self, item_target: str, obj_target: str):
        inv_item = next((i for i in self.inventory if item_target in i["key"] or item_target in i["name"].lower()), None)
        if not inv_item:
            return self._r([("warn", f"You don't have '{item_target}'. Check your inventory.")])
        interactions = self.room.get("use_interactions", {})
        match = next(
            (v for (ik, ok), v in interactions.items() if ik in inv_item["key"] and ok in obj_target),
            None
        )
        if match:
            lines = [("system", match["msg"])]
            if "clue" in match:
                self.clues.append(match["clue"])
                lines.append(("system", f"[CLUE] {match['clue']}"))
            return self._r(lines, changed=True)
        return self._r([("warn", f"Using {inv_item['name']} on {obj_target} does nothing useful right now.")])

    def _go(self):
        if not self.room_solved():
            remaining = [p for p in self.room["solve_condition"] if not self.puzzle_solved(p)]
            lines = [
                ("error", "[BLOCKED] Room not fully solved."),
                ("warn",  f"Remaining puzzles: {', '.join(remaining)}"),
            ]
            return self._r(lines)
        exit_key = self.room.get("exit_key")
        if exit_key and not self.has_item(exit_key):
            return self._r([("error", f"You need the {exit_key} to proceed.")])
        next_id = self.room.get("next_room")
        if not next_id:
            return self._r([("gold", "You are already in the final vault!")])
        self.room_id = next_id
        r = self.room
        lines = [
            ("gold",   f"── ENTERING: {r['name']} ──"),
            *[("normal", d) for d in r["desc"]],
            ("dim",    ""),
            ("system", f"[db] {r['db_indicator']}"),
            ("dim",    "Type 'look' to survey the room."),
        ]
        return self._r(lines, changed=True, room_changed=True)

    def _inv(self):
        if not self.inventory:
            return self._r([("dim", "Inventory is empty.")])
        lines = [("gold", "── Inventory ──")]
        for item in self.inventory:
            lines.append(("normal", f"  [{item['type'].upper():6}] {item['name']}"))
        return self._r(lines)

    def _clues(self):
        if not self.clues:
            return self._r([("dim", "No clues recorded yet. Examine objects carefully.")])
        lines = [("gold", "── Clue Log ──")]
        for i, c in enumerate(self.clues, 1):
            lines.append(("normal", f"  {i}. {c}"))
        return self._r(lines)

    def _stats(self):
        m, s = divmod(self.remaining, 60)
        lines = [
            ("gold",   "── Character Stats ──"),
            ("normal", f"  Player : {self.player['username']}"),
            ("normal", f"  Level  : {self.player['level']}"),
            ("normal", f"  XP     : {self.player['total_xp']}"),
            ("normal", f"  Escapes: {self.player['escapes']}"),
            ("warn",   f"  Time   : {m:02d}:{s:02d} remaining"),
            ("normal", f"  Room   : {self.room['name']}"),
        ]
        return self._r(lines)

    def _map(self):
        lines = [("gold", "── Room Order ──")]
        for rid in ["storage", "lab", "server", "vault"]:
            status = "CURRENT" if rid == self.room_id else ("DONE" if all(p in self.solved[rid] for p in ROOMS[rid]["solve_condition"]) else "locked")
            lines.append(("normal" if rid != self.room_id else "system",
                          f"  {'►' if rid==self.room_id else ' '} {ROOMS[rid]['name']}  [{status}]"))
        return self._r(lines)

    def _number_shortcut(self, n: int):
        actions = self._get_quick_actions()
        if 1 <= n <= len(actions):
            return self.parse(actions[n-1]["cmd"])
        return self._r([("warn", f"No action {n}.")])

    # ── Quick actions for GUI buttons ──────────────────────────────────────────
    def get_gui_actions(self) -> list:
        """Return list of {label, cmd, style} for the GUI action buttons."""
        return self._get_quick_actions()

    def _get_quick_actions(self) -> list:
        actions = [{"label": "Look around", "cmd": "look", "style": "normal"}]
        for obj in list(self.room["objects"].keys())[:4]:
            actions.append({"label": f"Examine {obj}", "cmd": f"examine {obj}", "style": "normal"})
        for pkey, puzzle in self.room["puzzles"].items():
            if not self.puzzle_solved(pkey):
                obj_map = {"toolbox":"toolbox","cabinet":"cabinet","specimenCabinet":"specimen cabinet",
                           "terminal":"terminal","briefcase":"briefcase"}
                obj_name = obj_map.get(pkey, pkey)
                actions.append({"label": f"Open {obj_name}", "cmd": f"open {obj_name}", "style": "warn"})
        if self.room_solved() and self.room.get("next_room"):
            actions.append({"label": "Proceed north ►", "cmd": "go n", "style": "gold"})
        return actions

    # ── Internals ──────────────────────────────────────────────────────────────
    def _find_obj(self, target: str, collection: dict) -> str | None:
        t = target.lower().strip()
        if t in collection:
            return t
        for k in collection:
            if t in k or k.split()[0] in t:
                return k
        return None

    def _r(self, lines, changed=False, room_changed=False, puzzle_key=None, solved=None, wrong=False):
        return {
            "lines": lines,
            "state_changed": changed,
            "room_changed": room_changed,
            "puzzle_key": puzzle_key,
            "solved_puzzle": solved,
            "wrong_code": wrong,
            "inventory": self.inventory[:],
            "clues": self.clues[:],
            "room_id": self.room_id,
            "remaining": self.remaining,
            "escaped": self.escaped,
            "finished": self.finished,
        }

    def get_room_enter_output(self) -> dict:
        """Called when first entering a room."""
        r = self.room
        lines = [
            ("gold",   "═" * 50),
            ("gold",   f"  {r['name']}"),
            ("gold",   "═" * 50),
            *[("normal", d) for d in r["desc"]],
            ("dim",    ""),
            ("system", f"[db] {r['db_indicator']}"),
            ("dim",    "Type 'look' to survey the room, or 'help' for all commands."),
            ("dim",    ""),
        ]
        return self._r(lines, room_changed=True)
