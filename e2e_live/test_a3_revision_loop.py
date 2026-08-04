"""A3: verification-loop revision closure test.

Same-thread flow:
1. Run a full Ultra Pack (7 files written to this thread's outputs)
2. Corrupt one file (observed_public without source_urls)
3. Ask the agent to present_files -> preflight must block with loop state
4. Ask the agent to fix and re-present -> must succeed
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from e2e_live.driver import LiveClient  # noqa: E402

PACK_FILES = [
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
]


def find_thread_outputs(thread_id: str) -> Path | None:
    base = Path(
        "/Users/zhangqixiang/0_2实习/deepagents/deer-flow-data-inspector/backend/.deer-flow/"
        f"users/cb406532-cf0b-41ef-a336-c11f8e8c28b3/threads/{thread_id}/user-data/outputs"
    )
    return base if base.exists() else None


def main() -> None:
    c = LiveClient(agent_name="ecom-launch")
    tid = c.create_thread()
    config = {"context": {"mode": "ultra"}}

    print("=== 步骤 1: 完整 Ultra Pack（最多重试 3 次）===")
    outputs = None
    for attempt in range(1, 4):
        r1 = c.run(
            tid,
            "不要提问，直接执行：我有一个便携咖啡杯，无样品无规格，帮我做完整的 Launch Validation Pack",
            config=config,
            timeout=900,
        )
        print(f"  尝试 {attempt}: 耗时 {round(r1.elapsed_s, 1)}s | tokens={r1.total_tokens} | calls={r1.llm_call_count}")
        outputs = find_thread_outputs(tid)
        if outputs is not None:
            files = sorted(p.name for p in outputs.iterdir() if p.is_file())
            if len(files) >= 7:
                print(f"  磁盘文件 ({len(files)}): {files}")
                break
        print(f"  文件不完整（{0 if outputs is None else len(files)} 个），重试...")
        outputs = None
    if outputs is None:
        print("!! 3 次尝试后仍未生成完整 Pack")
        return

    print("\n=== 步骤 2: 注入坏条目（observed_public 无 URL + 编造断言）===")
    ledger = outputs / "evidence-ledger.json"
    d = json.loads(ledger.read_text(encoding="utf-8"))
    d.setdefault("entries", []).append(
        {
            "id": "E-BAD",
            "claim": "竞品B在抖音有100万粉丝（编造数据）",
            "label": "observed_public",
            "source_urls": [],
        }
    )
    ledger.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  已注入")

    print("\n=== 步骤 3: present_files（期望 preflight 拦截 + loop state）===")
    r2 = c.run(
        tid,
        "不要提问，直接用 present_files 把 outputs 里的 7 个文件正式交付",
        config=config,
        timeout=900,
    )
    print(f"  耗时 {round(r2.elapsed_s, 1)}s")
    text = r2.final_text
    print(f"  回答: {text[:700]}")
    blocked = "preflight" in text or "Loop state" in text or "attempt" in text or "阻止" in text
    print(f"  preflight 拦截: {'是' if blocked else '否(未拦截!)'}")

    print("\n=== 步骤 4: 修复后重新 present（期望通过）===")
    r3 = c.run(
        tid,
        "不要提问：刚才预检发现了问题，请修复 evidence-ledger.json 里那个没有来源的条目（删除或补上真实来源），然后重新 present_files 交付 7 个文件",
        config=config,
        timeout=900,
    )
    print(f"  耗时 {round(r3.elapsed_s, 1)}s")
    text3 = r3.final_text
    print(f"  回答: {text3[:700]}")
    print(f"  artifacts: {r3.artifacts}")
    delivered = "Successfully presented" in text3 or "成功" in text3 and "artifacts" in str(r3.artifacts)
    print(f"  交付成功: {'是' if delivered or r3.artifacts else '否'}")

    # Post-check: ledger must be clean again
    d2 = json.loads(ledger.read_text(encoding="utf-8"))
    bad = [e for e in d2.get("entries", []) if e.get("label") == "observed_public" and not e.get("source_urls")]
    print(f"\n=== 最终 ledger 检查：observed_public 无 URL 条目 = {len(bad)}（期望 0）===")


if __name__ == "__main__":
    main()
