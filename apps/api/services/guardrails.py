"""Input and output guardrails for the LLM-facing agents.

These apply whether the agent is Bedrock-backed or the rule-based fallback:
- INPUT: length cap, PII redaction (never send SSN/policy numbers to a model),
  prompt-injection screening, and red-flag symptom detection (clinical urgency first).
- OUTPUT: every dollar/percent the model emits must come from the engine's facts,
  or the text is rejected; a disclaimer is always appended.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_INPUT_CHARS = 2000
DISCLAIMER = "Estimates only — actual benefits are determined when your claim is processed."

# Red-flag symptoms that need prompt in-person care — never financial optimization.
_RED_FLAGS = re.compile(
    r"\b(can'?t breathe|difficulty breathing|trouble swallowing|can'?t swallow|"
    r"facial swelling|swollen face|swelling (that )?spread|high fever|"
    r"uncontroll\w* bleeding|bleeding (that )?(won'?t|will not) stop|"
    r"severe (pain|swelling)|knocked[- ]out tooth|knocked out|avuls\w+)\b", re.I)

_EMERGENCY_MSG = (
    "This may be a dental emergency. Please contact your dentist's emergency line, or go to "
    "an urgent care or emergency room now — especially with facial swelling, trouble breathing "
    "or swallowing, a high fever, or bleeding that won't stop. Your health comes first; we can "
    "sort out benefits and costs afterward.")

# Prompt-injection markers in user text (treated as data, stripped/flagged).
_INJECTION = re.compile(
    r"(ignore (all )?(previous|prior|above) (instructions|prompts)|"
    r"disregard (the )?(system|previous)|you are now|new instructions:|"
    r"reveal (your )?(system )?prompt|act as (an?|the) )", re.I)

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_LONG_NUM = re.compile(r"\b\d{9,}\b")  # policy / member / account numbers

_DENTAL_HINT = re.compile(
    r"\b(tooth|teeth|dental|dentist|crown|filling|root canal|clean|cavity|gum|molar|implant|"
    r"brace|whiten|extract|x-?ray|exam|cover|coverage|benefit|plan|cost|deductible|estimate|"
    r"pre-?auth|network|appointment|pay|owe)\b", re.I)


@dataclass
class InputResult:
    ok: bool
    text: str                      # redacted text safe to send onward
    urgent: bool = False
    message: str | None = None     # a direct message to return without calling the model
    notes: list[str] = field(default_factory=list)


def screen_input(text: str) -> InputResult:
    notes: list[str] = []
    if not text or not text.strip():
        return InputResult(ok=False, text="", message="Tell me what procedure or question you have.")
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
        notes.append("truncated")

    redacted = _SSN.sub("[redacted-id]", text)
    redacted = _LONG_NUM.sub("[redacted-id]", redacted)
    if redacted != text:
        notes.append("pii_redacted")

    if _INJECTION.search(redacted):
        notes.append("injection_flagged")
        redacted = _INJECTION.sub("[removed]", redacted)

    if _RED_FLAGS.search(text):
        return InputResult(ok=True, text=redacted, urgent=True, message=_EMERGENCY_MSG, notes=notes + ["red_flag"])

    if not _DENTAL_HINT.search(text):
        return InputResult(ok=False, text=redacted, notes=notes + ["off_topic"],
                           message="I can help with your dental benefits — describe a procedure, "
                                   "a cost question, or your plan, and I'll walk through it.")
    return InputResult(ok=True, text=redacted, notes=notes)


_MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
_PCT = re.compile(r"\b\d{1,3}(?:\.\d+)?\s?%")


def _norm_money(s: str) -> int:
    return round(float(re.sub(r"[^\d.]", "", s)))


def check_output(text: str, allowed_amounts: set[int], allowed_pcts: set[int]) -> tuple[bool, list[str]]:
    """Every $ and % in `text` must be backed by an engine fact (within $1 / exact %)."""
    violations: list[str] = []
    for m in _MONEY.findall(text):
        v = _norm_money(m)
        if not any(abs(v - a) <= 1 for a in allowed_amounts):
            violations.append(m.strip())
    for m in _PCT.findall(text):
        v = round(float(re.sub(r"[^\d.]", "", m)))
        if v not in allowed_pcts:
            violations.append(m.strip())
    return (len(violations) == 0, violations)


def with_disclaimer(text: str) -> str:
    low = text.lower()
    if "actual" in low and ("claim" in low or "processed" in low):
        return text
    return text.rstrip() + "\n\n_" + DISCLAIMER + "_"
