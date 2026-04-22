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

## 项目状态（截至 2026-04-22）

| Phase | 内容 | 状态 |
|-------|------|------|
| P1 | 后端骨架 + 文本分类迁移 | ✅ 完成 |
| P2 | 音频转录 + 说话人分离（faster-whisper + pyannote） | ✅ 完成 |
| P3 | 完整 Pipeline + 统计报告 | ✅ 完成 |
| P4 | 前端完善（UI/导出/历史/Cancel） | ✅ 完成 |
| P5 | Pipeline 评估 + GPU 加速 + 重叠匹配 | ✅ 完成 |
| P6 | 实时标注（边说边出结果，chunked streaming） | ⬜ 进行中 |
| P7 | Pipeline 优化（进度追踪/分类加速/子句拆分） | ⬜ 待做 |
| P8 | Cue 输出扩展 + 详细统计（Module B/D） | ⬜ 待确认需求 |
| P9 | 与 SOAP/本体模块集成（Module A/C） | ⬜ 待确认接口 |
| P10 | 打包分发（Tauri 桌面 + 移动端 API） | ⬜ 待开始 |

### P6 实时标注设计要点

**数据流**
```
MediaRecorder (chunk ~3–5s)
  → WebSocket /api/stream (binary)
  → faster-whisper transcribe (sync, ~0.5s/chunk)
  → speaker verification（ECAPA embedding cos sim vs 开场 enrollment）
  → 非 therapist：transcript 显示即可
  → therapist：入分类队列 → Ollama 异步分类
  → WebSocket 推回 {utterance_id, cls}
```

**说话人识别：Enrollment + Verification（不走在线 pyannote）**
- **不用在线 pyannote 的原因**：pyannote 是全局聚类器，标签不跨 chunk 对齐（chunk1 的 SPEAKER_00 可能 ≠ chunk2 的 SPEAKER_00），且需要攒够数据才稳定
- **Enrollment（不是训练）**：用预训练的冻结 speaker encoder（ECAPA-TDNN，`pyannote/embedding` 或 `resemblyzer`），把开场 ~8s therapist 音频过一遍拿到参考向量
- **Verification**：每句 ASR 出来后切对应音频 → 提 embedding → 与参考向量算 cosine，过阈值（0.65–0.75）即 therapist
- **稳定性增强**：用 running average 在高置信句子上持续更新 therapist 向量，抗声音状态变化
- **预期精度**：二分类 EER 2–12%（取决于音质），通常 ≥ pyannote 离线 DER，且没有标签漂移问题
- **兜底**：录完后可选跑一遍离线完整 pipeline，覆盖实时结果用于最终报告

**采集与延迟**
- 浏览器 MediaRecorder 分 chunk 录，每 chunk 是完整 WebM/Opus blob（stop/start 方式避免 EBML header 问题）
- 服务端对每 chunk 用 PyAV 读 duration，累积 elapsed 作为 utterance 时间戳基准
- 端到端延迟预算：chunk 3s + ASR 0.5s + classify 2s ≈ 5.5s 可见分类结果

**UI**
- 新增 "Live" 页，保留原 Upload 页不变
- 流程：点 Start → 弹出"请说几句话做 enrollment（8s）" → 正式录音 → transcript 流式追加，badge 先显示 `…` 占位、分类完成后替换
- 统计面板边说边刷新（沿用现有 Directed/Guided 统计口径）

**GPU 共存**
- Whisper（small/fp16 ~2GB）+ pyannote-embedding（~200MB）+ Ollama qwen-bala（5.2GB）总计 ~7.5GB，当前显存够
- 代码不做显式调度，OOM 再加：Ollama 请求带 `keep_alive: 0` 分类完立即卸载

**里程碑**

| | 内容 | 状态 |
|---|---|---|
| M1 | 后端 WS + ASR + 异步分类（全语音当 therapist） | 🟡 骨架 |
| M2 | 前端 Live 页 + MediaRecorder 分片 + 流式 UI | ⬜ |
| M3 | Enrollment + speaker verification | ⬜ |
| M4 | 离线兜底（录完可选跑 `/api/analyze` 覆盖结果） | ⬜ |
| M5 | 延迟/稳定性打磨 | ⬜ |
| M6 | `/api/analyze` 改 WS：推进度 + 前端健康检测（复用 M1 基础设施） | ⬜ |

**WS 消息协议（`/api/stream`）**

Client → Server：binary frame = 完整 WebM/Opus chunk；`"stop"` 结束会话；后续加 `{type:"enrollment_start|enrollment_done"}`（M3）

Server → Client（JSON）：
```
{type:"utterance",       id, start, end, text, speaker?}
{type:"classification",  id, cls:"DIRECTED|GUIDED|NONE"}
{type:"error",           message}
```

**已知坑**
- MediaRecorder codec 不一致：Chrome `webm/opus`，Safari 只支持 `mp4`，需 mimeType 协商
- Enrollment 开场 8s 若有噪声参考向量偏，UI 上要提示 + 简单 VAD 剔除静音
- Whisper + Ollama + pyannote-embedding 常驻 ≈ 7.5GB，8GB 显存紧张

**待确认**
- chunk 长度（3s 延迟低但每 chunk 信息少，5s 反之）
- enrollment 失败/中途切换 therapist 如何处理
- 单麦 vs 双麦（双麦可跳过 enrollment，走通道区分）

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
- 🐛 Whisper 静音段幻觉（"Okay." / "Ice." 反复逐秒输出）：GPU 非确定性 + `condition_on_previous_text=True` 自反馈放大；运行间结果不稳定。缓解方案 `condition_on_previous_text=False` + `cudnn.deterministic=True`，但未测副作用，暂不改。P6 chunk + VAD 架构会天然规避
- 🐛 NONE 类误判：康复相关观察/评价容易被分为 GUIDED（微调数据 NONE 样本不足）
- ✅ faster-whisper GPU 已启用；`asr.py` 把 `torch/lib/` 加进 PATH 让 CTranslate2 复用 torch bundle 的 `cublas64_12.dll`（Windows 无 RPATH）。不再需要 `nvidia-cublas-cu12` pip 包
- ✅ torch 升到 `2.8.0+cu126`（驱动 CUDA 13.2 向下兼容），满足 pyannote 4.0.4 的 `torch>=2.8` 要求；CTranslate2 4.7.1 + torch 2.8 共存验证通过
- ✅ CTranslate2 + PyTorch CUDA 在 uvicorn 进程中可共存
- ⚠️ torchcodec 被 pyannote 4.0.4 列为必需依赖，但 DLL 在 Windows 加载不了；`asr.py` 用 PyAV 预解码绕过，仅 warning 不影响功能
- ⚠️ pip 23 解析 pyannote 依赖树会 OOM，venv 重建前需先 `pip install --upgrade pip`（>= 24）
- ⚠️ `requirements.txt` 不能含非 ASCII 字符（Windows pip 按 GBK 解码会报错）
- GPU 显存分配：Ollama 5.2GB + Whisper + pyannote 不能同时跑，需分时复用（Whisper → 释放 → pyannote → 释放 → Ollama）
- ⏱️ 30 分钟音频全 GPU pipeline 耗时 ~8 分钟（Whisper ~55s + pyannote ~58s + Ollama 分类 ~400s），分类占 80%+
- speaker 对齐用中点匹配（asr.py:91），GPU pyannote 已消除所有 UNKNOWN 标签
