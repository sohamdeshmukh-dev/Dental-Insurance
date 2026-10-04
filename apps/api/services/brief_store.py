"""Where research briefs live, so any server instance can read what another one wrote.

``BRIEFS_TABLE`` set -> DynamoDB (needed on Vercel, where instances share no memory).
Unset -> an in-process dict, which is all local dev and the test suite need.

A brief is a plain dict with a ``status`` of PENDING, RUNNING, READY or FAILED. The whole dict is
kept as one JSON string, because DynamoDB rejects Python floats (latencies, radii) in native
attributes; only ``status`` and ``updated_at`` are real attributes, for the conditional claim.
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

TTL_SECONDS = 7 * 24 * 3600  # DynamoDB TTL deletes the item after this; briefs are disposable
STALE_SECONDS = 180          # a RUNNING brief this old is assumed crashed and may be re-claimed

_MEMORY: dict[str, dict] = {}  # session_id -> {"data": brief, "updated_at": epoch seconds}
_client = None  # boto3 DynamoDB client; created lazily, replaceable in tests


def _table() -> Optional[str]:
    return os.environ.get("BRIEFS_TABLE")


def _ddb():
    global _client
    if _client is None:
        import boto3  # lazy by design, same as services/bedrock_agent.py

        region = os.environ.get("AWS_REGION") or os.environ.get("BEDROCK_REGION") or "us-east-1"
        _client = boto3.client("dynamodb", region_name=region)
    return _client


def get(session_id: str) -> Optional[dict]:
    if not _table():
        item = _MEMORY.get(session_id)
        return dict(item["data"]) if item else None
    resp = _ddb().get_item(TableName=_table(), Key={"session_id": {"S": session_id}}, ConsistentRead=True)
    item = resp.get("Item")
    if not item:
        return None
    brief = json.loads(item["data"]["S"])
    brief["status"] = item["status"]["S"]  # claim() changes the attribute, not the JSON
    return brief


def put(session_id: str, brief: dict) -> None:
    now = time.time()
    if not _table():
        _MEMORY[session_id] = {"data": dict(brief), "updated_at": now}
        return
    _ddb().put_item(TableName=_table(), Item={
        "session_id": {"S": session_id},
        "status": {"S": brief["status"]},
        "data": {"S": json.dumps(brief)},
        "updated_at": {"N": str(now)},
        "expires_at": {"N": str(int(now + TTL_SECONDS))},
    })


def claim(session_id: str) -> bool:
    """Atomically move PENDING -> RUNNING (or a stale RUNNING -> RUNNING). True means the caller
    now owns the job; False means someone else is running it, or it is already done."""
    now = time.time()
    if not _table():
        item = _MEMORY.get(session_id)
        if not item:
            return False
        status = item["data"]["status"]
        if status == "PENDING" or (status == "RUNNING" and item["updated_at"] < now - STALE_SECONDS):
            item["data"]["status"], item["updated_at"] = "RUNNING", now
            return True
        return False
    try:
        _ddb().update_item(
            TableName=_table(), Key={"session_id": {"S": session_id}},
            UpdateExpression="SET #s = :running, updated_at = :now",
            ConditionExpression="#s = :pending OR (#s = :running AND updated_at < :stale)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":running": {"S": "RUNNING"}, ":pending": {"S": "PENDING"},
                                       ":now": {"N": str(now)}, ":stale": {"N": str(now - STALE_SECONDS)}})
        return True
    except Exception as exc:
        if getattr(exc, "response", {}).get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise
