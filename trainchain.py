"""Train the Markov Chain to generate fake ASCII art."""
import pyfiglet
import random  #Seeded by secrets for security
import secrets #Generates seeds
import random
from collections import defaultdict
import json
with open("config.json","r") as f:
    config=json.load(f)
    chars=config["chars"] #Confusing chars may make the captcha hard so those are removed
    good_fonts=config["good_fonts"]
    order=config["training_settings"]["memory"]
    examples=config["training_settings"]["examples"]
class AsciiMarkovChain:
    def __init__(self, corpus=None, order=5):
        self.order = order
        self.model = defaultdict(list)
        if corpus:
            self._train(corpus)
    def _train(self, corpus):
        for i in range(len(corpus) - self.order):
            current_state = corpus[i : i + self.order]
            next_char = corpus[i + self.order]
            self.model[current_state].append(next_char)

    def generate(self, length=1000):
        start_key = random.choice(list(self.model.keys()))
        output = start_key
        current_state = start_key
        
        for _ in range(length):
            possible_next_chars = self.model.get(current_state)
            if not possible_next_chars:
                current_state = random.choice(list(self.model.keys()))
                continue
            
            next_char = random.choice(possible_next_chars)
            output += next_char
            current_state = output[-self.order:]
            
        return output

    def save_to_json(self, filepath="model.json"):
        data = {
            "order": self.order,
            "model": self.model
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"Model saved to {filepath}")
    @classmethod
    def load_from_json(cls, filepath="model.json"):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        instance = cls(corpus=None, order=data["order"])
        instance.model = defaultdict(list, data["model"])
        
        return instance

#generate the corpus!
def asciiart(text_font_pairs):
    all_blocks = []
    for text, font in text_font_pairs:
        art = pyfiglet.figlet_format(text, font=font)
        all_blocks.append(art.splitlines())
    max_height = max(len(block) for block in all_blocks)
    for block in all_blocks:
        while len(block) < max_height:
            block.append(" " * len(block[0]) if block else "")
    ans = ""
    for i in range(max_height):
        combined_line = "".join(block[i] for block in all_blocks)
        ans += combined_line + "\n"
    return ans
try:
    
    print(asciiart([("Starting...","standard")]))
    print("Press Ctrl+C to stop.")
    corpus = ""
    print("- Seeding RNG... (1/4)")
    rng = random.Random(secrets.randbits(64))
    print(f"\033[A\033[0;32;49m- Generating random text (2/4) 0/{examples}")

    def get_challenge():
        global rng
        challenge="".join(rng.choice(chars) for _ in range(rng.choice([5,6,7])))
        fonts=[rng.choice(good_fonts) for _ in range(len(challenge))]
        ctext = asciiart(list(zip(challenge, fonts))).replace("\n","")
        return ctext
    for i in range(examples):
        corpus += get_challenge()
        if i % 19 == 0:
            print(f"\033[A- Generating random text (2/4) {i+1}/{examples}")
    print("\033[A- Training Markov Chain... (3/4)")
    markov_chain = AsciiMarkovChain(corpus, order=order)
    print("\033[A- Saving model to model.json... (4/4)")
    markov_chain.save_to_json("model.json")
    print("\033[1;92;49mCompleted training and saved model successfully.\033[0;39;49m")
    print("Test generation: (this should be giberrish)")
    initgen = markov_chain.generate(200)
    testgen = ""
    #split into line length 40 (in an actual generation this would be the same as the real one)
    for i in range(0, len(initgen), 40):
        testgen += initgen[i:i+40] + "\n"
    print(testgen)
except KeyboardInterrupt:
    exit(0)
except Exception as e:
    raise e