"""python -m app.synth [generate|eval|seed-demo]"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.synth")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Generate digital PDFs + ground truth (+ optional degradations)")
    g.add_argument("--skip-degraded", action="store_true")
    g.add_argument("--degrade-limit", type=int, default=4, help="Degrade first N layouts (memory)")
    g.add_argument("--digital-only", action="store_true")

    e = sub.add_parser("eval", help="Run accuracy harness → docs/accuracy-report.md")
    e.add_argument("--no-degraded", action="store_true")
    e.add_argument("--max-degraded-layouts", type=int, default=3)

    sub.add_parser("seed-demo", help="Seed 3 fictional profiles with ~3y quarterly data")

    args = p.parse_args(argv)
    if args.cmd == "generate":
        from app.synth.generate import generate_all

        result = generate_all(
            skip_degraded=args.skip_degraded or args.digital_only,
            degrade_layout_limit=None if args.digital_only else args.degrade_limit,
        )
        print(json.dumps({"layout_count": result["layout_count"]}, indent=2))
        return 0
    if args.cmd == "eval":
        from app.synth.eval_harness import run_eval

        run_eval(
            include_degraded=not args.no_degraded,
            max_degraded_layouts=args.max_degraded_layouts,
        )
        return 0
    if args.cmd == "seed-demo":
        from app.synth.seed_demo import seed_demo

        seed_demo()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
