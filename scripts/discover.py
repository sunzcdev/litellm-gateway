#!/usr/bin/env python3
"""免费模型自动探索器。

扫描 OpenRouter 和 Groq 平台，寻找定价为 0 的免费模型。
保存缓存，对比历史结果并生成变更日志。
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional

CACHE_DIR = os.path.expanduser("~/.hermes/data")
CACHE_FILE = os.path.join(CACHE_DIR, "discover_cache.json")
LOG_FILE = "discover_changelog.log"
TIMEOUT = 30


class Scanner:
    """扫描器基类"""

    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url

    def fetch_json(self) -> Optional[dict]:
        """发送 GET 请求并解析 JSON，返回 dict 或 None。"""
        try:
            req = urllib.request.Request(self.url, method="GET")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            print(f"[{self.name}] HTTP {e.code} {e.reason} while fetching {self.url}",
                  file=sys.stderr)
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            print(f"[{self.name}] Connection/parse error: {e}", file=sys.stderr)
        return None

    def scan(self) -> List[Dict[str, str]]:
        """返回模型列表，每个模型 dict 包含 id、provider、price。"""
        raise NotImplementedError


class OpenRouterScanner(Scanner):
    """OpenRouter 免费模型扫描器"""

    def __init__(self) -> None:
        super().__init__("OpenRouter", "https://openrouter.ai/api/v1/models")

    def scan(self) -> List[Dict[str, str]]:
        data = self.fetch_json()
        if not data:
            return []
        models: List[Dict[str, str]] = []
        for m in data.get("data", []):
            slug = m.get("slug", "")
            pricing = m.get("pricing", {})
            prompt_price = pricing.get("prompt", "")
            # 只收集免费模型（prompt price == "0"）
            if slug and prompt_price == "0":
                models.append({
                    "id": f"openrouter/{slug}",
                    "provider": "openrouter",
                    "price": prompt_price,
                })
        return models


class GroqScanner(Scanner):
    """Groq 免费模型扫描器（所有模型目前均视为免费，有速率限制）"""

    def __init__(self) -> None:
        super().__init__("Groq", "https://api.groq.com/openai/v1/models")

    def scan(self) -> List[Dict[str, str]]:
        data = self.fetch_json()
        if not data:
            return []
        models: List[Dict[str, str]] = []
        for m in data.get("data", []):
            model_id = m.get("id", "")
            if model_id:
                models.append({
                    "id": f"groq/{model_id}",
                    "provider": "groq",
                    "price": "free",   # 平台整体免费
                })
        return models


def load_cache() -> Optional[dict]:
    """读取上次缓存的扫描结果。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_cache(report: dict) -> None:
    """将当前扫描结果写入缓存。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)


def build_model_index(models: List[Dict[str, str]]) -> Dict[str, dict]:
    """根据模型 id 建立索引，便于比较。"""
    return {m["id"]: m for m in models}


def compute_diff(current_models: List[Dict[str, str]],
                 previous_cache: Optional[dict]) -> dict:
    """比较当前扫描结果与历史缓存，输出新增、消失、价格变更。"""
    if previous_cache is None:
        prev_models = []
    else:
        prev_models = previous_cache.get("models", [])

    prev_index = build_model_index(prev_models)
    curr_index = build_model_index(current_models)

    added_ids = set(curr_index.keys()) - set(prev_index.keys())
    removed_ids = set(prev_index.keys()) - set(curr_index.keys())
    common_ids = set(curr_index.keys()) & set(prev_index.keys())

    added = [curr_index[mid] for mid in added_ids]
    removed = [prev_index[mid] for mid in removed_ids]

    price_changed = []
    for mid in common_ids:
        curr_price = curr_index[mid].get("price", "")
        prev_price = prev_index[mid].get("price", "")
        if curr_price != prev_price:
            price_changed.append({
                "id": mid,
                "provider": curr_index[mid]["provider"],
                "old_price": prev_price,
                "new_price": curr_price,
            })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": current_models,
        "added": added,
        "removed": removed,
        "price_changed": price_changed,
    }


def format_report(diff: dict) -> str:
    """生成人类可读的变更报告。"""
    added = diff["added"]
    removed = diff["removed"]
    pc = diff["price_changed"]
    total = len(diff["models"])

    lines = [
        "📢 免费模型更新报告",
        "━━━━━━━━━━━━━━━━━━",
    ]
    for m in added:
        lines.append(f"🆕 新增: {m['id']} (供应商: {m['provider']})")
    for m in removed:
        lines.append(f"❌ 消失: {m['id']} (供应商: {m['provider']})")
    for c in pc:
        lines.append(
            f"⚠️ 变价: {c['id']} ({c['provider']}) "
            f"(旧价: {c['old_price']} → 新价: {c['new_price']}) 自动摘除"
        )
    if not added and not removed and not pc:
        lines.append("✅ 无变化")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"本次扫描: {total} 个模型 (新增 {len(added)}, 消失 {len(removed)})")
    return "\n".join(lines)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="免费模型探索器")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅打印报告，不写入日志/缓存")
    args = parser.parse_args()

    scanners = [OpenRouterScanner(), GroqScanner()]
    all_models: List[Dict[str, str]] = []
    for scanner in scanners:
        models = scanner.scan()
        all_models.extend(models)
        print(f"[{scanner.name}] 扫描到 {len(models)} 个模型")

    previous_cache = load_cache()
    diff = compute_diff(all_models, previous_cache)
    report = format_report(diff)

    if args.dry_run:
        print(report)
    else:
        # 写入日志文件
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"{report}\n")
        # 更新缓存
        save_cache(diff)
        print(report)
        print(f"报告已追加至 {LOG_FILE}，缓存已更新。")


if __name__ == "__main__":
    main()
