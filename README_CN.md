# AutoKiri

AutoKiri 是一个专为直播回放（Archive/VOD）设计的自动化工具，支持 **YouTube、Twitch、TwitCasting、Twitter(X) Space** 平台。它可以一键完成视频下载、弹幕抓取与清洗、语音识别（Whisper），并为后续的人工 AI 分析准备好素材。

## 🌟 核心功能

* **多平台支持**：完整支持 YouTube、Twitch、TwitCasting 的视频与信息提取，以及 Twitter(X) Space 的音频下载。
* **智能下载**：自动处理 YouTube 会员限定视频（需 Cookie）与 Twitch 订阅者限定视频（需 OAuth）。
* **弹幕清洗**：将复杂的原始弹幕格式转换为标准化的 JSON 格式，方便后续分析。
* **语音识别**：调用 Faster-Whisper-XXL 生成高质量 SRT 字幕，参数可在 `config.yaml` 中细调。
* **AI 分析素材准备**：自动将过长的 SRT 均分切片（`[Part-N]XXX.srt`），并把分析用的 Prompt 文件一并放到字幕旁边，方便你直接投喂给 LLM。
* **自动分段**：自动检测并切割超过 10GB 的超大视频文件，适应QQ闪存。
* **yt-dlp 自动更新**：每次下载任务开始前，自动将内置的 yt-dlp 更新至 Nightly 版本，减少因平台改版导致的下载失败。

> ℹ️ **关于「AI 分析」的职责边界**
> 本程序**不会**自动调用 LLM。它负责跑完「语音识别 → 字幕切片 → 部署 Prompt」，
> 最后一步（把 SRT 与 Prompt 投喂给 Gemini 等模型做精华分析）由**人工**完成。

## 已知问题
1. YouTube聊天室处理需时，直播结束没法马上取得，目前建议后续使用`AutoKiri-DownChat.exe`重新下载
2. TwitCasting聊天室抓取功能实现较为复杂，目前不支援
3. Twitter(X) Space 为纯音频直播，无弹幕抓取

## ⚡ 快速开始 (EXE 版本)
1. 配置文件：将 `.env.example` 重命名为 `.env`(不需加任何前缀) 并填入你的 `Twitch Token`。
   - `.env` 需与 EXE 放在**同一个目录**下，程序会以 EXE 所在位置去寻找它。
2. 对于 YouTube 会员限定影片，`请下载firefox浏览器并登入Youtube账号`
    - (Chrome, Edge目前不支援自动获取Cookie)
3. 运行：双击 `AutoKiri-Main.exe`，粘贴直播链接，按下回车。

## 🛠️ 环境准备与安装

为了确保程序正常运行，请按以下步骤配置环境：

### 1. 基础配置 (.env)

在程序根目录下建立一个名为 `.env` 的文件(不需加任何前缀)，并填入你的 Twitch 授权信息：

```env
twitch_OAuth="你的TwitchOAuth"
```

**如何获取 Twitch OAuth？**

1. 在浏览器登录 Twitch 账号，并打开 Twitch 页面。
2. 按下 `F12` 打开开发者工具。
3. 点击 **应用程序 (Application)** 选项卡 -> 左侧 **Cookies** -> 找到 `https://www.twitch.tv`。
4. 在列表中找到名为 `auth-token` 的值，将其复制到 `.env` 文件中。

### 2. 语音识别引擎 (可选)

如果你需要使用语音转文字功能，必须手动下载 Whisper 引擎（该目录体积较大，未随源码一同发布）：

1. 下载：[Faster-Whisper-XXL (Standalone Windows)](https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r245.4_windows.7z)
2. 在项目根目录下创建 `tools` 文件夹。
3. 将下载的压缩包解压至 `tools/Faster-Whisper-XXL/` 路径下，确保 `faster-whisper-xxl.exe` 位于该目录内。

> 该引擎为绿色版，自带运行时，**无需安装 Python 或 CUDA 环境**。

### 3. YouTube 会员限定视频

对于 YouTube 会员限定影片，`请下载firefox浏览器并登入Youtube账号`

### 4. 从源码运行 (开发者)

```bash
pip install -r requirements.txt
python main.py
```

依赖极少（`PyYAML`、`python-dotenv`），因为 ffmpeg / yt-dlp / Whisper 等重型组件全部以独立可执行文件的形式放在 `tools/` 下，由程序以子进程方式调用。

---

## 🎚️ 语音识别配置

语音识别的全部参数集中在 `config.yaml` 的 `whisper:` 段：

```yaml
whisper:
  language: "ja"                     # 识别语言
  model: "large-v3-turbo"            # 使用的模型
  compute_type: "float16"            # 计算精度；显存不足可改 int8_float16 或 int8
  beam_size: 5                       # 集束搜索宽度，越大越准、越慢
  vad_filter: False                  # 是否启用 VAD 静音过滤
  condition_on_previous_text: False  # 关闭可显著减少长视频的"复读机"幻觉
  no_speech_threshold: 0.5           # 无语音判定阈值
  vad_threshold: 0.35                # VAD 语音判定阈值（仅 vad_filter 为 True 时生效）
  vad_min_speech_duration_ms: 250    # 最短语音片段时长（仅 vad_filter 为 True 时生效）
```

**关于更换模型**

模型文件存放在 `tools/Faster-Whisper-XXL/_models/` 下，每个子文件夹是一个模型，
内含标准的 CTranslate2 格式文件（`model.bin`、`config.json`、`tokenizer.json`、`vocabulary.json`）。

内置的 `faster-whisper-large-v3-turbo/` 对应上面的 `model: "large-v3-turbo"`。
更换模型只需修改 `model:` 这一行，**无需改动任何代码**；
若要使用官方列表之外的模型，需先将其转换为 CTranslate2 格式后放入 `_models/`。

---

## 🚀 使用说明

本项目已封装为以下 5 个主要执行程序（EXE）：

### 1️⃣ `AutoKiri-Main.exe` (全流程模式)

**功能**：一站式服务。

* 输入直播链接。
* 程序会自动：更新 yt-dlp -> 解析元数据 -> 下载视频 -> 下载并清洗弹幕 -> 视频切割（如有必要） -> 执行 Whisper 语音识别 -> 切割字幕并部署 Prompt。

### 2️⃣ `AutoKiri-Download.exe` (下载模式：影片 + 弹幕)

**功能**：下载直播视频**并**抓取、清洗弹幕，不进行语音识别。

### 3️⃣ `AutoKiri-DownVideo.exe` (仅影片模式)

**功能**：只下载直播视频，不抓取弹幕，不进行语音识别。适合只需要收藏回放的用户。

### 4️⃣ `AutoKiri-DownChat.exe` (仅弹幕模式)

**功能**：只抓取并清洗弹幕，生成可读性高的 JSON 文件。适合已下载视频，只需补全弹幕数据的场景。

### 5️⃣ `AutoKiri-Highlight.exe` (仅语音识别模式)

**功能**：对本地已有的视频进行处理。

* 运行后输入本地视频的绝对路径。
* 程序将直接开始：语音转文字 -> 字幕分段 -> 部署 Prompt 文件。

---

## 📂 项目结构

```text
└── anson70242-autokiri/
    ├── AutoKiri-Main.exe      # 全流程执行
    ├── AutoKiri-Download.exe  # 下载视频+弹幕
    ├── AutoKiri-DownVideo.exe # 仅下载视频
    ├── AutoKiri-DownChat.exe  # 仅下载弹幕
    ├── AutoKiri-Highlight.exe # 仅本地语音识别
    ├── config.yaml            # 全局配置 (主播ID、Whisper参数、工具路径等)
    ├── .env                   # 个人机密配置 (Twitch OAuth)
    ├── tools/                 # 存放 ffmpeg, yt-dlp, Faster-Whisper 等工具
    ├── logs/                  # 运行日志
    └── videos/                # 默认输出文件夹，按 主播/日期/标题 分类存放
```

### 输出命名规则

任务目录为 `videos/{主播}/{日期}/{标题}_[{视频ID}]/`，
目录内的文件统一采用 `[平台][日期][主播] 标题` 前缀，方便混放后仍能一眼分辨来源：

```text
videos/Yuka/20250109/直播标题_[dQw4w9WgXcQ]/
├── [youtube][20250109][Yuka] 直播标题.mp4              # 影片本体（Twitter Space 为 .wav）
├── [youtube][20250109][Yuka] 直播标题_chat.json        # 原始弹幕
├── [youtube][20250109][Yuka] 直播标题_chat_parsed.json # 清洗后的弹幕
├── [youtube][20250109][Yuka] 直播标题.srt              # Whisper 生成的完整字幕
├── [Part-1][youtube][20250109][Yuka] 直播标题.srt      # 均分切片后的字幕（超长时才有）
├── 直播标题_source_link.txt                            # 来源链接备忘
├── speech_analyze.md                                   # 已部署的分析 Prompt（供人工投喂 LLM）
└── to_excel.md                                         # 已部署的整理 Prompt（供人工投喂 LLM）
```

> 注：YouTube 的原始弹幕由 yt-dlp 产出，实际扩展名为 `.live_chat.json`；清洗后统一为 `_chat_parsed.json`。

---

## ⚖️ 许可证

本项目采用 **GNU Affero General Public License v3.0 (AGPL-3.0)** 协议授权。

## ⚠️ 注意事项

* 请确保你的网络环境可以正常访问对应的直播平台。
* 如果下载速度缓慢，可以在 `config.yaml` 中调整 `yt-dlp` 的相关参数。
* 第一次运行语音识别时，模型加载可能需要较长时间，请耐心等待。
* 若已存在同名 `.srt` 文件，语音识别会自动跳过，方便中断后续跑。
