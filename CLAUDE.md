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

## 项目状态（截至 2026-04-17）

| Phase | 内容 | 状态 |
|-------|------|------|
| P1 | 后端骨架 + 文本分类迁移 | ✅ 完成 |
| P2 | 音频转录 + 说话人分离（faster-whisper + pyannote） | ✅ 完成 |
| P3 | 完整 Pipeline + 统计报告 | ✅ 完成 |
| P4 | 前端完善（UI/导出/历史/Cancel） | ✅ 完成 |
| P5 | Pipeline 评估 + GPU 加速 + 重叠匹配 | ✅ 完成 |
| P6 | Pipeline 优化（进度追踪/分类加速/子句拆分） | ⬜ 待做 |
| P7 | Cue 输出扩展 + 详细统计（Module B/D） | ⬜ 待确认需求 |
| P8 | 与 SOAP/本体模块集成（Module A/C） | ⬜ 待确认接口 |
| P9 | 打包分发（Tauri 桌面 + 移动端 API） | ⬜ 待开始 |

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
│   │   └── pipeline.py      # POST /api/analyze（完整 pipeline）
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

## 团队与分工（2026-04-15 会议）

| 成员 | 模块 | 职责 |
|------|------|------|
| Yanshan Wang | 全局 | 技术 PI / 统筹 |
| Beth Skidmore | 全局 | 临床 PI |
| Jay | Module B/D | Verbal Cue 识别 + 定量统计 |
| Maneesh Bilalpur | Module A | SOAP Note 生成（John Snow Labs） |
| Manoj | Module C | 概念抽取 + 本体映射（ICF/NCBO/CPT） |
| Katie, May | 数据 | 临床标注 |

### Module B/D 待扩展（Jay 负责）

- Cue 输出格式：需加 `cue_id`、`duration`、`linked_concepts`（对接 Module C）
- 统计指标：需加每类 cue 的 `mean/min/max/range` 时长、delta proportion（干预前后对比）
- 待确认：NONE 类是否保留、cue 边界精度（词级 vs 句级）、session 划分规则

## Pipeline 评估结果（2026-04-15）

- 测试音频：30 分钟康复对话，gold standard 44 条 cue（16 GUIDED + 28 DIRECTED）
- **Whisper + qwen-bala：68.2%**（30/44），GUIDED 81.3%，DIRECTED 60.7%
- **AWS 文本 + qwen-bala：29.5%**（13/44），粗切分导致短指令被淹没
- **结论：细粒度切分是关键**，Whisper 按停顿切分比 AWS 按轮次切分准确率高一倍
- **Prompt 改进无效**：qwen-bala 是微调模型，system prompt 定义对分类行为影响极小
- **GPU pyannote**：58 秒 vs CPU 28 分钟（30 倍加速），需 PyTorch GPU 版
- **ASR 质量**：Whisper WER 93% vs AWS 8%（对比 gold standard），但 gold standard 文本基于 AWS 转录，对比原始音频 Whisper 实际更准确。WER 高是参照物问题，不是 Whisper 差
- 主要问题：短指令在长句中被淹没 + 微调数据短指令样本不足
- **分类瓶颈**：每条 utterance 独立调一次 Ollama API（system prompt + user message），200 条 × ~2s ≈ 400s，占总耗时 80%+
- 改进方向（按优先级）：
  1. post-ASR 子句拆分（提升准确率，最有效）
  2. 分类加速：批量打包多条 utterance 一次调用 / 蒸馏到 1.5B-3B 小模型 / 换 BERT 级分类器（毫秒级）
  3. 补充短指令训练数据
- 详细报告：`test/report.md`

## 已知问题 / 坑

- 🐛 短指令误判：短指令（"breathe"、"right here"）在 Whisper 长句中被淹没标为 NONE，改 prompt 无效，需 post-ASR 子句拆分或补充训练数据
- 🐛 NONE 类误判：康复相关观察/评价容易被分为 GUIDED（微调数据 NONE 样本不足）
- ⚠️ faster-whisper GPU 已启用（pip nvidia-cublas-cu12，asr.py 动态加载 DLL）
- ⚠️ PyTorch 已切换为 GPU 版（torch 2.4.1+cu121），pyannote GPU 可用（58s vs CPU 28 分钟）
- ⚠️ torch 版本降级到 2.4.1（pyannote 要求 >=2.8 但实际可用）
- ✅ CTranslate2 + PyTorch CUDA 在 uvicorn 进程中可共存（测试脚本中会冲突，但 FastAPI 服务正常）
- ⚠️ torchcodec 在 Windows 不可用，已卸载，音频解码走 PyAV
- GPU 显存分配：Ollama 5.2GB + Whisper + pyannote 不能同时跑，需分时复用（Whisper → 释放 → pyannote → 释放 → Ollama）
- ⏱️ 30 分钟音频全 GPU pipeline 耗时 ~8 分钟（Whisper ~55s + pyannote ~58s + Ollama 分类 ~400s），分类占 80%+
- speaker 对齐用中点匹配（asr.py:91），GPU pyannote 已消除所有 UNKNOWN 标签
