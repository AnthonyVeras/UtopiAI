import json
import uuid

import pytest

from utopiai.dreaming import DreamPlanError, validate_plan


def valid_plan(message_id):
    return {
        "summary": "Consolidado",
        "share_worthy": True,
        "interestingness": 0.8,
        "changes": [
            {
                "operation": "add",
                "kind": "user",
                "content": "Gosta de chuva",
                "supersedes_id": None,
                "evidence_message_ids": [str(message_id)],
            }
        ],
    }


def test_validates_evidence_and_schema():
    message_id = uuid.uuid4()
    plan = validate_plan(json.dumps(valid_plan(message_id)), {message_id})
    assert plan["interestingness"] == 0.8


@pytest.mark.parametrize(
    "mutation",
    [
        lambda plan: "not-json",
        lambda plan: json.dumps([]),
        lambda plan: json.dumps({**plan, "interestingness": 2}),
        lambda plan: json.dumps({**plan, "changes": [{"operation": "delete"}]}),
        lambda plan: json.dumps({**plan, "changes": [{**plan["changes"][0], "evidence_message_ids": []}]}),
        lambda plan: json.dumps({**plan, "changes": [{**plan["changes"][0], "operation": "supersede"}]}),
    ],
)
def test_rejects_invalid_plans(mutation):
    message_id = uuid.uuid4()
    with pytest.raises(DreamPlanError):
        validate_plan(mutation(valid_plan(message_id)), {message_id})
