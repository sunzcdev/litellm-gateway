#!/bin/bash
# 供 systemd 健康检查用
curl -sf http://localhost:4000/health/liveliness > /dev/null 2>&1
exit $?
