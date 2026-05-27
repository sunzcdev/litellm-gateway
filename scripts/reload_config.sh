#!/bin/bash
# 向 LiteLLM 发送 SIGHUP 重载配置
LITELLM_PID=$(pgrep -f "litellm.*config/config.yaml" | head -1)
if [ -n "$LITELLM_PID" ]; then
    kill -SIGHUP "$LITELLM_PID"
    echo "[$(date)] LiteLLM config reloaded (PID: $LITELLM_PID)"
else
    echo "[$(date)] LiteLLM not running"
    exit 1
fi
