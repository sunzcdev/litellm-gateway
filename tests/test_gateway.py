import requests

BASE_URL = "http://localhost:4000"
MASTER_KEY = "litellm-gateway-master-key"
HEADERS = {
    "Authorization": f"Bearer {MASTER_KEY}",
    "Content-Type": "application/json",
}


def test_health():
    """连通性测试：GET /health/liveliness 应返回 200"""
    resp = requests.get(f"{BASE_URL}/health/liveliness", headers=HEADERS)
    assert resp.status_code == 200, f"健康检查失败: {resp.status_code}"


def test_model_list():
    """模型列表测试：返回值应包含别名 smart/fast/vision/local/coder"""
    resp = requests.get(f"{BASE_URL}/v1/models", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    model_ids = [m["id"] for m in data["data"]]
    for alias in ["smart", "fast", "vision", "local", "coder"]:
        assert alias in model_ids, f"缺少别名模型: {alias}"


def test_smart_chat():
    """smart 路由测试：调用应返回 choices"""
    payload = {
        "model": "smart",
        "messages": [{"role": "user", "content": "Say hello in 3 words"}],
    }
    resp = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=HEADERS)
    assert resp.status_code == 200, f"路由失败: {resp.status_code} {resp.text[:200]}"
    data = resp.json()
    assert "choices" in data, "未返回 choices"
    assert "content" in data["choices"][0]["message"], "未返回内容"


def test_budget_block():
    """预算拦截测试：调用不存在的模型应返回 4xx"""
    payload = {
        "model": "nonexistent-model",
        "messages": [{"role": "user", "content": "hi"}],
    }
    resp = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=HEADERS)
    assert resp.status_code >= 400, f"应返回错误状态码，实际: {resp.status_code}"


def test_discover_dry_run():
    """探索脚本 dry-run 测试：确认能正常输出"""
    import subprocess
    result = subprocess.run(
        ["python3", "scripts/discover.py", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "discover.py 应正常退出"
    output = result.stdout.strip()
    assert "免费模型更新报告" in output, "应输出报告头"


if __name__ == "__main__":
    tests = [
        test_health,
        test_model_list,
        test_smart_chat,
        test_budget_block,
        test_discover_dry_run,
    ]
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
        except Exception as e:
            print(f"  FAIL {t.__name__}: {e}")
