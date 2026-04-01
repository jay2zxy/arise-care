# Arise Care - 开发日志

### 2026-03-26 - Session 1: 原型搭建

**Node.js + Ollama 原型**：
- ✅ 搭建 Node.js 零依赖 HTTP 服务器（server.js + index.html）
- ✅ 微调 Qwen2.5-7B 模型（qwen_bala_Q5_K_M.gguf）导入 Ollama 为 `qwen-bala`
- ✅ 修复 Modelfile：补上 `<|im_start|>/<|im_end|>` chat template + 分类专用 system prompt
- ✅ 设置 temperature 0.1 + num_predict 10，提升分类确定性
- ✅ Web 界面测试通过，DIRECTED/GUIDED 分类正确

**踩坑**：
- ⚠️ Modelfile Template 错误：默认 `{{ .Prompt }}` 是原始拼接，Qwen2.5 需要 chat template 格式，否则模型自由生成而不是分类
- ⚠️ System prompt 太通用：只写了 "You are a helpful assistant."，模型不知道该做分类任务

**已知问题**：
- 🐛 NONE 类分类不够准：康复相关观察/评价容易误判为 GUIDED
  - "Your session went really well today" → GUIDED（应为 NONE）
  - "I noticed your range of motion has improved" → GUIDED（应为 NONE）
  - 原因：微调数据中"治疗相关观察"类 NONE 样本可能不足

### 2026-03-31 - Session 2: 项目重构规划

**技术决策**：
- 项目正式命名为 **arise-care**
- 架构方向：Node.js → Python FastAPI，分类继续用 Ollama API
- ASR 方案：faster-whisper（本地 Whisper，论文也提到作为替代）
- 说话人分离：whisperX + pyannote
- 打包方案：Tauri（闭源桌面应用，医疗场景）
- 模型分发：开发阶段用 Ollama API（GPU 开箱即用）；打包时可换 llama-cpp-python 或蒸馏小模型

**技术调研**：
- 📊 依赖体积：fastapi + uvicorn + httpx 很轻量
- 📊 模型体积：Q5_K_M 量化 5.2GB，后续可蒸馏到 1.5B/3B (~1GB) 内嵌分发
- ⚠️ llama-cpp-python Windows 编译需预编译 wheel（备选方案，当前不用）

**项目初始化**：
- ✅ GitHub repo: jay2zxy/arise-care
- ✅ 创建 main 分支 + jay-dev 开发分支
- ✅ 初始提交：.gitignore, README, CLAUDE.md, log.md, legacy/
- ✅ 旧版 Node.js 代码移入 `legacy/`（server.js, index.html）
- ✅ fastapi, uvicorn, httpx 安装完成
- ✅ 项目目录结构创建：app/{routers,services,models,static}, data/

**Phase 1 完成**：
- ✅ `config.py`：Ollama URL、模型名、推理参数
- ✅ `app/services/classifier.py`：httpx 调用 Ollama API 分类（替代 llama-cpp-python）
- ✅ `app/routers/classify.py`：`POST /api/classify` 端点
- ✅ `app/models/schemas.py`：Pydantic 数据模型
- ✅ `app/main.py`：FastAPI 入口 + 静态文件服务
- ✅ `app/static/index.html`：前端迁移，API 路径改为 `/api/classify`
- ✅ 分类验证：DIRECTED/GUIDED/NONE 均正确
- ✅ Git: e426e65

### 2026-04-01 - Session 3: Phase 2 音频转录

**环境**：
- ✅ 创建 venv 虚拟环境，依赖隔离
- ✅ 全局 Python 清理，移除 arise-care 相关包
- ✅ faster-whisper 安装成功

**Phase 2 进行中**：
- ✅ `app/services/asr.py`：faster-whisper 转录服务（small 模型）
- ✅ `app/routers/transcribe.py`：`POST /api/transcribe` 端点
- ✅ `app/models/schemas.py`：新增 TranscribeSegment/TranscribeResponse
- ✅ 转录测试通过（r.m4a → "Please rise your left arm slowly."）

**踩坑**：
- ⚠️ faster-whisper GPU 模式需要 cublas64_12.dll（CUDA 12），本机未安装，暂用 CPU
- ⚠️ GPU 显存分配：Ollama qwen-bala 占 ~5.2GB / 8GB RTX 3070，Whisper 无法共享 GPU
- ⚠️ python-multipart 未在 requirements.txt 中，文件上传报错

**待完成**：
- ⬜ speaker diarization（pyannote，需 HuggingFace token）
- ⬜ Phase 3：完整 pipeline + 统计报告
- ⬜ Phase 4：前端完善（Google AI Studio 风格 dashboard）
