# AutoKiri

AutoKiri 是一个专为直播回放（Archive/VOD）设计的自动化工具，支持 **YouTube、Twitch、TwitCasting** 平台。它可以一键完成视频下载、弹幕抓取与清洗、语音识别（Whisper）以及 AI 精华片段分析预处理。

## 🌟 核心功能

* **多平台支持**：完整支持 YouTube、Twitch、TwitCasting 的视频与信息提取。
* **智能下载**：自动处理 YouTube 会员限定视频（需 Cookie）与 Twitch 订阅者限定视频（需 OAuth）。
* **弹幕清洗**：将复杂的原始弹幕格式转换为标准化的 JSON 格式，方便后续分析。
* **AI 精华预处理**：利用 Faster-Whisper 生成高质量字幕，并自动部署 AI 分析所需的 Prompt。
* **自动分段**：自动检测并切割超过 10GB 的超大视频文件，适应QQ闪存。

## 已知问题
1. YouTube聊天室处理需时，直播结束没法马上取得，目前建议后续使用`down_chat.exe`重新下载
2. TwitCasting聊天室抓取功能实现较为复杂，目前不支援

## ⚡ 快速开始 (EXE 版本)
1. 配置文件：将 `.env.example` 重命名为 `.env`(不需加任何前缀) 并填入你的 `Twitch Token`。
2. 对于 YouTube 会员限定影片，`请下载firefox浏览器并登入Youtube账号`
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

### 2. AI 功能增强 (可选)

如果你需要使用 AI 精华提取功能（语音转文字），必须手动下载 Whisper 引擎：

1. 下载：[Faster-Whisper-XXL (Standalone Windows)](https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r245.4_windows.7z)
2. 在项目根目录下创建 `tools` 文件夹。
3. 将下载的压缩包解压至 `tools/Faster-Whisper-XXL/` 路径下，确保 `faster-whisper-xxl.exe` 位于该目录内。

### 3. YouTube 会员限定视频

对于 YouTube 会员限定影片，`请下载firefox浏览器并登入Youtube账号`

---

## 🚀 使用说明

本项目已封装为以下 5 个主要执行程序（EXE）：

### 1️⃣ `AutoKiri-Main.exe` (全流程模式)

**功能**：一站式服务。

* 输入直播链接。
* 程序会自动：解析元数据 -> 下载视频 -> 下载并清洗弹幕 -> 视频切割（如有必要） -> 执行 Whisper 语音识别 -> 部署 AI 分析 Prompt。

### 2️⃣ `AutoKiri-Download.exe` (仅影片模式)

**功能**：下载直播视频，抓取弹幕，不进行 AI 分析。

### 3️⃣ `AutoKiri-DownVideo.exe` (仅影片模式)

**功能**：只下载直播视频，不抓取弹幕，不进行 AI 分析。适合只需要收藏回放的用户。

### 4️⃣ `AutoKiri-DownChat.exe` (仅弹幕模式)

**功能**：只抓取并清洗弹幕，生成可读性高的 JSON 文件。适合已下载视频，只需补全弹幕数据的场景。

### 5️⃣ `AutoKiri-Highlight.exe` (仅 AI 分析模式)

**功能**：对本地已有的视频进行处理。

* 运行后输入本地视频的绝对路径。
* 程序将直接开始：语音转文字 -> 字幕分段 -> 部署 AI 任务文件。

---

## 📂 项目结构

```text
└── anson70242-autokiri/
    ├── main.exe            # 全流程执行
    ├── video_chat.py       # 下载视频+弹幕
    ├── down_video.exe      # 仅下载视频
    ├── down_chat.exe       # 仅下载弹幕
    ├── clip_highlight.exe  # 仅本地AI分析
    ├── config.yaml         # 全局配置 (主播ID、Whisper参数等)
    ├── .env                # 个人机密配置 (Twitch OAuth)
    ├── tools/              # 存放 ffmpeg, yt-dlp, Faster-Whisper 等工具
    └── videos/             # 默认输出文件夹，按 主播/日期/标题 分类存放

```

---

## ⚖️ 许可证

本项目采用 **GNU Affero General Public License v3.0 (AGPL-3.0)** 协议授权。

## ⚠️ 注意事项

* 请确保你的网络环境可以正常访问对应的直播平台。
* 如果下载速度缓慢，可以在 `config.yaml` 中调整 `yt-dlp` 的相关参数。
* 第一次运行 AI 分析时，模型加载可能需要较长时间，请耐心等待。