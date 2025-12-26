#!/usr/bin/env python3
from collections import defaultdict
import io
import zlib
import base64
import json
import sys
from PIL import Image, ImageDraw, ImageFont
import pyfiglet
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn
import secrets
from pydub import AudioSegment
import jwt
from fastapi.middleware.cors import CORSMiddleware
import importlib
import time
import shutil
app = FastAPI()
origins = [
    "http://localhost",
    "http://localhost:8080",
    "*",
]
color_warn="\x1b[1;93;49m"
color_err="\x1b[1;91;49m"
color_acc="\x1b[1;92;49m"
color_reset="\x1b[0m"
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
        start_key = secrets.choice(list(self.model.keys()))
        output = start_key
        current_state = start_key

        # keep adding characters until we have at least `length`, then trim
        while len(output) < length:
            possible_next_chars = self.model.get(current_state)
            if not possible_next_chars:
                current_state = secrets.choice(list(self.model.keys()))
                # reset current_state to a valid key but keep trying to reach desired length
                continue

            next_char = secrets.choice(possible_next_chars)
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

try:
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
                deceptor_module=importlib.import_module(deceptor)
            except ImportError as e:
                print(f"{color_err}Error: Deceptor module not found.{color_reset}",e)
                exit(1)
            def generate_decoy(linelen,lineheight,realtext):
                return deceptor_module.generate_decoy(linelen,lineheight,realtext)
        audio_engine=config.get("audio_engine","audiogen")
        try:
            audio_module=importlib.import_module(audio_engine)
            audio_generator=audio_module.AudioGenerator("config.json")
        except ImportError as e:
            print(f"{color_err}Error: Audio engine module not found.{color_reset}",e)
            exit(1)
        jwt_secret=config.get("jwt_secret",None)
        if jwt_secret == None:
            print(f"{color_err}Error: jwt_secret not set in config.json. Please set it to a secure random string.{color_reset}")
            exit(1)
except FileNotFoundError:
    print(f"{color_err}Error: config.json not found.{color_reset}")
    print(f"{color_warn}Try copying config.json.example to config.json and editing it as needed.{color_reset}")
    exit(1)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print(color_acc+asciiart([("Starting...", "standard")])+color_reset)
print(f"{color_acc}TINAC API is running. Press Ctrl+C to stop.{color_reset}")
print(f"{color_acc}Listening on 0.0.0.0:{sys.argv[1] if len(sys.argv) > 1 else 3456}.{color_reset}")
if ((shutil.which("ffmpeg") is None) and (shutil.which("avconv") is None)) and ("audio" in config.get("allowed_types",[])):
    print(f"{color_warn}Warning: ffmpeg or avconv not installed. Audio challenges may not work properly.{color_reset}")
if jwt_secret=="CHANGE_THIS_CHANGE_THIS_CHANGE_THIS_CHANGE_THIS":
            print(f"{color_err}Warning: jwt_secret is set to the default value. THIS IS ONLY RECOMMENDED FOR TESTING. Change this to a different value.{color_reset}")
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
GET /challenge_audio: Get an audio challenge.The audio is a base64 encoded mp3 file array.
    Request body: none needed
    Example response:
        {"id":"unique-id-urlsafe-base64",
        "challenge":["base64-encoded-mp3-audio-data1","2", ... ,"50"],
        "steps":50}
    Use the same /verify endpoint to verify the answer.
POST /verify    : Verify an answer (case sensitive).
    Example request body: {"id":"unique-id-urlsafe-base64","answer":"abcd"} or {"id":"unique-id-urlsafe-base64","answer":"abcd", "index": 2}
    Example response: {"answer": true} 
                or: {"answer": true, "index": true}
                or: {"error": "Invalid or expired ID/id parameter required/answer parameter required"}
    """

@app.get("/challenge")
def get_challenge():
    if "legacy" not in config.get("allowed_types",[]):
        return {"error":"Legacy challenges are disabled."}
    global charlens
    
    cid="legacy_"+secrets.token_urlsafe(32)
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
    if "image" not in config.get("allowed_types",[]):
        return {"error":"Image challenges are disabled."}
    global charlens
    global imager #CaptchaCompressor instance

    cid="image_"+secrets.token_urlsafe(32)
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

@app.get("/challenge_audio")
def get_audio_challenge():
    if "audio" not in config.get("allowed_types",[]):
        return {"error":"Audio challenges are disabled."}
    global charlens
    global audio_generator
    cid="audio_"+secrets.token_urlsafe(32)
    challenge="".join(secrets.choice(chars) for _ in range(secrets.choice(charlens)))
    if len(challenges)>100000000: # approx 4GB ram usage limit
        challenges.popitem(last=False)
    correct_index=secrets.randbelow(steps+1)
    challenges[cid]=[challenge,correct_index]
    challenges_list = []
    for i in range(steps):
        if i == correct_index:
            audio_seg = audio_generator.segment_to_base64(audio_generator.generate_real(challenge))
            challenges_list.append(audio_seg)
        else:
            audio_seg = audio_generator.segment_to_base64(audio_generator.generate_decoy(len(challenge)))
            challenges_list.append(audio_seg)
    return {"id": cid, "challenge": challenges_list, "steps": steps}




@app.post("/verify")
def verify_answer(payload: dict):
    cid=payload.get("id",None)
    answer=payload.get("answer",None)
    index=payload.get("index",None)
    if cid not in challenges:
        return {"error":"Invalid or expired ID"}
    if answer is None:
        return {"error":"answer parameter required"}
    if cid is None:
        return {"error":"id parameter required"}
    if cid.startswith("audio_"):
        ctype="audio"
    elif cid.startswith("image_"):
        ctype="image"
    elif cid.startswith("legacy_"):
        ctype="legacy"
    else:
        print(f"{color_warn}Warning: A challenge ID with invalid prefix was issued by the server:{color_reset} {cid}")
        return {"error":"Invalid or expired ID"}
    
    correct_answer,correct_index=challenges.pop(cid)
    response={"answer": answer==correct_answer}
    if index is not None:
        response["index"]= index==correct_index
    jwt_payload={
        "cid": cid,
        "answer": answer==correct_answer,
        "index": index==correct_index if index is not None else False,
        "type": ctype,
        "iat": int(time.time()),
        "exp": int(time.time()) + 300  # Token expires in 5 minutes
    }
    token = jwt.encode(jwt_payload, jwt_secret, algorithm="HS256")
    response["token"] = token
    return response

@app.post("/verify_token")
def verify_token(payload: dict):
    token=payload.get("token",None)
    if token is None:
        return {"error":"token parameter required"}
    try:
        decoded = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        return {"valid": True, "data": decoded}
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token has expired"}
    except jwt.InvalidTokenError:
        return {"valid": False, "error": "Invalid token"}
    

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else 3456
    uvicorn.run("backend:app", host="0.0.0.0", port=int(port), reload=True)