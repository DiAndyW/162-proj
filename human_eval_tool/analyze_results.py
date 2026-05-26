"""Analyze completed blind human evaluation exports.

Usage:
    python human_eval_tool/analyze_results.py human_eval_completed_eval_*.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEY_PATH = ROOT / "results" / "20260519_232753_writer_labeled_human_eval_key.json"
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


def percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{numerator / denominator:.1%}"


def print_distribution(title: str, values: list[str | None]) -> None:
    counts = Counter(value for value in values if value)
    total = sum(counts.values())
    for value in ("writer", "ai", "Tie", "Unsure", "A", "B"):
        if value in counts:
            print(f"  {value}: {counts[value]} ({percent(counts[value], total)})")


def simple_pairwise_agreement(values_by_review: dict[str, list[str | None]]) -> tuple[int, int, float | None]:
    agree = 0
    total = 0
    for values in values_by_review.values():
        usable = [value for value in values if value]
        for first, second in combinations(usable, 2):
            total += 1
            if first == second:
                agree += 1
    if total == 0:
        return agree, total, None
    return agree, total, agree / total


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze completed blind human eval exports.")
    parser.add_argument("completed_files", nargs="+", type=Path)
    parser.add_argument("--key", type=Path, default=KEY_PATH)
    args = parser.parse_args()

    key_items = {item["review_id"]: item for item in load_json(args.key)}
    raw_by_field: dict[str, list[str | None]] = defaultdict(list)
    decoded_by_field: dict[str, list[str | None]] = defaultdict(list)
    model_overall: dict[str, list[str | None]] = defaultdict(list)
    agreement_values: dict[str, dict[str, list[str | None]]] = {
        field: defaultdict(list) for field in PREFERENCE_FIELDS
    }

    evaluator_count = 0
    review_ids_by_file: dict[str, set[str]] = {}

    for path in args.completed_files:
        evaluator_count += 1
        rows = load_json(path)
        review_ids_by_file[str(path)] = {row.get("review_id") for row in rows}
        for row in rows:
            review_id = row.get("review_id")
            if review_id not in key_items:
                raise ValueError(f"{path} contains unknown review_id {review_id!r}")
            key_item = key_items[review_id]
            for field in PREFERENCE_FIELDS:
                choice = row.get(field)
                if choice not in ALLOWED_VALUES:
                    raise ValueError(f"{path} {review_id} has invalid {field}: {choice!r}")
                decoded = decode_choice(choice, key_item)
                raw_by_field[field].append(choice)
                decoded_by_field[field].append(decoded)
                agreement_values[field][review_id].append(decoded)
            model = key_item.get("model", "unknown")
            model_overall[model].append(decode_choice(row.get("overall_preference"), key_item))

    shared_review_ids = set.intersection(*review_ids_by_file.values()) if review_ids_by_file else set()

    for field in PREFERENCE_FIELDS:
        print_distribution(f"{field} raw A/B choices", raw_by_field[field])
        print_distribution(f"{field} decoded source choices", decoded_by_field[field])

    print("\nModel-level overall preference rates")
    for model in sorted(model_overall):
        values = [value for value in model_overall[model] if value in {"writer", "ai"}]
        if not values:
            continue
        counts = Counter(values)
        print(
            f"  {model}: writer {counts['writer']} ({percent(counts['writer'], len(values))}), "
            f"ai {counts['ai']} ({percent(counts['ai'], len(values))})"
        )

    print("\nSimple pairwise inter-rater agreement")
    for field in PREFERENCE_FIELDS:
        agree, total, ratio = simple_pairwise_agreement(agreement_values[field])
        ratio_text = "n/a" if ratio is None else f"{ratio:.1%}"
        print(f"  {field}: {agree}/{total} agreeing pairs ({ratio_text})")


if __name__ == "__main__":
    main()
