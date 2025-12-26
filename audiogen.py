import base64
import os
import glob
import json
import secrets
import io

from pydub import AudioSegment
class AudioGenerator:
    def __init__(self, config_path="config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.num_files = self._index_nums()
        durs = []
        for digit in self.num_files:
            for path in self.num_files[digit]:
                durs.append(len(AudioSegment.from_wav(path)))
        self.max_num_len = max(durs) if durs else 700
        self.min_num_len = min(durs) if durs else 500
        total_ms = 0
        count = 0
        for digit in self.num_files:
            for path in self.num_files[digit]:
                total_ms += len(AudioSegment.from_wav(path))
                count += 1
        self.sdur = total_ms / count if count > 0 else 500
        gapval = self.config.get("gap","500")
        self.gap = float(gapval) if not gapval.endswith("%") else (self.sdur * float(gapval[:-1]) / 100)
        sources = []
        for json_path in glob.glob(f"audio/aligned/*.json"):
            mp3_path = json_path.replace(".json", ".mp3")
            if os.path.exists(mp3_path):
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    number_words = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
                    safe_zones = [
                        w for w in data.get("words", [])
                        if w.get("case") == "success" and w["word"].lower() not in number_words
                    ]
                if safe_zones:
                    sources.append({"audio": mp3_path, "zones": safe_zones})
        self.decoy_sources = sources
        
    def _index_nums(self):
        index = {str(i): [] for i in range(10)}
        for f in glob.glob("audio/numbers/*.wav"):
            filename = os.path.basename(f)
            digit = filename[0]
            if digit in index:
                index[digit].append(f)
        return index
    def _fit_to_grid(self,segment):
        #grid is a 1D grid
        currentlen=len(segment)
        if currentlen==0:return AudioSegment.silent(duration=0)
        new_rate = int((currentlen / self.sdur) * segment.frame_rate)
        new_rate = max(8000, min(new_rate, 96000))
        warped = segment._spawn(segment.raw_data, overrides={"frame_rate": new_rate})
        return warped.set_frame_rate(44100).normalize()
    def generate_real(self,digits):
        combined= AudioSegment.empty()
        spacer= AudioSegment.silent(duration=self.gap)
        for i in str(digits):
            if i not in self.num_files or not self.num_files[i]:
                continue
            path=secrets.choice(self.num_files[i])
            seg = AudioSegment.from_wav(path)
            combined += self._fit_to_grid(seg) + spacer
        return combined
    def generate_decoy(self, length):
        combined = AudioSegment.empty()
        spacer = AudioSegment.silent(duration=self.gap)
        source_data = secrets.choice(self.decoy_sources)
        full_audio = AudioSegment.from_mp3(source_data["audio"])
        safe_zones = source_data["zones"]
        cryptogen = secrets.SystemRandom()
        for _ in range(length):
            slice_len = cryptogen.randint(int(self.min_num_len), int(self.max_num_len))
            candidates = [w for w in safe_zones if (w["end"] - w["start"]) * 1000 > slice_len]
            if not candidates:
                word = cryptogen.choice(safe_zones)
                print("Warning: not candidates is true")
            else:
                word = cryptogen.choice(candidates)
            w_start_ms = int(word["start"] * 1000)
            w_end_ms = int(word["end"] * 1000)
            w_dur = w_end_ms - w_start_ms
            if w_dur > slice_len:
                max_offset = w_dur - slice_len
                offset = cryptogen.randint(0, max_offset)
                start = w_start_ms + offset
                end = start + slice_len
            else:
                start, end = w_start_ms, w_end_ms
            
            seg = full_audio[start:end]
            combined += self._fit_to_grid(seg) + spacer
            
        return combined
    def segment_to_base64(self, segment):
        buffer = io.BytesIO()
        segment.export(buffer, format="mp3", bitrate="64k")
        binary_data = buffer.getvalue()
        base64_data = base64.b64encode(binary_data).decode('utf-8')
        return base64_data

        