#!/bin/bash
# 重载 LiteLLM 配置
# config-only 模式下通过重启服务实现热加载
systemctl --user daemon-reload
systemctl --user restart litellm-gateway
echo "[$(date)] LiteLLM Gateway 已重启"
