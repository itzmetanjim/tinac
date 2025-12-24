from collections import defaultdict
import json
import pyfiglet
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn
import secrets
import random
from fastapi.middleware.cors import CORSMiddleware
origins = [
    "http://localhost",
    "http://localhost:8080",
    "*",
]


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
with open("config.json","r") as f:
    config=json.load(f)
    good_fonts=config["good_fonts"]
    chars=config["chars"] #Confusing chars may make the captcha hard so those are removed
    deceptor=config.get("deceptor","markov")
    if deceptor=="markov":
        markov_chain=AsciiMarkovChain.load_from_json("model.json")
        def generate_decoy(linelen,lineheight,realtext):
            global markov_chain
            decoy=markov_chain.generate(linelen*lineheight)
            #split into lineheight lines of length linelen
            lines=[]
            for i in range(lineheight):
                lines.append(decoy[i*linelen:(i+1)*linelen])
            return "\n".join(lines)
    elif deceptor=="random":
        def generate_decoy(linelen,lineheight,realtext):
            decoy=""
            charset=realtext.replace("\n","")
            for _ in range(lineheight):
                line="".join(secrets.choice(charset) for _ in range(linelen))
                decoy+=line+"\n"
            return decoy
    else:
        #import python module
        try:
            deceptor_module=__import__(deceptor)
        except ImportError as e:
            print("Error: Deceptor module not found.",e)
            exit(1)
        def generate_decoy(linelen,lineheight,realtext):
            return deceptor_module.generate_decoy(linelen,lineheight,realtext)
        
    
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print(asciiart([("Starting server...", "standard")]))
challenges={}
@app.get("/",response_class=PlainTextResponse)
def read_root():
    """
    Returns help text.
    """
    return """TINAC API is running.
Endpoints:
GET /challenge  : Get a random challenge.
    Request body: none needed
    Example response:
        {"id":"unique-id-urlsafe-base64"
        "challenge":["random_challenge_texts"]}
POST /verify    : Verify an answer (case sensitive).
    Example request body: {"id":"unique-id-urlsafe-base64","answer":"abcd"} or {"id":"unique-id-urlsafe-base64","answer":"abcd", "index": 2}
    Example response: {"answer": true} 
                or: {"answer": true, "index": true}
                or: {"error": "Invalid or expired ID/id parameter required/answer parameter required"}
    """

@app.get("/challenge")
def get_challenge():
    cid=secrets.token_urlsafe(32)
    challenge="".join(secrets.choice(chars) for _ in range(secrets.choice([5,6,7])))
    fonts=[secrets.choice(good_fonts) for _ in range(len(challenge))]
    if len(challenges)>1000:
        challenges.popitem(last=False)
    ctext = asciiart(list(zip(challenge, fonts)))
    correct_index=secrets.randbelow(51)
    challenges[cid]=[challenge,correct_index]
    #generate decoys
    challenges_list=[]
    for i in range(50):
        if i==correct_index:
            challenges_list.append(ctext)
        else:
            decoy_text=generate_decoy(len(challenge),1,challenge).replace("\n","")
            challenges_list.append(decoy_text)
    
    return {"id":cid,"challenge":challenges_list}



    

if __name__ == "__main__":
    uvicorn.run("backend:app", host="127.0.0.1", port=8000, reload=True)
