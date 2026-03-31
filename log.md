# 项目日志

## 2026-03-26

### 完成
- 搭建了 Node.js + Ollama 的治疗师话语分类 Web 服务（server.js + index.html）
- 将微调的 Qwen2.5-7B 模型（qwen_bala_Q5_K_M.gguf）导入 Ollama 为 `qwen-bala`
- 修复 Modelfile 配置问题：
  - 补上 Qwen2.5 的 chat template（`<|im_start|>/<|im_end|>` 格式），原来用的 `{{ .Prompt }}` 导致 chat API 消息格式不对
  - 添加分类专用 system prompt
  - 设置 temperature 0.1 + num_predict 10，提升分类确定性和响应速度
- Web 界面测试通过，DIRECTED/GUIDED 分类正确

### 踩坑
1. **Modelfile Template 错误** — 默认生成的 `TEMPLATE {{ .Prompt }}` 是原始拼接，Qwen2.5 需要 `<|im_start|>/<|im_end|>` 格式的 chat template，否则 chat API 的 messages 没被正确格式化，模型收到乱拼的 prompt 就自由生成而不是分类
2. **System prompt 太通用** — 只写了 "You are a helpful assistant."，没有分类指令，模型不知道该做分类任务，导致输出长篇对话而非标签

### 已知问题
- NONE 类分类不够准：跟康复相关的观察/评价容易误判为 GUIDED
  - "Your session went really well today" → GUIDED（应为 NONE）
  - "I noticed your range of motion has improved" → GUIDED（应为 NONE）
  - 纯闲聊（天气、问候、时间提醒）分类正确
  - 原因：微调数据中"治疗相关观察"类 NONE 样本可能不足

## 2026-03-31

### 规划
- 项目正式命名为 **arise-care**，准备建 GitHub repo
- 确定技术重构方向：Node.js + Ollama → Python FastAPI + llama-cpp-python
- 完整 pipeline 规划：音频上传 → faster-whisper ASR → whisperX 说话人分离 → qwen-bala 分类 → 统计报告
- 最终目标：Tauri 打包为闭源桌面应用（医疗场景）

### 技术调研
- llama-cpp-python 可直接加载 .gguf 文件推理，替代 Ollama 作为中间层，更适合打包分发
- faster-whisper 是 whisper.cpp 的 Python 封装，本地 ASR 方案，论文也提到 Whisper 作为替代
- whisperX 集成 pyannote 做 speaker diarization，区分治疗师 vs 患者
- fastapi + uvicorn + llama-cpp-python 总依赖约 50-70MB，模型 5.2GB 已在本地
- llama-cpp-python 在 Windows 上编译失败，需要预编译 wheel（待解决）

### 模型分发思路
- 5.2GB gguf 不适合内嵌安装包，应用启动时让用户指定模型路径或单独下载
- 后续可考虑进一步量化（Q4_K_M ~4.4GB）或蒸馏到更小模型（Qwen2.5-1.5B/3B）
