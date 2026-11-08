"""Labeled synthetic extraction/verification/tool-policy evaluations.

Live mode spends provider credits; offline mode scores supplied predictions.
This is a smoke dataset, not evidence of production email quality.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace


def read_cases(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Cases require unique IDs")
    for row in rows:
        if row["kind"] not in {"extract", "verify", "plan"}:
            raise ValueError("Unsupported evaluation kind")
    return rows


def score(cases, predictions):
    if set(predictions) != {row["id"] for row in cases}:
        raise ValueError("Predictions must exactly match dataset IDs")
    correct, false_accepts = 0, 0
    breakdown = {}
    for row in cases:
        predicted = predictions[row["id"]]
        expected = row["expected"]
        if row["kind"] == "extract":
            passed = all(predicted.get(key) == value for key, value in expected.items())
        elif row["kind"] == "verify":
            passed = predicted.get("passed") is expected
            false_accepts += int(expected is False and predicted.get("passed") is True)
        else:
            passed = predicted.get("tool") in expected
        correct += int(passed)
        group = breakdown.setdefault(row["kind"], {"correct": 0, "count": 0})
        group["correct"] += int(passed)
        group["count"] += 1
    return {"count": len(cases), "accuracy": correct / len(cases), "unsafe_false_accepts": false_accepts, "by_task": breakdown}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/agent.jsonl")
    parser.add_argument("--predictions", help="Score existing JSON predictions without cloud calls")
    parser.add_argument("--min-accuracy", type=float, default=0.8)
    args = parser.parse_args()
    cases = read_cases(args.dataset)
    if args.predictions:
        predictions = json.loads(Path(args.predictions).read_text())
    else:
        from app.core.config import get_settings
        from app.integrations.llm.assistant import EmailAssistant
        assistant = EmailAssistant(get_settings())
        predictions = {}
        for row in cases:
            data = row["data"]
            if row["kind"] == "extract":
                predictions[row["id"]] = assistant.extract(SimpleNamespace(sender="synthetic@example.test", subject=data["subject"], body_text=data["body"]))
            else:
                predictions[row["id"]] = getattr(assistant, row["kind"])(data)
    result = score(cases, predictions)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["accuracy"] >= args.min_accuracy and not result["unsafe_false_accepts"] else 1)


if __name__ == "__main__":
    main()
