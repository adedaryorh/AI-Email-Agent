import pytest
from app.evals.run import read_dataset, score


def test_eval_scores_actual_predictions_and_rejects_missing_ids():
    rows = read_dataset("evals/seed.jsonl")
    predictions = {row["id"]: row["category"] for row in rows}
    predictions["support-1"] = "spam"
    result = score(rows, predictions)
    assert result["count"] == 28
    assert result["accuracy"] == 27 / 28
    assert result["per_category_accuracy"]["support"] == 0.75
    assert result["confusion"]["support->spam"] == 1
    del predictions["support-1"]
    with pytest.raises(ValueError):
        score(rows, predictions)


def test_agent_eval_scores_extraction_and_unsafe_false_accepts():
    from app.evals.agent import read_cases, score as score_agent
    cases = read_cases("evals/agent.jsonl")
    predictions = {}
    for row in cases:
        if row["kind"] == "extract":
            predictions[row["id"]] = row["expected"]
        elif row["kind"] == "verify":
            predictions[row["id"]] = {"passed": row["expected"]}
        else:
            predictions[row["id"]] = {"tool": "finish"}
    assert score_agent(cases, predictions)["accuracy"] == 1
    predictions["verify-2"] = {"passed": True}
    result = score_agent(cases, predictions)
    assert result["unsafe_false_accepts"] == 1
    assert result["accuracy"] == 13 / 14
    del predictions["extract-1"]
    with pytest.raises(ValueError):
        score_agent(cases, predictions)
