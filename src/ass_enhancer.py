import re
import subprocess
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import librosa
import yaml
import scipy.io.wavfile


class ConfigLoader:
    """Handle configuration loading and management."""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or self._default_config_path()
        self.config: Dict[str, Any] = {}
    
    @staticmethod
    def _default_config_path() -> Path:
        return Path(__file__).parent.parent / "config.yaml"
    
    def load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        return self.config
    
    def get_whisper_config(self) -> Dict[str, Any]:
        return self.config.get("whisper", {})
    
    def get_faster_whisper_path(self) -> str:
        return self.config.get("tools_paths", {}).get("faster_whisper")


class TimeConverter:
    """Handle time format conversions."""
    
    TIME_PATTERN = re.compile(r"(\d+):(\d{2}):(\d{2})\.(\d{2})")
    
    @classmethod
    def ass_to_seconds(cls, time_str: str) -> float:
        match = cls.TIME_PATTERN.match(time_str.strip())
        if not match:
            raise ValueError(f"Invalid ASS time format: {time_str}")
        hours, minutes, seconds, centiseconds = match.groups()
        return (int(hours) * 3600 + int(minutes) * 60 + 
                int(seconds) + int(centiseconds) / 100)
    
    @classmethod
    def seconds_to_ass(cls, seconds: float) -> str:
        total_seconds = int(seconds * 100)
        hours = total_seconds // 360000
        minutes = (total_seconds % 360000) // 6000
        secs = (total_seconds % 6000) // 100
        centisecs = total_seconds % 100
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


class ASSParser:
    """Parse and manipulate ASS subtitle files."""
    
    def __init__(self, ass_path: Path):
        self.ass_path = ass_path
        self.lines: List[str] = []
        self.events: List[Dict[str, Any]] = []
    
    def parse(self) -> Tuple[List[str], List[Dict[str, Any]]]:
        with open(self.ass_path, "r", encoding="utf-8") as f:
            self.lines = f.readlines()
        
        self.events = []
        in_events = False
        
        for line in self.lines:
            if line.startswith("[Events]"):
                in_events = True
                continue
            elif line.startswith("[") and in_events:
                break
            
            if in_events and line.startswith("Dialogue:"):
                event = self._parse_dialogue_line(line)
                if event:
                    self.events.append(event)
        
        return self.lines, self.events
    
    def _parse_dialogue_line(self, line: str) -> Dict[str, Any]:
        parts = line.split(",", 9)
        if len(parts) < 9:
            return None
        
        return {
            "line": line,
            "line_index": self.lines.index(line),
            "start": TimeConverter.ass_to_seconds(parts[1]),
            "end": TimeConverter.ass_to_seconds(parts[2]),
            "original_text": parts[8] if len(parts) > 8 else ""
        }
    
    def update_event_text(self, event: Dict[str, Any], new_text: str):
        parts = event["line"].rstrip("\n").split(",", 9)
        if len(parts) >= 9:
            old_text = parts[8]
            new_text_value = old_text + " " + new_text if old_text else new_text
            parts[8] = new_text_value
            new_line = ",".join(parts) + "\n"
            self.lines[event["line_index"]] = new_line
    
    def write(self, output_path: Path):
        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(self.lines)


class AudioProcessor:
    """Handle audio loading and chunk extraction."""
    
    def __init__(self, video_path: Path, sample_rate: int = 16000):
        self.video_path = video_path
        self.sample_rate = sample_rate
        self.audio_data = None
    
    def load(self):
        print(f"Loading audio from {self.video_path}...")
        self.audio_data, self.sample_rate = librosa.load(
            self.video_path, sr=self.sample_rate
        )
        print(f"Audio loaded: {len(self.audio_data)} samples at {self.sample_rate}Hz")
    
    def extract_chunk(self, start_sec: float, end_sec: float) -> str:
        start_sample = int(start_sec * self.sample_rate)
        end_sample = int(end_sec * self.sample_rate)
        chunk = self.audio_data[start_sample:end_sample]
        
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_file.close()
        
        scipy.io.wavfile.write(temp_file.name, self.sample_rate, chunk)
        
        return temp_file.name


class WhisperTranscriber:
    """Handle transcription using Faster-Whisper."""
    
    def __init__(self, config: ConfigLoader):
        self.config = config
        self.whisper_path = config.get_faster_whisper_path()
        
        if not self.whisper_path or not os.path.exists(self.whisper_path):
            raise FileNotFoundError(
                f"Faster-Whisper executable not found: {self.whisper_path}"
            )
    
    def transcribe(self, audio_path: str) -> str:
        whisper_config = self.config.get_whisper_config()
        
        cmd = [self.whisper_path, audio_path]
        
        if whisper_config.get("language"):
            cmd.extend(["--language", whisper_config["language"]])
        if whisper_config.get("model"):
            cmd.extend(["--model", whisper_config["model"]])
        if whisper_config.get("compute_type"):
            cmd.extend(["--compute_type", whisper_config["compute_type"]])
        if whisper_config.get("beam_size"):
            cmd.extend(["--beam_size", str(whisper_config["beam_size"])])
        
        cmd.extend(["--condition_on_previous_text", "False"])
        
        temp_srt = tempfile.NamedTemporaryFile(suffix=".srt", delete=False)
        temp_srt.close()
        cmd.extend(["--output_file", temp_srt.name])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Warning: Whisper failed: {result.stderr}")
                return ""
            
            with open(temp_srt.name, "r", encoding="utf-8") as f:
                srt_content = f.read()
            
            return self._extract_text_from_srt(srt_content)
        
        finally:
            if os.path.exists(temp_srt.name):
                os.remove(temp_srt.name)
    
    def _extract_text_from_srt(self, srt_content: str) -> str:
        lines = srt_content.strip().split("\n")
        text_lines = []
        for line in lines:
            if line and not re.match(r"^\d+$|^\d{2}:\d{2}:\d{2}", line):
                text_lines.append(line.strip())
        return " ".join(text_lines)


class ASSEnhancer:
    """Main class to enhance ASS files with ASR."""
    
    def __init__(self, video_path: Path, ass_path: Path):
        self.video_path = Path(video_path)
        self.ass_path = Path(ass_path)
        self.config = None
        self.audio_processor = None
        self.transcriber = None
        self.ass_parser = None
    
    def _initialize(self):
        self.config = ConfigLoader()
        self.config.load()
        
        self.audio_processor = AudioProcessor(self.video_path)
        self.audio_processor.load()
        
        self.transcriber = WhisperTranscriber(self.config)
        self.ass_parser = ASSParser(self.ass_path)
        self.ass_parser.parse()
    
    def enhance(self, output_ass_path: Path):
        self._initialize()
        
        print(f"Parsing {self.ass_path}...")
        print(f"Found {len(self.ass_parser.events)} subtitle events")
        
        for i, event in enumerate(self.ass_parser.events):
            print(f"Processing event {i+1}/{len(self.ass_parser.events)}: "
                  f"{event['start']:.2f}s - {event['end']:.2f}s")
            
            temp_audio = self.audio_processor.extract_chunk(
                event["start"], event["end"]
            )
            
            try:
                recognized_text = self.transcriber.transcribe(temp_audio)
                
                if recognized_text:
                    self.ass_parser.update_event_text(event, recognized_text)
            finally:
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)
        
        print(f"Writing output to {output_ass_path}...")
        self.ass_parser.write(output_ass_path)
        print("Done!")


def main():
    import sys
    
    if len(sys.argv) != 4:
        print("Usage: python ass_enhancer.py <video_path> <ass_path> <output_ass_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    ass_path = sys.argv[2]
    output_ass_path = sys.argv[3]
    
    enhancer = ASSEnhancer(video_path, ass_path)
    enhancer.enhance(Path(output_ass_path))


if __name__ == "__main__":
    main()
