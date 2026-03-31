# arise-care

## 项目概述

康复策略训练忠实度自动评估系统（Arise Care）。基于匹兹堡大学论文，自动识别康复训练中治疗师的语言提示类型，支持音频上传转录和文本分类。

- 论文1 (paper/2115.pdf)：NLP 自动识别 guided/directed 语言提示
- 论文2 (paper/Feasibility...pdf)：深度学习识别手势提示（后续阶段）

## 分类类别

- **DIRECTED**: 明确的指令、命令、示范，直接告诉患者做什么
- **GUIDED**: 引导性的提问或提示，鼓励患者自己思考或决定
- **NONE**: 闲聊、观察、解释，不涉及指导或引导行为

## 架构

```
浏览器 → FastAPI (localhost:8000) → llama-cpp-python (gguf) → 分类结果
                                  → faster-whisper (ASR) → 转录文本
```

### 旧版（保留参考）
- `server.js` — Node.js 原型，调用 Ollama API
- `index.html` — 原始前端

### 新版
- `app/main.py` — FastAPI 入口
- `app/services/classifier.py` — llama-cpp-python 直接加载 gguf 推理
- `app/services/asr.py` — faster-whisper + whisperX diarization
- `app/services/pipeline.py` — 音频 → 转录 → 分类 → 报告
- `app/static/index.html` — 前端页面
- `config.py` — 配置（模型路径等）

## 模型相关

- 模型文件: `C:\Users\del\.ollama\custom\qwen_bala_Q5_K_M.gguf`（Q5_K_M 量化，5.2GB）
- 原始模型: Qwen2.5-7B-Instruct 微调，从 fp16 量化而来
- Ollama 模型名: `qwen-bala`（旧版用）

## 技术栈

- **后端**: Python + FastAPI
- **分类推理**: llama-cpp-python（直接加载 gguf，不依赖 Ollama）
- **ASR**: faster-whisper（本地 Whisper）
- **说话人分离**: whisperX + pyannote
- **前端**: vanilla HTML/CSS/JS
- **未来打包**: Tauri（闭源桌面应用）

## 启动

```bash
# 新版
uvicorn app.main:app --reload
# 访问 http://localhost:8000

# 旧版（仍可用，需 Ollama 运行）
node server.js
# 访问 http://localhost:3000
```

## API

```
POST /api/classify
Body: { "text": "治疗师话语" }
Response: { "input": "...", "classification": "DIRECTED|GUIDED|NONE" }

POST /api/transcribe
Body: multipart/form-data, file=音频文件
Response: { "segments": [...], "speakers": [...] }
```

## 已知问题

- NONE 类分类不够准：跟康复相关的观察/评价容易误判为 GUIDED
- llama-cpp-python 在 Windows 上需要预编译 wheel
