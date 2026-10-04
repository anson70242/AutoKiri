<div align="center">

# AutoKiri (自動切片 / Stream Highlight Clipper)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Supported-green.svg)](https://ffmpeg.org/)
[![GitHub stars](https://img.shields.io/github/stars/anson70242/AutoKiri?style=social)](https://github.com/anson70242/AutoKiri)

[**中文說明 / Chinese Documentation**](https://github.com/anson70242/AutoKiri/blob/main/README_CN.md) | **English**

<p align="center">
  An automated pipeline for live-stream downloading, highlight detection, speech recognition (ASR), and subtitle generation for VTuber and stream clips (切り抜き).
</p>

</div>

---

## 📖 Overview

**AutoKiri** is an end-to-end automation toolkit built to simplify and accelerate the process of creating stream highlights (*kirinuki* / 切片). It automates stream downloading, chat density analysis, audio transcription via state-of-the-art ASR models, and subtitle synchronization, turning hours of raw stream footage into ready-to-edit clips.

---

## ✨ Features

- **Automated Stream Ingestion:** Download complete VODs or live streams with metadata and synchronized chat logs via `yt-dlp`.
- **Smart Highlight Detection:** Detect entertaining or climactic moments based on chat activity, audio energy levels, or manual timestamp markers.
- **Accurate Speech-to-Text (ASR):** Integrated with OpenAI Whisper / Faster-Whisper for high-accuracy multilingual transcription (Japanese, Traditional Chinese, English, etc.).
- **Subtitle Generation & Styling:** Automatically align timestamps and export clean `.srt` or styled `.ass` subtitle files.
- **Vocal & Background Separation:** Optional Demucs integration to filter out background game audio or BGM for crisper voice recognition.
- **Configurable Pipeline:** Tweak clipping thresholds, silence detection, model sizes, and output formats through a unified configuration file.

---

## 📁 Repository Structure

```text
AutoKiri/
├── core/
│   ├── downloader.py       # Stream and chat log fetcher (yt-dlp wrapper)
│   ├── detector.py         # Highlight & peak activity detector
│   ├── transcriber.py      # Whisper / Faster-Whisper speech recognition
│   └── subtitle.py         # Subtitle styling (.srt / .ass) and alignment
├── utils/
│   ├── audio.py            # FFmpeg audio extraction, normalization & splitting
│   └── logger.py           # Logging utilities
├── config/
│   └── config.yaml         # Pipeline configurations and parameters
├── main.py                 # Pipeline entry point
├── requirements.txt        # Python dependency list
├── README.md               # English README
└── README_zh.md            # Chinese README
```

---

## 🛠️ Prerequisites

Ensure the following tools and runtimes are installed before running AutoKiri:

1. **Python 3.10+**
2. **FFmpeg & FFprobe:** Installed and accessible in your system's `PATH`.
   - **Ubuntu/Debian:** `sudo apt install ffmpeg`
   - **macOS:** `brew install ffmpeg`
   - **Windows:** Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or install via `winget install Gyan.FFmpeg`.
3. **NVIDIA GPU with CUDA (Recommended):** Greatly speeds up Whisper transcription and model inference.

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/anson70242/AutoKiri.git
cd AutoKiri
```

### 2. Create a Virtual Environment & Install Dependencies

```bash
# Optional: create a virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure the Pipeline

Copy or edit `config/config.yaml` to specify your preferred settings:

```yaml
general:
  output_dir: "./outputs"
  temp_dir: "./temp"

asr:
  model_name: "large-v3"    # tiny, base, small, medium, large-v3
  device: "cuda"            # "cuda" or "cpu"
  compute_type: "float16"   # "float16", "int8", or "float32"
  language: "ja"            # Target language (e.g., ja, zh, en)

clipping:
  chat_spike_threshold: 2.5 # Multiplier over average chat rate to trigger clip
  min_clip_duration: 30     # Minimum duration in seconds
  max_clip_duration: 180    # Maximum duration in seconds
```

---

## 💻 Usage

### Full Automated Pipeline

Run the full pipeline on a stream URL:

```bash
python main.py --url "https://www.youtube.com/watch?v=EXAMPLE_ID"
```

### Process an Existing Local Video

```bash
python main.py --input "path/to/vod.mp4" --output "./outputs"
```

### Run Subtitle Generation Only

```bash
python core/transcriber.py --input "path/to/clip.mp4" --format ass --model large-v3
```

---

## 🗺️ Roadmap

- [ ] Web-based UI (Gradio / Streamlit) for interactive timeline reviewing.
- [ ] Direct export to video editor project formats (e.g., DaVinci Resolve `.edl` / Premiere XML).
- [ ] Multi-platform chat support (Twitch IRC, YouTube Live, Bilibili Danmaku).
- [ ] Automatic face tracking and vertical format (9:16) reframing for TikTok / YouTube Shorts.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!  
Feel free to open an issue or submit a pull request on the [GitHub repository](https://github.com/anson70242/AutoKiri/issues).

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
