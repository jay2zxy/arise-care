# Arise Care

**文档**：CLAUDE.md（给 AI 看）| log.md（开发日志）| README.md（项目说明）

---

## 开发规则

### Git 工作流
- 开发分支：`jay-dev`，完成后 PR 到 `main`
- 每次 push 到 `jay-dev`，再创建 PR

### 每个 Phase 完成前必须执行
1. `uvicorn app.main:app --reload` — 服务正常启动
2. API 端点手动测试通过
3. 前端功能验证

---

## 项目状态（截至 2026-04-01）

| Phase | 内容 | 状态 |
|-------|------|------|
| P1 | 后端骨架 + 文本分类迁移 | ✅ 完成 |
| P2 | 音频转录 + 说话人分离（faster-whisper + pyannote） | 🔧 进行中 |
| P3 | 完整 Pipeline + 统计报告 | ⬜ 待开始 |
| P4 | 前端完善（UI/导出/历史） | ⬜ 待开始 |

---

## 架构

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│   浏览器     │────▶│  FastAPI (localhost:8000)                 │
│  static/     │◀────│                                          │
│  index.html  │     │  ┌─────────────┐   ┌─────────────────┐  │
└─────────────┘     │  │ /api/classify│   │ /api/transcribe │  │
                    │  └──────┬──────┘   └───────┬─────────┘  │
                    │         │                   │             │
                    │         ▼                   ▼             │
                    │  ┌─────────────┐   ┌─────────────────┐  │
                    │  │ classifier  │   │ asr.py          │  │
                    │  │ httpx →     │   │ faster-whisper  │  │
                    │  │ Ollama API  │   │ + pyannote(PyAV)│  │
                    │  └─────────────┘   └─────────────────┘  │
                    │                                          │
                    │  ┌──────────────────────────────────┐   │
                    │  │ pipeline.py                       │   │
                    │  │ 音频 → ASR → diarization → 分类  │   │
                    │  │ → 统计报告                        │   │
                    │  └──────────────────────────────────┘   │
                    └──────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────────┐
                    │  Ollama (localhost:11434)                 │
                    │  qwen-bala (Qwen2.5-7B 微调, GPU 加速)    │
                    └──────────────────────────────────────────┘
```

---

## 技术栈

- **后端**: Python + FastAPI + uvicorn
- **分类推理**: Ollama API（开发阶段，GPU 加速；打包时可换 llama-cpp-python）
- **ASR**: faster-whisper（本地 Whisper）
- **说话人分离**: pyannote.audio 4.0 + PyAV（不依赖系统 FFmpeg）
- **前端**: vanilla HTML/CSS/JS
- **打包**: Tauri（闭源桌面应用）

---

## 关键文件

```
arise-care/
├── app/
│   ├── main.py              # FastAPI 入口，静态文件服务
│   ├── routers/
│   │   ├── classify.py      # POST /api/classify（文本分类）
│   │   ├── transcribe.py    # POST /api/transcribe（音频转录）
│   │   └── report.py        # GET /api/report/{session_id}
│   ├── services/
│   │   ├── classifier.py    # httpx 调用 Ollama API 分类
│   │   ├── asr.py           # faster-whisper + pyannote diarization
│   │   └── pipeline.py      # 编排：音频 → 转录 → 分句 → 分类 → 统计
│   ├── models/
│   │   └── schemas.py       # Pydantic 数据模型
│   └── static/
│       └── index.html       # 前端页面
├── legacy/                   # Node.js 原型（参考用）
│   ├── server.js
│   └── index.html
├── config.py                 # Ollama URL、模型名、推理参数
├── requirements.txt
└── paper/                    # 论文（gitignore）
```

---

## 分类类别

- **DIRECTED**: 明确的指令、命令、示范，直接告诉患者做什么
- **GUIDED**: 引导性的提问或提示，鼓励患者自己思考或决定
- **NONE**: 闲聊、观察、解释，不涉及指导或引导行为

## 模型

- Ollama 模型名: `qwen-bala`
- 底层: Qwen2.5-7B-Instruct 微调 → Q5_K_M 量化 gguf（5.2GB）
- 打包分发策略：开发用 Ollama API；未来可蒸馏到小模型（1.5B/3B ~1GB）内嵌分发

## API

```
POST /api/classify
Body: { "text": "治疗师话语" }
Response: { "input": "...", "classification": "DIRECTED|GUIDED|NONE" }

POST /api/transcribe?diarize=false
Body: multipart/form-data, file=音频文件
Response: { "segments": [{"start", "end", "text", "speaker?"}], "speakers?": [...] }
# diarize=true 时返回带说话人标签的转录 + 说话人时间轴
```

## 启动

```bash
# 确保 Ollama 在运行（ollama serve）
uvicorn app.main:app --reload
# http://localhost:8000
```

---

## 已知问题 / 坑

- 🐛 NONE 类误判：康复相关观察/评价容易被分为 GUIDED（微调数据 NONE 样本不足）
- ⚠️ faster-whisper GPU 需要 CUDA 12（cublas64_12.dll），当前缺失，暂用 CPU 模式
- ⚠️ pyannote 依赖 PyTorch（~800MB），打包时用 torch CPU-only 或 ONNX 优化
- ⚠️ torchcodec 在 Windows 不可用，已卸载，音频解码走 PyAV
- GPU 显存分配：Ollama qwen-bala 占 ~5.2GB / 8GB，whisper + pyannote 跑 CPU
- speaker 对齐用中点匹配（asr.py:91），理论上 whisper/pyannote 切分不一致时中点可能落空隙标 UNKNOWN，但康复对话轮次清晰，实际风险低。未来可改用重叠比例匹配
