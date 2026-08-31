import json
from pathlib import Path


def test_evaluation_suite_has_required_coverage():
    cases = [
        json.loads(line)
        for line in Path("evals/cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    categories = {case["category"] for case in cases}
    assert len(cases) >= 25
    assert {
        "fact_extraction",
        "knowledge_update",
        "temporal",
        "cross_session",
        "abstention",
        "personality",
        "relationship",
        "persona_isolation",
        "privacy_scope",
    }.issubset(categories)
    assert len({case["id"] for case in cases}) == len(cases)
