"""Kavach evals: how well does the brain catch scams, and how often does it cry wolf?

    .venv\\Scripts\\python -m evals.run_evals          rules only (free, offline)
    .venv\\Scripts\\python -m evals.run_evals --llm    rules + Sarvam LLM (uses credits)

Each case is fed line by line, like a live call. We report detection rate, false alarms,
and how many lines it took to warn (earlier = better).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from backend import brain, rules  # noqa: E402


async def run_case(case, client):
    lines, red_at, yellow_at, final = [], None, None, None
    for i, line in enumerate(case["lines"], start=1):
        lines.append(line)
        text = "\n".join(lines[-14:])
        llm = await brain.llm_score(client, text) if client else None
        final = brain.fuse(rules.evaluate(text), llm)
        if final.level in ("yellow", "red") and yellow_at is None:
            yellow_at = i
        if final.level == "red" and red_at is None:
            red_at = i
    return red_at, yellow_at, final


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also use the Sarvam LLM")
    args = ap.parse_args()

    client = None
    if args.llm:
        key = os.getenv("SARVAM_API_KEY", "").strip()
        if not key:
            raise SystemExit("SARVAM_API_KEY is not set in .env")
        from sarvamai import AsyncSarvamAI
        client = AsyncSarvamAI(api_subscription_key=key)

    cases = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    scams = [c for c in cases if c["scam"]]
    normals = [c for c in cases if not c["scam"]]
    caught, warned, false_red, false_yellow, lines_to_red = 0, 0, 0, 0, []

    for c in cases:
        red_at, yellow_at, final = await run_case(c, client)
        if c["scam"]:
            caught += red_at is not None
            warned += yellow_at is not None
            if red_at:
                lines_to_red.append(red_at)
            mark = "CAUGHT" if red_at else ("WARNED" if yellow_at else "MISSED")
        else:
            false_red += red_at is not None
            false_yellow += yellow_at is not None and red_at is None
            mark = "FALSE ALARM" if red_at else ("caution" if yellow_at else "ok")
        print(f"{mark:12} {c['id']:28} score={final.score:3} type={final.scam_type}")

    print("\n--- Kavach evals", "(rules + LLM)" if client else "(rules only)", "---")
    print(f"Scams caught (red):        {caught}/{len(scams)} = {100 * caught / len(scams):.0f}%")
    print(f"Scams warned (yellow+):    {warned}/{len(scams)} = {100 * warned / len(scams):.0f}%")
    print(f"False red alarms:          {false_red}/{len(normals)}")
    print(f"Normal calls with caution: {false_yellow}/{len(normals)}")
    if lines_to_red:
        print(f"Avg lines until red:       {sum(lines_to_red) / len(lines_to_red):.1f}")


if __name__ == "__main__":
    asyncio.run(main())
