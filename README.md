# LiteLLM Gateway — 免费保险模型中转站

基于 [LiteLLM](https://github.com/BerriAI/litellm) 构建的个人 LLM 统一网关，聚合多家厂商的免费 API 额度，提供统一接入、自动探索、无缝切换、用量统计。

---

## 架构

```
客户端 ─→ LiteLLM Proxy (localhost:4000) ─→ OpenRouter:free
                      │                       ├─ DeepSeek 直连
                      │                       ├─ 智谱 GLM-4V-Flash
                      │                       ├─ Groq 免费
                      │                       └─ Ollama (本地)
                      │
                 auto-discover (cron 每日)
                      │
                      ▼
              发现新免费模型 → 自动注册
              模型转付费 → 自动摘除 + 通知
```

## 模型别名

| 别名 | 用途 | 模型池（按成本优先级排序） |
|------|------|---------------------------|
| `smart` | 日常对话/推理 | gemma-4:free → deepseek-v4:free → groq/llama → deepseek-chat |
| `fast` | 快速响应 | groq/llama-3.1-8b → groq/qwen-2.5-32b → gemma-4:free |
| `vision` | 图片理解 | 智谱 GLM-4V-Flash → gemma-4:free |
| `local` | 本地轻量 | Ollama Qwen2.5-1.5B |
| `coder` | 编程任务 | deepseek-v4-flash:free |

> 调用方永远传别名，LiteLLM 自行按成本策略选择实际模型。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp config/.env.example config/.env
# 编辑 config/.env，填入你的 API Key
```

需要的 Key：
- `LITELLM_MASTER_KEY` — 网关管理密钥（任意字符串）
- `OPENROUTER_API_KEY` — OpenRouter 密钥
- `DEEPSEEK_API_KEY` — DeepSeek 直连密钥
- `ZHIPU_API_KEY` — 智谱密钥
- `GROQ_API_KEY` — Groq 密钥

### 3. 启动网关

```bash
# 加载环境变量
set -a && source config/.env && set +a

# 启动
litellm --config config/config.yaml --port 4000
```

### 4. 验证

```bash
# 健康检查
curl http://localhost:4000/health/liveliness

# 模型列表（应包含 smart/fast/vision/local/coder）
curl -s http://localhost:4000/v1/models | python3 -m json.tool

# 调用测试
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"smart","messages":[{"role":"user","content":"你好"}]}'
```

### 5. 配置 Hermes

```yaml
# ~/.hermes/config.yaml
default_provider: litellm
providers:
  litellm:
    api_base: http://localhost:4000/v1
    api_key: <你的 LITELLM_MASTER_KEY>
    models:
      default: smart
      chat: smart
      vision: vision
```

---

## 自动探索

每日自动扫描免费模型：

```bash
# 试运行（不写缓存/日志）
python3 scripts/discover.py --dry-run

# 正式运行
python3 scripts/discover.py
```

设置定时任务：

```bash
crontab -e
# 每天 08:00 执行
0 8 * * * cd /path/to/litellm-gateway && python3 scripts/discover.py >> discover_changelog.log 2>&1
```

---

## systemd 部署

```ini
# ~/.config/systemd/user/litellm-gateway.service
[Unit]
Description=LiteLLM AI Gateway
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/litellm --config /path/to/config/config.yaml --port 4000
EnvironmentFile=/path/to/config/.env
Restart=always
RestartSec=10
ExecReload=/bin/kill -SIGHUP $MAINPID

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now litellm-gateway
```

---

## 热加载配置

修改 `config/config.yaml` 后无需重启：

```bash
bash scripts/reload_config.sh
```

---

## 运行测试

```bash
# 确保网关已启动，然后：
python3 tests/test_gateway.py
```

---

## 项目结构

```
litellm-gateway/
├── config/
│   ├── config.yaml        # LiteLLM 主配置（模型别名 + 路由策略）
│   └── .env.example       # 环境变量模板
├── scripts/
│   ├── discover.py        # 免费模型自动探索器
│   ├── reload_config.sh   # 配置热加载
│   └── check_health.sh    # 健康检查（供 systemd 用）
├── tests/
│   └── test_gateway.py    # 集成测试
├── docs/
│   ├── 需求文档.md          # 产品需求
│   ├── 软件需求文档.md       # 软件需求规格
│   └── 技术文档.md          # 技术设计
├── requirements.txt
└── README.md
```

## 注意事项

- `max_budget: 0` 已配置为硬上限，防止意外调用付费模型
- 如有新的免费模型上线，`discover.py` 会自动发现并写入日志（config 热加载需手动触发或后续自动化）
- ⚠️ 不要将 `.env` 文件提交到 git（已列入 `.gitignore`）
