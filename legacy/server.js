const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = 3000;
const OLLAMA_URL = "http://localhost:11434/api/chat";
const MODEL = "qwen-bala";

const server = http.createServer(async (req, res) => {
  // 静态页面
  if (req.method === "GET" && req.url === "/") {
    const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf-8");
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(html);
    return;
  }

  // 分类 API
  if (req.method === "POST" && req.url === "/classify") {
    let body = "";
    for await (const chunk of req) body += chunk;

    const { text } = JSON.parse(body);
    if (!text) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "text is required" }));
      return;
    }

    try {
      const ollamaRes = await fetch(OLLAMA_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: MODEL,
          messages: [{ role: "user", content: text }],
          stream: false,
        }),
      });

      const data = await ollamaRes.json();
      const result = data.message?.content?.trim() || "NO RESPONSE";

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ input: text, classification: result }));
    } catch (err) {
      res.writeHead(502, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Ollama unavailable: " + err.message }));
    }
    return;
  }

  res.writeHead(404);
  res.end("Not Found");
});

server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
