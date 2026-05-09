# LLM Proxy Sniffer Configuration

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8080

# Backend LLM server (OpenAI-compatible endpoint)
REMOTE_URL = "https://idealab.alibaba-inc.com/api/openai"

# API key to use when forwarding to backend
BACKEND_API_KEY = "ff3d672e4c65f6526816cfbdcd338bdf"

# API keys accepted from clients (empty list = accept any)
ACCEPTED_API_KEYS = []

# Session timeout in seconds for auto-grouping
SESSION_TIMEOUT = 1800

# Database and media storage paths
DB_PATH = "logs/sniffer.db"
MEDIA_DIR = "logs/media"

# Frontend static files directory
STATIC_DIR = "static"
