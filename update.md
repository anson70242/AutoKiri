## 已完成
1. 分切后的SRT命名: [Part-N]XXX (Done)
2. 支持Twitter Space下载 (Done wait for test)
3. 影片标题前面加上[平台] (Done) — 实现在 src/downloader/base.py 的 generate_output_path()
4. yt-dlp自动更新 (Done) — Nightly 通道，每个进程只检查一次

---

## 待办
1. 机翻SRT供剪辑使用
   - 曾以 LLM 翻译 agent 实现 (commit c8ba152: src/agents/ + config 的 agents 段 + vocab 词表)，现已回退
   - 重做时需一并恢复：requirements.txt 的 requests、config 的 translater / translater_glossary 路径
2. 自动路灯

---

## 备注
- LLM 精华分析目前是**人工步骤**：程序只负责产出 SRT 切片并把 speech_analyze.md / to_excel.md
  部署到字幕旁边，投喂给模型由人工完成 (src/core/pipeline.py 的 HighlightPipeline)
- src/trigger/ 下的开播轮询模块尚未接入任何 EXE 入口
