import json
import secrets
import pyfiglet
from collections import defaultdict

# --- CONFIG LOADING ---
def load_config(path="config.json"):
    with open(path, "r") as f:
        return json.load(f)

CONFIG = load_config()

def asciiart(text_font_pairs): 
    all_blocks = []
    for text, font in text_font_pairs:
        try:
            art = pyfiglet.figlet_format(text, font=font)
        except:
            art = pyfiglet.figlet_format(text, font="standard")
        all_blocks.append(art.splitlines())
    
    if not all_blocks: return ""

    max_height = max(len(block) for block in all_blocks)
    for block in all_blocks:
        while len(block) < max_height:
            block.append(" " * len(block[0]) if block else "")
            
    ans = ""
    for i in range(max_height):
        combined_line = "".join(block[i] for block in all_blocks if i < len(block))
        ans += combined_line + "\n"
    return ans

def generate_training_corpus():
    """Generates a massive string of random CAPTCHA-like text."""
    print("Generating training corpus...")
    corpus_lines = []
    
    num_examples = CONFIG["training_settings"]["examples"]
    chars = CONFIG["chars"]
    charlens = CONFIG["charlens"]
    good_fonts = CONFIG["good_fonts"]

    for i in range(num_examples):
        if i % 100 == 0: print(f"Generated {i}/{num_examples} examples...")
        
        word_len = secrets.choice(charlens)
        challenge_text = "".join(secrets.choice(chars) for _ in range(word_len))
        fonts = [secrets.choice(good_fonts) for _ in range(len(challenge_text))]
        
        art_block = asciiart(list(zip(challenge_text, fonts)))
        
        lines = art_block.split("\n")
        # remove empty strings resulting from split
        lines = [l for l in lines if l] 
        corpus_lines.extend(lines)

    return corpus_lines

# --- 2D MARKOV TRAINING ---
def train():
    lines = generate_training_corpus()
    
    # Pad lines to form a perfect grid 
    if not lines: return
    max_width = max(len(l) for l in lines)
    grid = [line.ljust(max_width) for line in lines]
    height = len(grid)
    
    model = defaultdict(list)
    order = CONFIG["training_settings"].get("memory", 3) # unused in 2d
    
    print("Analyzing 2D patterns...")
    
    for r in range(1, height):
        for c in range(1, max_width):
            curr = grid[r][c]
            
            # use ordinals (ascii codes) for the key to avoid json escaping issues with \ or "
            left_char = grid[r][c-1]
            up_char   = grid[r-1][c]
            upleft_char = grid[r-1][c-1]
            key = f"{ord(left_char)},{ord(up_char)},{ord(upleft_char)}"
            
            model[key].append(curr)

    final_model = {
        "rules": dict(model),
        "meta": {
            "avg_width": max_width, # Just for reference
            "description": "2D Markov Chain (Left, Up, UpLeft)"
        }
    }

    with open("model2d.json", "w") as f:
        json.dump(final_model, f)
    
    print("Training complete. Saved to model2d.json")

if __name__ == "__main__":
    train()