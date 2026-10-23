"""Small, intentionally constrained workflow format and explicit review receipts."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any


class ContractError(ValueError):
    pass


def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def approve(recipe: dict, reviewer: str = "local developer") -> dict:
    """A review receipt, NOT a signature or an authenticated approval service."""
    validate_recipe(recipe)
    return {"recipe_sha256": digest(recipe), "reviewer": reviewer,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "notice": "Local checksum receipt; not a cryptographic signature."}


def validate_target(target: Any) -> None:
    if not isinstance(target, list) or not 1 <= len(target) <= 3:
        raise ContractError("A target needs 1-3 explicitly approved strategies")
    for strategy in target:
        if not isinstance(strategy, dict):
            raise ContractError("Target strategies must be objects")
        by = strategy.get("by")
        allowed = {"role": {"by", "role", "name"}, "label": {"by", "value"},
                   "testid": {"by", "value"}}
        if not isinstance(by, str) or by not in allowed or set(strategy) != allowed[by]:
            raise ContractError("Only exact role/name, label, and test-id strategies are supported")
        if any(not isinstance(x, str) or not x or len(x) > 150 for x in strategy.values()):
            raise ContractError("Invalid target text")
        if by == "role" and strategy["role"] not in ("button", "link", "textbox", "heading", "status"):
            raise ContractError("Role is outside this prototype's capability set")


def validate_recipe(recipe: dict) -> None:
    if not isinstance(recipe, dict) or set(recipe) != {"schema_version", "id", "revision", "name", "parameters", "steps"}:
        raise ContractError("Unknown or missing workflow fields")
    if type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1 or type(recipe["revision"]) is not int or not 1 <= recipe["revision"] <= 100000:
        raise ContractError("Unsupported schema/revision")
    if not isinstance(recipe["id"], str) or not re.fullmatch(r"[a-z0-9-]{1,64}", recipe["id"]):
        raise ContractError("Invalid workflow ID")
    if not isinstance(recipe["name"], str) or not 1 <= len(recipe["name"]) <= 120:
        raise ContractError("Invalid workflow name")
    if recipe["parameters"] != {"topic": "string", "limit": "integer"}:
        raise ContractError("This prototype supports exactly topic and limit parameters")
    steps = recipe["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
        raise ContractError("Invalid number of steps")
    ids = set()
    for step in steps:
        if not isinstance(step, dict):
            raise ContractError("Each step must be an object")
        op = step.get("op")
        fields = {"fill": {"id", "op", "target", "value"},
                  "click": {"id", "op", "target"},
                  "wait": {"id", "op", "target"},
                  "collect": {"id", "op", "target", "download_target"}}
        if not isinstance(op, str) or op not in fields or set(step) != fields[op]:
            raise ContractError("Unknown action or unexpected action fields")
        if not isinstance(step["id"], str) or not re.fullmatch(r"[a-z0-9-]{1,64}", step["id"]) or step["id"] in ids:
            raise ContractError("Invalid or duplicated step ID")
        ids.add(step["id"])
        validate_target(step["target"])
        if op == "fill" and step["value"] != "{{topic}}":
            raise ContractError("Only the approved topic parameter can be filled")
        if op == "collect":
            validate_target(step["download_target"])
    if sum(step["op"] == "collect" for step in steps) > 1:
        raise ContractError("At most one collection loop is supported")
    if any(step["op"] == "collect" for step in steps[:-1]):
        raise ContractError("Collection must be the last step")


def validate_parameters(topic: str, limit: int) -> None:
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 80 or any(ord(c) < 32 for c in topic):
        raise ContractError("Topic must be 1-80 printable characters")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ContractError("Limit must be an integer between 1 and 20")


def load_default() -> dict:
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "recipes" / "collect-images.json"
    return json.loads(path.read_text())
