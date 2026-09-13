import json
import secrets
import os

DEFAULT_MAX_RUN = 5

def _load_max_run(config_path="config.json"):
    """
    Reads markov2d_settings.max_run from config.json if present, else
    falls back to DEFAULT_MAX_RUN. Tolerant of a missing/invalid
    config.json so this module stays importable/testable standalone.
    """
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return int(config.get("markov2d_settings", {}).get("max_run", DEFAULT_MAX_RUN))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError, KeyError):
        return DEFAULT_MAX_RUN

MAX_RUN = _load_max_run()

class DecoyEngine:
    def __init__(self, model_path="model2d.json"):
        self.rules = {}
        self.ink_pool = []
        self.load_model(model_path)

    def load_model(self, path):
        if not os.path.exists(path):
            print(f"Warning: {path} not found. Decoys will be blank.")
            return

        with open(path, "r") as f:
            data = json.load(f)
            self.rules = data["rules"]

        # Flatten every non-space char seen in any context into one
        # frequency-weighted pool, used when we must force ink but the
        # current context has no (or no non-space) continuations.
        pool = []
        for chars in self.rules.values():
            pool.extend(c for c in chars if c != " ")
        self.ink_pool = pool

    def get_char(self, left, up, upleft, force_ink=False):
        """
        Look up the next character based on neighbors.
        If force_ink is True, never return a space: prefer the non-space
        entries of this context's own rule, then the global ink_pool,
        and only fall back to " " if the model has no ink at all.
        """
        key = f"{ord(left)},{ord(up)},{ord(upleft)}"

        possible_chars = self.rules.get(key)

        if force_ink:
            if possible_chars:
                non_space = [c for c in possible_chars if c != " "]
                if non_space:
                    return secrets.choice(non_space)
            if self.ink_pool:
                return secrets.choice(self.ink_pool)
            return " "

        if possible_chars:
            return secrets.choice(possible_chars)
        else:
            return " "

_engine = DecoyEngine()
def generate_decoy(linelen, lineheight, realtext):
    """
    Generates a 2D text texture of specific dimensions.

    Args:
        linelen (int): The width of the block.
        lineheight (int): The height of the block.
        realtext (str): Ignored for generation content (as requested),
                        but could be used for logging/metrics if needed.
    """
    grid = [[" " for _ in range(linelen)] for _ in range(lineheight-1)]

    for r in range(lineheight-1): #TODO find out why i need to put -1
        run = 0  # consecutive blanks placed so far in this row
        for c in range(linelen):
            left   = grid[r][c-1] if c > 0 else " "
            up     = grid[r-1][c] if r > 0 else " "
            upleft = grid[r-1][c-1] if (r > 0 and c > 0) else " "
            force = run >= MAX_RUN
            char = _engine.get_char(left, up, upleft, force_ink=force)
            grid[r][c] = char
            run = 0 if char != " " else run + 1
    return "\n".join("".join(row) for row in grid)
