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
- 架构方向：Node.js + Ollama → Python FastAPI + llama-cpp-python
- ASR 方案：faster-whisper（本地 Whisper，论文也提到作为替代）
- 说话人分离：whisperX + pyannote
- 打包方案：Tauri（闭源桌面应用，医疗场景）
- 模型分发：应用不内嵌模型，启动时指定路径或单独下载

**技术调研**：
- 📊 依赖体积：fastapi + uvicorn + llama-cpp-python 约 50-70MB
- 📊 模型体积：Q5_K_M 量化 5.2GB，后续可压缩（Q4_K_M ~4.4GB / 蒸馏到 1.5B/3B）
- ⚠️ llama-cpp-python Windows 编译失败（无 MSVC），需预编译 wheel

**项目初始化**：
- ✅ GitHub repo: jay2zxy/arise-care
- ✅ 创建 main 分支 + jay-dev 开发分支
- ✅ 初始提交：.gitignore, README, CLAUDE.md, log.md, legacy/
- ✅ 旧版 Node.js 代码移入 `legacy/`（server.js, index.html）
- ✅ llama-cpp-python 通过预编译 wheel 安装成功
- ✅ fastapi, uvicorn 安装完成
- ✅ 项目目录结构创建：app/{routers,services,models,static}, data/

**下一步**：
- ⬜ Phase 1：config.py → classifier.py → main.py → 前端迁移
- ⬜ Phase 2：faster-whisper + whisperX 音频转录
- ⬜ Phase 3：完整 pipeline + 统计报告
- ⬜ Phase 4：前端完善
