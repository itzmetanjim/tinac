import json
import secrets
import os

class DecoyEngine:
    def __init__(self, model_path="model2d.json"):
        self.rules = {}
        self.load_model(model_path)
        
    def load_model(self, path):
        if not os.path.exists(path):
            print(f"Warning: {path} not found. Decoys will be blank.")
            return

        with open(path, "r") as f:
            data = json.load(f)
            self.rules = data["rules"]

    def get_char(self, left, up, upleft):
        """
        Look up the next character based on neighbors.
        """
        key = f"{ord(left)},{ord(up)},{ord(upleft)}"
        
        possible_chars = self.rules.get(key)
        
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
    grid = [[" " for _ in range(linelen)] for _ in range(lineheight)]
    
    for r in range(lineheight):
        for c in range(linelen):
            left   = grid[r][c-1] if c > 0 else " "
            up     = grid[r-1][c] if r > 0 else " "
            upleft = grid[r-1][c-1] if (r > 0 and c > 0) else " "
            char = _engine.get_char(left, up, upleft)
            grid[r][c] = char
    return "\n".join("".join(row) for row in grid)