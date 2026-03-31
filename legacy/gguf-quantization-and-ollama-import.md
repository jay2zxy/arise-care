# 2026-03-26 GGUF 模型量化与 Ollama 导入

## 背景

有一个本地的 `qwen_bala_fp16.gguf`（15GB），之前从 HuggingFace 格式硬转的，想用 Ollama 代理运行。

## 量化原理

- FP16 每个权重 16bit，量化就是把高精度浮点压缩成低精度整数，用少量精度换大量空间和速度
- 模型权重大多集中在很小的数值范围，FP16 精度过剩，可以压缩
- 量化过程：一组权重（如 32 个）找最大最小值 → 映射到整数范围（Q4 = 0~15）→ 存一个缩放因子（scale）用于还原
- K-quant（如 Q5_K_M）对不同层用不同精度：attention 层给高精度，不重要的层给低精度，效果比全量化好
- 量化级别对比：
  - Q8 → ~7.5GB（体积减半）
  - **Q5_K_M → ~5GB**（推荐，质量和体积平衡）
  - Q4_K_M → ~4GB
  - Q2 → ~2GB（太糙）

## 操作步骤

### 1. 编译 llama-quantize

环境：已有 CMake 4.2.3 + MinGW GCC 16.0.1

```bash
cd /e/Code
git clone --depth 1 https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_FLAGS="-D_WIN32_WINNT=0x0A00" \
  -DCMAKE_CXX_FLAGS="-D_WIN32_WINNT=0x0A00"
cmake --build build --target llama-quantize -j$(nproc)
```

**踩坑**：cpp-httplib 用了 `CreateFile2` API，MinGW 头文件默认没声明，需要手动定义 `_WIN32_WINNT=0x0A00`（Win10 级别）。设成 `0x0602`（Win8）会被 httplib 的预处理检查直接 `#error` 拒绝。

### 2. 量化模型

```bash
llama-quantize.exe qwen_bala_fp16.gguf qwen_bala_Q5_K_M.gguf Q5_K_M
```

结果：14.5GB → 5.2GB，耗时约 60 秒。

### 3. Ollama 导入

模型文件放在 `C:\Users\del\.ollama\custom\`（自建目录，不干扰 Ollama 内部 blob 管理）。

创建 Modelfile：
```
FROM ./qwen_bala_Q5_K_M.gguf
```

导入：
```bash
cd C:\Users\del\.ollama\custom
ollama create qwen-bala -f Modelfile
```

### 4. 使用方式

这是一个微调过的分类模型（康复治疗师话语分类：DIRECTED/GUIDED/NONE），不适合用 `ollama run` 聊天——会幻觉出不相关的内容。

正确用法是通过 API 调用，按训练时的格式传入待分类文本：
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen-bala",
  "prompt": "待分类的治疗师话语",
  "stream": false
}'
```

## 关键路径

- llama.cpp 源码：`E:\Code\llama.cpp\`
- 量化工具：`E:\Code\llama.cpp\build\bin\llama-quantize.exe`
- 量化后模型：`C:\Users\del\.ollama\custom\qwen_bala_Q5_K_M.gguf`
- Modelfile：`C:\Users\del\.ollama\custom\Modelfile`
- Ollama 模型名：`qwen-bala:latest`
