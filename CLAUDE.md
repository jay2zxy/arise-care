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

## 项目状态（截至 2026-05-05）

| Phase | 内容 | 状态 |
|-------|------|------|
| P1 | 后端骨架 + 文本分类迁移 | ✅ 完成 |
| P2 | 音频转录 + 说话人分离（faster-whisper + pyannote） | ✅ 完成 |
| P3 | 完整 Pipeline + 统计报告 | ✅ 完成 |
| P4 | 前端完善（UI/导出/历史/Cancel） | ✅ 完成 |
| P5 | Pipeline 评估 + GPU 加速 + 重叠匹配 | ✅ 完成 |
| P6 | 实时标注（边说边出结果，chunked streaming） | 🟡 M1/M2/M3 完成，M4-M6 待做 |
| P7 | Pipeline 优化（并发分类 / 子句拆分 / 进度追踪） | ⬜ 待做 |
| P8 | Cue 输出扩展 + 详细统计（Module B/D） | ⬜ 待确认需求 |
| P9 | 与 SOAP/本体模块集成（Module A/C） | ⬜ 待确认接口 |
| P10 | 打包分发（Tauri 桌面 + 移动端 API） | ⬜ 待开始 |

### P6 实时标注设计要点

**数据流**
```
MediaRecorder (chunk ~3–5s)
  → WebSocket /api/stream (binary)
  → faster-whisper transcribe (sync, ~0.5s/chunk)
  → 每条 utterance 切音频 → ECAPA embedding → 存起来（不在线聚类）
  → utterance 推前端，speaker 字段固定 '?' 占位
  → 同时入分类队列 → Ollama 异步分类
  → WebSocket 推回 {utterance_id, cls}
按 Stop:
  → 等分类队列清空
  → sklearn AgglomerativeClustering 一次性聚类全部 embedding
  → 推 speakers_summary { clusters, relabel:{uid->S1/S2} }
  → 前端按 relabel 改写所有 chip + 弹 picker modal 让用户指认 therapist
```

**说话人识别：录中只存 embedding，Stop 后一次性离线聚类**
（演变史见 log.md Session 8：enrollment → 在线贪心 → 全离线，三次方案）
- **算法**：
  ```
  录的时候每条 utterance:
    emb = ECAPA(audio_slice)               # pyannote/embedding, 192-d, L2-normalize
    clusterer.record(uid, emb, dur, text)  # 只存，不分组
    speaker_label_in_message = '?'

  按 Stop（finalize）:
    labels = sklearn.cluster.AgglomerativeClustering(
      n_clusters=2,                       # 强制 2 簇 (1 therapist + 1 patient)
      metric='cosine', linkage='average'
    ).fit_predict(stack(所有 embedding))
    按时间顺序重编号 S1, S2（先出现的人是 S1）
    返回 relabel:{uid -> S1/S2} + summary
  ```
  时间成本：N=200 ~10-30ms，跟 Stop 后等分类队列清空（1-3s）比可忽略。
- **不用 pyannote pipeline-3.1 的原因**：是离线 batch，3 秒 chunk 单独跑标签不跨 chunk 对齐
- **音频切片**：ASR 的 `start/end` 时间戳从原 chunk 切波形；<0.5s 跳过（embedding 不可靠），永远 `?`
- **embedding 模型**：`pyannote/embedding`（ECAPA-TDNN, 192-d），HF gated 模型，HF token 已配；GPU 单例
- **therapist 指认**：录完按 relabel 改 chip + 弹卡片（每簇句数/总时长/采样文本）→ 用户点 → 前端纯渲染过滤统计，零 LLM 重算
- **分类策略**：所有 utterance 不区分 speaker 都送 Ollama，前端按选中簇过滤——切换 therapist 不用回头补跑
- **预期精度**：默认 1 治疗师 + 1 患者，强制 2 簇；3+ 人场景需要把 `DEFAULT_N_CLUSTERS` 调大（或后续加 UI 让用户选）
- **⚠️ 现阶段折中**：硬指定 `n_clusters=2` 是为了规避短句 ECAPA embedding 噪声大、distance_threshold 不稳过分裂的问题（实测 8 句 → 8 簇）。后续要支持任意人数前需要换更稳的方案（如锚点+贴附两阶段，或更鲁棒的 embedding）
- **兜底**：可选跑离线完整 pipeline（M4）覆盖结果

**采集与延迟**
- 浏览器 MediaRecorder 分 chunk 录，每 chunk 是完整 WebM/Opus blob（stop/start 方式避免 EBML header 问题）
- 服务端对每 chunk 用 PyAV 解码一次拿波形 + duration，累积 elapsed 作为 utterance 时间戳基准
- 端到端延迟预算：chunk 3s + ASR 0.5s + 聚类 ~50ms + classify 2s ≈ 5.5s 可见分类结果（聚类几乎不增延迟）

**UI**
- 新增 "Live" 页，保留原 Upload 页不变
- 流程：点 Start → 直接录音（无 enrollment 步骤）→ transcript 流式追加，每条带 `S1/S2/...` 色块 + badge 先 `…` 占位、分类完成后替换
- 录制中统计面板灰显，文案 "Pick therapist after stop"
- 点 Stop → 状态 "Finalizing…"（等剩余分类返回，1-3 秒）→ 弹簇摘要卡片 → 用户点 "Set as therapist" → 统计填入
- 允许重选 therapist（前端纯渲染，瞬时切换）

**GPU 共存**
- Whisper（small/fp16 ~2GB）+ pyannote-embedding（~200MB）+ Ollama qwen-bala（5.2GB）总计 ~7.5GB，当前显存够
- 代码不做显式调度，OOM 再加：Ollama 请求带 `keep_alive: 0` 分类完立即卸载

**里程碑**

| | 内容 | 状态 |
|---|---|---|
| M1 | 后端 WS + ASR + 异步分类（全语音当 therapist） | ✅ |
| M2 | 前端 Live 页 + MediaRecorder 分片 + 流式 UI | ✅ 跑通（截图验证 utterance + badge 替换 + VAD 治幻觉） |
| M3 | ECAPA embedding 边录边存 + Stop 后离线凝聚聚类 + therapist 指认 UI（无在线聚类） | ✅ |
| M4 | 离线兜底（录完可选跑 `/api/analyze` 覆盖结果） | ⬜ |
| M5 | 延迟/稳定性打磨 | ⬜ |
| M6 | `/api/analyze` 改 WS：推进度 + 前端健康检测（复用 M1 基础设施） | ⬜ |

**WS 消息协议（`/api/stream`）**

Client → Server：binary frame = 完整 WebM/Opus chunk；`"stop"` 文本帧 = 结束会话

Server → Client（JSON）：
```
{type:"utterance",         id, start, end, text, speaker:"S1|S2|...|?"}
{type:"classification",    id, cls:"DIRECTED|GUIDED|NONE"}
{type:"speakers_summary",  clusters:[{id, count, total_seconds, samples}], relabel:{uid->S1|S2|...}}  ← Stop 后队列清空 + 离线重聚类
{type:"error",             message}
```

**已知坑**
- MediaRecorder codec 不一致：Chrome `webm/opus`，Safari 只支持 `mp4`，需 mimeType 协商
- 极短 utterance（<0.5s）/ chunk 边界碎片 → embedding 不可靠 → 标 `?` 不参与聚类（不进 therapist 统计）
- Whisper + Ollama + pyannote-embedding 常驻 ≈ 7.4GB，8GB 显存紧张；offline analyze + Live 同进程跑过会双载 ECAPA → 7.6GB

**待确认**
- chunk 长度（3s 延迟低但每 chunk 信息少，5s 反之）
- 多人场景 `DEFAULT_N_CLUSTERS`（默认 2，未来可加 UI 让用户选 2/3）；演变历史见 log.md Session 8
- 单麦 vs 双麦（双麦可跳过聚类，走通道区分）

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
│   │   ├── speaker.py       # ECAPA embedding + 离线凝聚聚类（M3）
│   │   ├── stream.py        # WS 会话：ASR + embedding 收集 + 异步分类 + Stop 离线聚类
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

## Pipeline 评估结果（要点）

详细数据见 `test/report.md` 和 log.md（评估时间 2026-04-15，批处理评估 2026-04-23）。

- **当前基准**：Whisper + qwen-bala 68.2%（30/44，30 分钟康复音频），GUIDED 81.3% / DIRECTED 60.7%
- **核心结论**：细粒度切分（Whisper 按停顿）比粗切分（AWS 按轮次）准确率高一倍——短指令不能被长句淹没
- **优化路线**（按优先级）：
  1. post-ASR 子句拆分（最有效）
  2. 分类加速：单条+并发 `asyncio.gather`（3-5×）/ 蒸馏到 1.5B-3B / 换 BERT 级分类器
  3. 补充短指令训练数据
- **批处理 ❌ 不走**：batch=10 能 8× 但 31% 结果跟单条不一致（qwen-bala 微调是 1-in-1-out，强行批改变分布）
- **prompt 改进无效**：qwen-bala 是微调模型，system prompt 影响极小
- **30min 全 GPU 耗时 ~8 分钟**：Whisper 55s + pyannote 58s + Ollama 分类 400s（占 80%+ 是瓶颈）

## 已知问题 / 坑

**分类质量问题**
- 🐛 短指令误判：短指令（"breathe"、"right here"）在 Whisper 长句中被淹没标为 NONE，改 prompt 无效，需 post-ASR 子句拆分或补充训练数据
- 🐛 NONE 类误判：康复相关观察/评价容易被分为 GUIDED（微调数据 NONE 样本不足）
- 🐛 Whisper 静音段幻觉（"Okay." / "Ice." / "Thank you." 反复逐秒输出）：GPU 非确定性 + `condition_on_previous_text=True` 自反馈放大
  - **streaming 路径已修**：`transcribe(vad_filter=True)` + Silero VAD (`min_silence_duration_ms=500`)
  - **离线 pipeline 未改**：已评估 68.2%，改 VAD 需重评估才动

**环境 / 依赖现状**
- faster-whisper GPU 启用：`asr.py` 把 `torch/lib/` 加进 PATH 让 CTranslate2 复用 torch bundle 的 `cublas64_12.dll`（Windows 无 RPATH）
- torch `2.8.0+cu126` + CTranslate2 4.7.1 + pyannote 4.0.4 共存验证通过
- ⚠️ torchcodec 被 pyannote 列为必需依赖但 Windows DLL 加载不了；`asr.py` 用 PyAV 预解码绕过（warning 不影响功能）
- ⚠️ `requirements.txt` 不能含非 ASCII 字符（Windows pip GBK 解码报错）
- ⚠️ pip < 24 解析 pyannote 依赖树会 OOM
- ⚠️ pyannote 模型是 HF gated repo（`speaker-diarization-3.1` + `embedding`）——每个开发者要自己 HF 账号 + 接受条款 + `HF_TOKEN`
  - **dev 阶段**：维持现状，新成员走一遍 HF 申请
  - **P10 分发前**：换 `speechbrain/spkrec-ecapa-voxceleb`（同 ECAPA 架构 Apache-2.0 无门槛）或 `resemblyzer`（更轻精度低），需重测聚类阈值

**GPU 显存**
- Ollama 5.2GB + Whisper 2GB + pyannote-embedding 0.2GB ≈ 7.4GB；offline + Live 同进程跑过会双载 ECAPA → 7.6GB
- 同进程下三模型共存，但分时执行（uvicorn 单 worker 不并发，自然串行）
- speaker 对齐用中点匹配（`asr.py:91`），GPU pyannote 已消除所有 UNKNOWN 标签
