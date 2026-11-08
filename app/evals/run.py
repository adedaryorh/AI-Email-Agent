"""Evaluate a versioned classifier against labeled JSONL, without logging message bodies."""
import argparse
import json
from collections import Counter
from pathlib import Path

CATEGORIES = {"support", "billing", "sales", "newsletter", "personal", "spam", "other"}


def read_dataset(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    ids = [row.get("id") for row in rows]
    if not rows or any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Dataset requires nonempty, unique IDs")
    for row in rows:
        if row.get("category") not in CATEGORIES or not isinstance(row.get("body_text"), str):
            raise ValueError("Every row requires a valid category and body_text")
    return rows


def score(rows, predictions):
    if set(predictions) != {row["id"] for row in rows}:
        raise ValueError("Prediction IDs must match dataset IDs exactly")
    correct, totals, hits, confusion = 0, Counter(), Counter(), Counter()
    for row in rows:
        expected, predicted = row["category"], predictions[row["id"]]
        if predicted not in CATEGORIES:
            raise ValueError("Prediction category is invalid")
        totals[expected] += 1
        confusion[(expected, predicted)] += 1
        if expected == predicted:
            correct += 1
            hits[expected] += 1
    return {"count": len(rows), "accuracy": correct / len(rows),
            "per_category_accuracy": {key: hits[key] / value for key, value in sorted(totals.items())},
            "confusion": {f"{a}->{b}": count for (a, b), count in sorted(confusion.items())}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--predictions", help="Optional JSON mapping of ID to category for offline scoring")
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    args = parser.parse_args()
    if not 0 <= args.min_accuracy <= 1:
        parser.error("min-accuracy must be in [0,1]")
    rows = read_dataset(args.dataset)
    if args.predictions:
        predictions = json.loads(Path(args.predictions).read_text())
        version, model = "offline", "provided-predictions"
    else:
        from app.core.config import get_settings
        from app.integrations.llm.classifier import LLMClassifier
        classifier = LLMClassifier(get_settings())
        predictions = {row["id"]: classifier.classify(
            sender=row.get("sender", ""), subject=row.get("subject", ""),
            body_text=row["body_text"], has_unsubscribe=row.get("has_unsubscribe", False),
        ).category.value for row in rows}
        version, model = classifier.prompt_version, classifier.model_name
    report = score(rows, predictions)
    print(json.dumps({"prompt_version": version, "model": model, **report}, indent=2))
    return 0 if report["accuracy"] >= args.min_accuracy else 1

if __name__ == "__main__":
    raise SystemExit(main())
