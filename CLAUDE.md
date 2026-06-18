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

## 项目状态（截至 2026-06-18）

| Phase | 内容 | 状态 |
|-------|------|------|
| P1 | 后端骨架 + 文本分类迁移 | ✅ 完成 |
| P2 | 音频转录 + 说话人分离（faster-whisper + pyannote） | ✅ 完成 |
| P3 | 完整 Pipeline + 统计报告 | ✅ 完成 |
| P4 | 前端完善（UI/导出/历史/Cancel） | ✅ 完成 |
| P5 | Pipeline 评估 + GPU 加速 + 重叠匹配 | ✅ 完成 |
| P6 | 实时标注（重构：live 转录预览 + Stop 整段离线分析） | 🟡 重构完成待实测；旧在线聚类方案废弃 |
| P7 | Pipeline 优化（并发分类 / 子句拆分 / 进度追踪） | ⬜ 待做 |
| P8 | Cue 输出扩展 + 详细统计（Module B/D） | ⬜ 待确认需求 |
| P9 | 与 SOAP/本体模块集成（Module A/C） | ⬜ 待确认接口 |
| P10 | 打包分发（Tauri 桌面 + 移动端 API） | ⬜ 待开始 |

> **2026-06-18 UI 重做**：前端设计系统升级——Fraunces（标题衬线）+ IBM Plex Sans/Mono（正文/数据）、
> teal 强调色（统一 `--accent`，替掉原硬编码蓝）、报告页顶部 **KPI 仪表盘**、**History 改为侧栏导航 + 主区详情**
> （侧栏 Recent Sessions 可折叠列表选 session → 主区详情：Overview + KPI + transcript，可重指派 speaker / 选 therapist / 分页 / 导出，改动重算并写回 localStorage）。
> 后端加 **`GET /api/health`** 探测当前后端就绪，前端状态点据此显示 checking/online/offline；ollama 挂时
> `/api/classify` 返回 503 `{error}` 而非裸 500。上传区分析成功后自动清理、选新文件清旧报告。

### P6 实时标注设计要点

> **2026-06-11 重构**：放弃"边录边聚类 + 边录边分类"的在线方案（旧 M1-M3），改为
> **「录音中只出实时转录预览，Stop 后把整段音频走完整离线 pipeline」**。
> 理由：在线 ECAPA 短切片聚类不稳（硬定 2 簇、实测 8 句→8 簇），且有了 BERT 后整段分类
> 已不再是瓶颈。新方案让 Live 和 Upload **共用同一条已验证的 pipeline**。旧在线方案演变史见
> log.md Session 8 + Session 10。`app/services/speaker.py`（ECAPA + sklearn 聚类）已**弃用**（死代码，留作参考）。

**数据流（新）**
```
录音中：
  MediaRecorder (chunk ~3s, stop/start 出完整 WebM blob)
    → WebSocket /api/stream (binary)
    → 服务端 PyAV 解码 → ① 累积 PCM（攒整段）② faster-whisper(vad_filter) 转录
    → 推 {type:utterance, id,start,end,text}  ← 纯实时预览，无 speaker / 无分类
按 Stop（"stop" 文本帧 → finalize）：
    → np.concatenate(累积 PCM) → 写一个完整 16kHz mono WAV
    → run_pipeline(wav)：整段 Whisper 重转 + pyannote diarization + 逐句分类 + 统计
    → 按阶段推 {type:status, message} （Transcribing… / Identifying speakers… / Classifying…）
    → 推 {type:result, segments, stats}
前端收到 result：
    → 丢弃 live 预览，复用 Upload 的报告 UI（renderReport）→ 跳 Analyze 页 + 存 History
```
**关键：live 预览（每 3s chunk 单独转）只图快，可能不准（断句/用词都可能和最终不同）；
最终报告是整段重跑，以最终为准。转录、说话人、标签三件事都在 Stop 后基于同一批最终 segment 一次算出，内部一致。**

**说话人识别：pyannote 完整 pipeline 跑整段（不再自己聚类）**
- `asr.py:diarize()` 用 `speaker-diarization-3.1`，和 Upload 同一条路径
- **人数**：传 `min_speakers=1, max_speakers=3`（`asr.py` 顶部 `MAX_SPEAKERS=3`）。pyannote 在范围内
  自动估人数——既解决了旧方案"硬定 2 簇/猜不准"的问题，又封顶防止过分裂跑出 5 个
- ⚠️ 仍非完美：>3 人录音会被并进 3 个；典型 1 治疗师+1 患者场景没问题
- **分类**：逐句 `classify(seg["text"])`，走 `state.current_model` → BERT 或 qwen 都生效（和 Upload 一致）
- **therapist 指认**：复用 Upload 的右栏下拉 + 点击行内 speaker 重指派，无单独 picker

**采集与延迟**
- 浏览器 MediaRecorder 分 chunk 录，每 chunk 是完整 WebM/Opus blob（stop/start 方式避免 EBML header 问题）
- 服务端对每 chunk 用 PyAV 解码：累积 PCM（供最终 WAV）+ 累积 elapsed（供预览时间戳）
- **Stop 后耗时**：≈ ASR + diarization（30min 音频 ~2min）+ 分类。选 **BERT** 分类几乎瞬间；选 **qwen** 长 session 会很久（2.9s/句串行）
- 状态栏靠 `status` 消息显示进度；安全超时 10min

**UI**
- "Live" 页：点 Start → 录音 → transcript 流式追加（只「时间 + 文字」，无色块无 badge）
- 点 Stop → 状态栏 "Finalizing… → 各阶段" → 收到 result → 自动跳 Analyze 页展示最终报告

**GPU 共存**
- 新方案 Live 不再常驻 ECAPA embedding：Whisper（~2GB）+ pyannote diarization（Stop 时载）+ qwen/BERT
- 代码不做显式调度，OOM 再加 `keep_alive: 0`

**里程碑**

| | 内容 | 状态 |
|---|---|---|
| M1 | 后端 WS + ASR + 异步分类 | ✅（后被重构取代）|
| M2 | 前端 Live 页 + MediaRecorder 分片 + 流式 UI | ✅ |
| M3 | ECAPA 边录边存 + Stop 离线聚类 | ⛔ 废弃（在线聚类不稳，改走 pyannote 整段）|
| **R1** | **重构：live 只转录预览 + Stop 整段走 run_pipeline（pyannote diarize + 分类）** | ✅ 代码完成，待浏览器实测 |
| M5 | 延迟/稳定性打磨（chunk 边界丢帧、长 session 内存） | ⬜ |
| M6 | Stop pipeline 进度推送 | 🟡 已有 status 阶段消息（粗粒度），细进度待做 |

**WS 消息协议（`/api/stream`）**

Client → Server：binary frame = 完整 WebM/Opus chunk；`"stop"` 文本帧 = 结束会话

Server → Client（JSON）：
```
{type:"utterance",  id, start, end, text}                  ← 录音中实时预览（无 speaker/无 cls）
{type:"status",     message}                                ← Stop 后各阶段进度
{type:"result",     segments:[...], stats:{...}}            ← Stop 后整段 pipeline 结果（同 /api/analyze 形状）
{type:"error",      message}
```

**已知坑**
- MediaRecorder codec 不一致：Chrome `webm/opus`，Safari 只支持 `mp4`，需 mimeType 协商
- stop/start 分片之间可能丢几毫秒（chunk 边界）→ 累积 PCM 有极小断点，对 Whisper 可忽略
- 长 session 累积 PCM 占内存：30min 16kHz mono float32 ≈ 115MB，可接受；超长需考虑落盘
- 短指令被 Whisper 揉进长句 → 易判 NONE（切句粒度问题，跟 live/offline 无关，待 P7 子句拆分）

**待确认**
- chunk 长度（3s 延迟低但每 chunk 信息少，5s 反之）
- `MAX_SPEAKERS`（默认 3）；>3 人场景需调
- 单麦 vs 双麦（双麦可走通道区分，跳过 diarization）

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
- **分类推理**: 双后端可切换 — Ollama API（qwen-bala，GPU）/ BERT（transformers 进程内，~360× 快）；前端模型下拉选 `bert` 即切，详见下方"模型 → BERT 后端"
- **ASR**: faster-whisper（本地 Whisper）
- **说话人分离**: pyannote.audio 4.0 + PyAV（不依赖系统 FFmpeg）
- **前端**: vanilla HTML/CSS/JS；设计系统 = Fraunces（标题）+ IBM Plex Sans/Mono（正文/数据）+ teal 强调色 `--accent`；报告页 KPI 仪表盘 + History 侧栏导航/详情
- **打包**: Tauri（闭源桌面应用）

### 主题（明/暗切换）

- 所有结构色（背景/边框/文字灰阶 + 分类色 D/G/N 含徽章底色）抽成 CSS 变量：`:root` = 暗色默认，`[data-theme="light"]` 覆盖变量值。**改前端切勿再写死十六进制色**，新颜色一律加变量。
- 右上角按钮 `toggleTheme()` 切换 `<html data-theme>` 并存 `localStorage`；`<head>` 内有首屏脚本提前应用，防刷新闪烁。
- 强调色已统一为 `--accent`（teal，明暗各取值，另有 `--accent-strong`/`--on-accent`）——**新代码一律 `var(--accent)`，别再写死蓝**。话者色块 S1–S5、toast 两主题通用，未变量化。
- 字体走 Google Fonts CDN（Fraunces / IBM Plex Sans / IBM Plex Mono），变量 `--font-display`/`--font-body`/`--font-mono`；首屏无网时回退 Georgia/系统字体。
- ⚠️ 坑：变量定义块自身含十六进制字面量，批量 `#xxx → var(--x)` 会污染定义行（自引用）。正确顺序：先抽走定义块 → 全文替换 → 再插回。

---

## 关键文件

```
arise-care/
├── app/
│   ├── main.py              # FastAPI 入口 + 静态文件；/api/config·/models·/health
│   ├── routers/
│   │   ├── classify.py      # POST /api/classify（文本分类）；ollama 挂返回 503 {error}
│   │   ├── transcribe.py    # POST /api/transcribe（音频转录）
│   │   └── pipeline.py      # POST /api/analyze（完整 pipeline）
│   ├── services/
│   │   ├── classifier.py    # 分类入口：current_model=="bert" 走 BERT，否则 Ollama
│   │   ├── bert_classifier.py # BERT 进程内推理（transformers）；映射 {0:G,1:D,2:NONE}
│   │   ├── asr.py           # faster-whisper + pyannote diarization（min/max_speakers 约束）
│   │   ├── speaker.py       # ⛔ 弃用：旧 Live 在线 ECAPA 聚类，已无引用（留作参考）
│   │   ├── stream.py        # WS 会话：录中只 ASR 预览 + 累积 PCM；Stop 写 WAV → run_pipeline
│   │   └── pipeline.py      # 编排：音频 → 转录 → diarize → 分类 → 统计（progress 回调）
│   ├── models/
│   │   └── schemas.py       # Pydantic 数据模型
│   └── static/
│       └── index.html       # 前端（CSS 变量化主题 + KPI 仪表盘 + History 侧栏导航/详情 + 模型状态点）
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

### BERT 后端（2026-06-09 加，可切换，详见 log.md Session 9）

- **模型** `BERT_finetuned_final/`（bert-base + 3 分类头，437MB，**gitignored**），transformers 进程内，不走 Ollama
- **选用**：下拉选 `bert`（`current_model=="bert"` → `classify()` 分流），离线 + Live 都生效；`/api/models` 列首且 Ollama 挂了不 502
- ⚠️ **映射** `{0:GUIDED,1:DIRECTED,2:NONE}`，跟团队脚本 `Bert2026.py` 写的不一致（config 是占位 LABEL_0/1/2）。**改标签别信 config/脚本，用 `test/compare_models.py` + 真实标注验**
- **速度** ~360×（8ms vs 2940ms/句）；**精度未定论**：3001 gold 上 BERT 75% > qwen 63.6%（n=44 太小，不推翻论文 85%>77%）。两后端都留，BERT 默认候选

## API

```
POST /api/classify
Body: { "text": "治疗师话语" }
Response: { "input": "...", "classification": "DIRECTED|GUIDED|NONE" }
# ollama 不可达时返回 503 { "error": "Ollama not reachable …" }

GET /api/health
Response: { "backend":"bert|ollama", "model", "ollama_up", "model_available", "ready" }
# 前端模型状态点据此显示 checking / online / offline

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
- **30min 全 GPU 耗时 ~32 分钟**：Whisper + pyannote ~160s + Ollama 串行分类 1767s（601 utterance × 2.94s/条，占 91% 是瓶颈）；P7 并发后预期 ~5-8 分钟

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
