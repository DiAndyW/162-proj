"""Analyze completed blind human evaluation exports.

Usage:
    python human_eval_tool/analyze_results.py --dir modern_llm_results --key results/20260519_232753_writer_labeled_human_eval_key.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_DIR = TOOL_DIR / "davinci_results"
DEFAULT_KEY = ROOT / "results" / "davinci_labeled_human_eval_key.json"

PREFERENCE_FIELDS = ("overall_preference", "factuality_preference", "coverage_preference")
ALLOWED_VALUES = {"A", "B", "Tie", "Unsure"}


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def decode_choice(choice: str | None, key_item: dict) -> str | None:
    if choice in ("Tie", "Unsure", None, ""):
        return choice or None
    source = key_item.get(f"summary_{choice.lower()}_source")
    if source not in {"writer", "ai"}:
        raise ValueError(f"Cannot decode preference {choice!r} for {key_item.get('review_id')}")
    return source


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{numerator / denominator:.1%}"


def distribution_lines(title: str, values: list[str | None]) -> list[str]:
    """Reproduce the ``print_distribution`` blocks (note the trailing space on the title)."""
    counts = Counter(value for value in values if value)
    total = sum(counts.values())
    lines = [f"{title} "]
    for value in ("writer", "ai", "Tie", "Unsure", "A", "B"):
        if value in counts:
            lines.append(f"  {value}: {counts[value]} ({pct(counts[value], total)})")
    return lines


def agreement(values_by_review: dict[str, list[str | None]]) -> tuple[int, int]:
    agree = total = 0
    for values in values_by_review.values():
        usable = [value for value in values if value]
        for first, second in combinations(usable, 2):
            total += 1
            if first == second:
                agree += 1
    return agree, total

# Per-rater report
def per_rater_report(rows: list[dict], key_items: dict[str, dict]) -> str:
    raw_by_field: dict[str, list[str | None]] = defaultdict(list)
    decoded_by_field: dict[str, list[str | None]] = defaultdict(list)
    model_overall: dict[str, list[str | None]] = defaultdict(list)

    for row in rows:
        key_item = key_items[row["review_id"]]
        for field in PREFERENCE_FIELDS:
            choice = row.get(field)
            raw_by_field[field].append(choice)
            decoded_by_field[field].append(decode_choice(choice, key_item))
        model_overall[key_item.get("model", "unknown")].append(
            decode_choice(row.get("overall_preference"), key_item)
        )

    lines: list[str] = []
    for field in PREFERENCE_FIELDS:
        lines += distribution_lines(f"{field} raw A/B choices", raw_by_field[field])
        lines.append("")
        lines += distribution_lines(f"{field} decoded source choices", decoded_by_field[field])
        lines.append("")

    lines.append("Model-level overall preference rates")
    for model in sorted(model_overall):
        values = [value for value in model_overall[model] if value in {"writer", "ai"}]
        if not values:
            continue
        counts = Counter(values)
        lines.append(
            f"  {model}: writer {counts['writer']} ({pct(counts['writer'], len(values))}), "
            f"ai {counts['ai']} ({pct(counts['ai'], len(values))})"
        )
    lines.append("")

    lines.append("Simple pairwise inter-rater agreement")
    for field in PREFERENCE_FIELDS:
        # A single export has no rater pairs, so always 0/0
        agree, total = agreement({row["review_id"]: [decode_choice(row.get(field), key_items[row["review_id"]])]
                                  for row in rows})
        lines.append(f"  {field}: {agree}/{total} agreeing pairs ({pct(agree, total)})")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze completed blind human eval exports.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR,
                        help="directory holding the completed exports and receiving the .txt reports")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY,
                        help="labeled human-eval key for decoding A/B into writer/ai")
    args = parser.parse_args()

    target_dir = args.dir if args.dir.is_absolute() else (TOOL_DIR / args.dir)
    key_path = args.key if args.key.is_absolute() else (ROOT / args.key)

    key_items = {item["review_id"]: item for item in load_json(key_path)}

    completed = sorted(
        p for p in target_dir.glob("human_eval_completed_*.json")
    )
    if not completed:
        raise SystemExit(f"No human_eval_completed_*.json files in {target_dir}")

    # Validate every choice before reporting, so a bad export fails loudly
    per_file: list[list[dict]] = []
    for path in completed:
        rows = load_json(path)
        for row in rows:
            if row.get("review_id") not in key_items:
                raise ValueError(f"{path} has unknown review_id {row.get('review_id')!r}")
            for field in PREFERENCE_FIELDS:
                if row.get(field) not in ALLOWED_VALUES:
                    raise ValueError(f"{path} {row.get('review_id')} bad {field}: {row.get(field)!r}")
        per_file.append(rows)

    # Per-rater reports, numbered 1..N in sorted filename order.
    for index, rows in enumerate(per_file, start=1):
        out_path = target_dir / f"eval_results_eval_{index}.txt"
        out_path.write_text(per_rater_report(rows, key_items), encoding="utf-8")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
