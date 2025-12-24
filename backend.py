#!/usr/bin/env python3
from collections import defaultdict
import io
import zlib
import base64
import json
from PIL import Image, ImageDraw, ImageFont
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

class CaptchaCompressor:
    def __init__(self, font_path="font.ttf", font_size=20):
        try:
            self.font = ImageFont.truetype(font_path, font_size)
        except:
            print("Warning: Font not found, loading default.")
            self.font = ImageFont.load_default()

    def encode_bundle(self, text_frames):
        """
        Takes a list of ASCII strings.
        Returns a JSON object with metadata and ONE compressed binary blob.
        """
        if not text_frames: return None

        dummy_img = Image.new('1', (1, 1))
        d = ImageDraw.Draw(dummy_img)
        bbox = d.textbbox((0, 0), text_frames[0], font=self.font)
        width, height = bbox[2], bbox[3]
        
        width += 10
        height += 10
        all_frames_bits = bytearray()

        print(f"Encoding {len(text_frames)} frames...")

        for text in text_frames:
            img = Image.new('1', (width, height), color=1) # 1 is white
            draw = ImageDraw.Draw(img)
            draw.text((5, 5), text, font=self.font, fill=0) # 0 is black
            pixels = list(img.getdata())
            frame_bytes = bytearray()
            current_byte = 0
            bit_idx = 0
            
            for p in pixels:
                if p == 0: 
                    current_byte |= (1 << (7 - bit_idx))
                bit_idx += 1
                if bit_idx == 8:
                    frame_bytes.append(current_byte)
                    current_byte = 0
                    bit_idx = 0
            if bit_idx > 0:
                frame_bytes.append(current_byte)
                
            all_frames_bits.extend(frame_bytes)
        compressed_data = zlib.compress(all_frames_bits, level=9)
        b64_string = base64.b64encode(compressed_data).decode('utf-8')

        return {
            "width": width,
            "height": height,
            "count": len(text_frames),
            "data": b64_string
        }
imager = CaptchaCompressor()
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
        # produce exactly `length` characters in the returned string
        if length <= 0:
            return ""
        start_key = random.choice(list(self.model.keys()))
        output = start_key
        current_state = start_key

        # keep adding characters until we have at least `length`, then trim
        while len(output) < length:
            possible_next_chars = self.model.get(current_state)
            if not possible_next_chars:
                current_state = random.choice(list(self.model.keys()))
                # reset current_state to a valid key but keep trying to reach desired length
                continue

            next_char = random.choice(possible_next_chars)
            output += next_char
            current_state = output[-self.order:]

        return output[:length]

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
    charlens=config["charlens"]
    steps=config.get("steps",50)
    deceptor=config.get("deceptor","markov")
    if deceptor=="markov":
        markov_chain=AsciiMarkovChain.load_from_json("model.json")
        def generate_decoy(linelen,lineheight,realtext):
            global markov_chain

            decoy_base=markov_chain.generate(linelen*(lineheight-1)+1)
            decoy=decoy_base[:-1]
            #split into lineheight lines of length linelen
            lines=[]
            for i in range(lineheight-1):
                lines.append(decoy[i*linelen:(i+1)*linelen])
            return "\n".join(lines) + decoy_base[-1]
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
        {"id":"unique-id-urlsafe-base64",
        "challenge":["random_challenge1","2", ... ,"50"],
        "steps":50}
GET /challenge_img: Get an image challenge.The image is a compressed bundle of all frames. See source code for format.
    Request body: none needed
    Example response:
        {"id":"unique-id-urlsafe-base64",
        "challenge":{"width":W,"height":H,"count":N,"data":"base64-encoded-compressed-binary-blob"},
        "steps":50}
    Use the same /verify endpoint to verify the answer.
    To decode the image, see the example.html implementation in github.com/itzmetanjim/tinac
POST /verify    : Verify an answer (case sensitive).
    Example request body: {"id":"unique-id-urlsafe-base64","answer":"abcd"} or {"id":"unique-id-urlsafe-base64","answer":"abcd", "index": 2}
    Example response: {"answer": true} 
                or: {"answer": true, "index": true}
                or: {"error": "Invalid or expired ID/id parameter required/answer parameter required"}
    """

@app.get("/challenge")
def get_challenge():
    global charlens
    
    cid=secrets.token_urlsafe(32)
    challenge="".join(secrets.choice(chars) for _ in range(secrets.choice(charlens)))
    fonts=[secrets.choice(good_fonts) for _ in range(len(challenge))]
    if len(challenges)>100000000: # approx 4GB ram usage limit
        challenges.popitem(last=False)
    ctext = asciiart(list(zip(challenge, fonts)))
    correct_index=secrets.randbelow(steps+1)
    challenges[cid]=[challenge,correct_index]
    #generate decoys
    challenges_list=[]
    for i in range(steps):
        if i==correct_index:
            challenges_list.append(ctext)
        else:
            emptylinesbefore=0
            emptylinesafter=0
            for line in ctext.split("\n"):
                if line.strip()=="":
                    emptylinesbefore+=1
                else:
                    break
            for line in reversed(ctext.split("\n")):
                if line.strip()=="":
                    emptylinesafter+=1
                else:
                    break
            linelen = max(len(line) for line in ctext.split("\n"))
            lineheight = len(ctext.split("\n")) - emptylinesbefore - emptylinesafter
            
            decoy_text=(" "*linelen + "\n")* emptylinesbefore + generate_decoy(linelen,lineheight,challenge) + ("\n" + " "*linelen)* emptylinesafter
            challenges_list.append(decoy_text)
    
    return {"id":cid,"challenge":challenges_list,"steps":steps}



@app.get("/challenge_img")
def get_challenge_img():
    global charlens
    global imager #CaptchaCompressor instance

    cid=secrets.token_urlsafe(32)
    challenge="".join(secrets.choice(chars) for _ in range(secrets.choice(charlens)))
    fonts=[secrets.choice(good_fonts) for _ in range(len(challenge))]
    if len(challenges)>100000000: # approx 4GB ram usage limit
        challenges.popitem(last=False)
    ctext = asciiart(list(zip(challenge, fonts)))
    correct_index=secrets.randbelow(steps+1)
    challenges[cid]=[challenge,correct_index]
    #generate decoys
    challenges_list=[]
    for i in range(steps):
        if i==correct_index:
            challenges_list.append(ctext)
        else:
            emptylinesbefore=0
            emptylinesafter=0
            for line in ctext.split("\n"):
                if line.strip()=="":
                    emptylinesbefore+=1
                else:
                    break
            for line in reversed(ctext.split("\n")):
                if line.strip()=="":
                    emptylinesafter+=1
                else:
                    break
            linelen = max(len(line) for line in ctext.split("\n"))
            lineheight = len(ctext.split("\n")) - emptylinesbefore - emptylinesafter
            
            decoy_text=(" "*linelen + "\n")* emptylinesbefore + generate_decoy(linelen,lineheight,challenge) + ("\n" + " "*linelen)* emptylinesafter
            challenges_list.append(decoy_text)
    #now convert to image
    imgdata = imager.encode_bundle(challenges_list)
    return {"id":cid,"challenge":imgdata,"steps":steps}

@app.post("/verify")
def verify_answer(payload: dict):
    cid=payload.get("id",None)
    answer=payload.get("answer",None)
    index=payload.get("index",None)
    if cid not in challenges:
        return {"error":"Invalid or expired ID"}
    if answer is None:
        return {"error":"answer parameter required"}
    correct_answer,correct_index=challenges.pop(cid)
    response={"answer": answer==correct_answer}
    if index is not None:
        response["index"]= index==correct_index
    return response


    

if __name__ == "__main__":
    uvicorn.run("backend:app", host="0.0.0.0", port=3456, reload=True)
