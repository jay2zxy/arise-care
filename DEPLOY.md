# 部署指南（AWS）

把后端部署到一台 AWS GPU 实例，LLM 走实验室已有的 Ollama API，浏览器经 HTTPS 访问。
前端由 FastAPI 自己出（同源，相对路径自动正确，**前端零改动**）。

## 架构

```
浏览器 ──HTTPS/WSS──▶ Caddy(自动证书) ──▶ uvicorn app.main:app  (一台 g4dn EC2)
                                            ├ FastAPI + 前端 index.html
                                            ├ Whisper + pyannote  ← 本机 GPU
                                            └ classifier ──HTTP──▶ 实验室 Ollama (qwen-bala)
```

## 前置准备

- [ ] EC2 **g4dn.xlarge**（T4 16GB，~$0.5/hr）；AMI 选 **Deep Learning Base GPU AMI (Ubuntu 22.04)**（预装驱动+CUDA）
- [ ] **绑 Elastic IP**（停机重启后公网 IP 不变，否则域名会指空）
- [ ] **一个自己的域名**，A 记录指向 Elastic IP
      ⚠️ **不能用 EC2 默认的 `ec2-x.compute.amazonaws.com`**——Let's Encrypt 策略禁止给它签证书（会报 `Policy forbids issuing for name on Amazon EC2 domain`），没 HTTPS 麦克风就废
      → 最省：注册免费 **DuckDNS** 子域名（`xxx.duckdns.org`，Let's Encrypt 正常发证）；或买个便宜 .com/.xyz
- [ ] 实验室 **Ollama API 地址**（如 `http://<lab-host>:11434`），确认对方 `OLLAMA_HOST=0.0.0.0` 且本机连得到
- [ ] **HF_TOKEN**（HF 网页先接受 `pyannote/speaker-diarization-3.1` 条款）
      ⚠️ `pyannote/embedding` 自 P6 重构后已不用（旧 Live 在线聚类的依赖，现走 diarization-3.1），**只需接受 diarization 一个**

**安全组**：入站 22(你的IP) / 80 / 443；出站 11434 到实验室（同 VPC 走私网 IP，别走公网）

## 部署步骤

```bash
# 1. 上机验证 GPU
ssh ubuntu@<EC2_IP>
nvidia-smi

# 2. 拉代码 + 装依赖
sudo apt update && sudo apt install -y python3-venv git
git clone <仓库地址> arise-care && cd arise-care
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip          # 必须！pip<24 解析 pyannote 会 OOM
pip install -r requirements.txt
```

**3. 配置（核心改动就这两处）**

```python
# config.py 第 1 行：localhost 换成实验室地址
OLLAMA_URL = "http://<lab-host>:11434/api/chat"
```
```bash
echo "HF_TOKEN=hf_xxxx" > .env     # asr.py 用 load_dotenv 读
```

**4. 先手动起一次确认能跑**（首次会下 Whisper+pyannote 模型，等几分钟）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl -X POST localhost:8000/api/classify -H 'Content-Type: application/json' -d '{"text":"lift your arm slowly"}'
# 期望 {"...","classification":"DIRECTED|GUIDED|NONE"}
```

**5. uvicorn 设常驻**：`/etc/systemd/system/arise.service`

```ini
[Unit]
After=network.target
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/arise-care
ExecStart=/home/ubuntu/arise-care/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now arise
```

**6. Caddy 自动 HTTPS + WSS**

```bash
# 安装（官方源）
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```
`/etc/caddy/Caddyfile`（reverse_proxy 自动透传 WebSocket，活跃连接不设超时上限）：
```
your.domain.com {
    reverse_proxy 127.0.0.1:8000
}
```
> Caddy 透传 WS 时不会主动掐活跃连接，Live 的 Stop-后长 pipeline 没问题。
> **但若中间再加 ALB / CloudFront，它们的 idle timeout（常 60s）会掐断**——见下方关键坑。
```bash
sudo systemctl reload caddy
```

**7. 验收**：浏览器开 `https://your.domain.com`
- Upload 页传音频跑 `/api/analyze` 出转录+统计
- Live 页 Start → **弹麦克风授权**（HTTPS 才有）→ 出实时转录预览 → Stop → 等整段 pipeline（状态栏走 Transcribing/Identifying/Classifying）→ **自动跳报告页**出转录+说话人+统计

## 关键坑

- **麦克风必须 HTTPS**：没 TLS 麦克风被禁，Live 废
- **⚠️ Live Stop 后是长任务，别让中间层掐 WS**：P6 重构后，按 Stop 才在整段音频上跑 pipeline（30min 录音：BERT ~2min / qwen 十几分钟），期间 WS 要保持。Caddy 直连 uvicorn 默认 OK（透传不掐活跃 WS，且后端会推 status 阶段消息保活）；**但加了 ALB/CloudFront/Nginx 的话要把 idle/read timeout 调到 > 最长 session 处理时间**（ALB 默认 60s 必断）。选 BERT 后端能大幅缩短这个窗口
- **⚠️ /tmp 与内存**：finalize 写临时 WAV（~57MB/30min），累积 PCM 驻内存（~115MB/30min）；容器化时给够 `/tmp` 和内存，多并发 Live 会叠加
- **pip 必须 ≥24**：否则 pyannote 依赖解析 OOM
- **HF gated**：未接受条款会 401
- **实验室 Ollama 可达**：`OLLAMA_HOST=0.0.0.0` + 安全组放行 11434；同 VPC 用私网 IP
- **实验室模型名要叫 `qwen-bala`**：`config.py` 的 `OLLAMA_MODEL` 写死这个名，部署前让实验室 `ollama list` 确认对得上，否则分类 404
- **首次启动慢**：在下模型，别以为卡死
- **⚠️ faster-whisper 在 Linux 找不到 cuDNN/cuBLAS**（最容易踩）：
  `asr.py` 把 `torch/lib` 加进 **PATH** 的 hack 是 Windows 专用——Linux 加载 `.so` 看的是 `LD_LIBRARY_PATH`，PATH 没用。报 `Unable to load libcudnn` / `libcublas` 时：
  ```bash
  # 让 CTranslate2 找到 torch 自带的 CUDA 库
  export LD_LIBRARY_PATH=$(python -c "import os,torch;print(os.path.dirname(torch.__file__))")/lib:$LD_LIBRARY_PATH
  ```
  （Deep Learning AMI 自带系统 cuDNN，多数情况无需手动设；报错再加）
- **⚠️ systemd 环境精简，GPU 库可能丢**：交互式 shell 能跑、systemd 起的进程却报找不到库，是因为 service 环境干净。需要时在 §5 的 `[Service]` 段补一行（路径同上）：
  ```ini
  Environment=LD_LIBRARY_PATH=/home/ubuntu/arise-care/.venv/lib/python3.x/site-packages/torch/lib
  ```

---

## 将来可选（当前用不上，需要时再做）

- **拆前端到 S3/CloudFront**：跨域，需改前端 API 为绝对地址 + `main.py` 加 CORS。
- **Docker 容器化**：把 GPU 依赖固化，需装 `nvidia-container-toolkit`、`docker run --gpus all`，Caddy 留主机。
- **停机省钱**：不用时 `aws ec2 stop-instances`（保留 EBS）；配合 Elastic IP 保 IP 不变。
- **⚠️ 换 Amazon Transcribe 去 GPU 化**：用 Transcribe API 替掉 Whisper+pyannote → 后端变纯 CPU 轻服务，可上 Fargate/App Runner、按用量付费、零 GPU 运维。
  **但这是"重构+重测"，不是捷径**：要重写 `asr.py` + `pipeline.py`/Live 路径，且 Transcribe 切句方式不同会**让现有 68.2% 精度评估作废，必须重新评估**（"短指令被长句淹没"的问题可能复发）。只有当 GPU 成本/运维成为负担、或要大规模多用户时才值得立项做。
