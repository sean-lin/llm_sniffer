# LLM Proxy Sniffer

LLM API 代理嗅探工具。拦截并记录 OpenAI / Anthropic 格式的 LLM API 请求，提供 Web 界面浏览对话日志。

## 功能

- 同时接受 OpenAI 和 Anthropic 格式的客户端请求，统一转发到 OpenAI 协议后端
- 支持 SSE streaming 透传
- 自动按 session 分组记录所有请求/响应（SQLite）
- 多媒体内容（图片/音频）提取保存到本地文件
- Web UI 浏览 session 列表、多轮对话、tool_use 详情及内联多媒体展示

## 安装

```bash
# Python 依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 前端构建（需要 Node.js）
cd frontend
npm install
npm run build
cd ..
```

## 配置

编辑 `config.py`：

```python
LISTEN_PORT = 8080           # 监听端口
REMOTE_URL = "https://api.openai.com"  # 后端 LLM 地址
BACKEND_API_KEY = "sk-xxx"   # 后端 API Key
```

## 使用

```bash
source venv/bin/activate
python server.py
```

- Web UI：`http://localhost:8080/`
- OpenAI 客户端：设置 `base_url = "http://localhost:8080/v1"`
- Anthropic 客户端：设置 `base_url = "http://localhost:8080"`

可通过 `X-Session-ID` 请求头手动指定 session 分组，否则自动按 IP + 模型 + 时间窗口分组。
