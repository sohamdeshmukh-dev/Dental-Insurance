"""Procedure intelligence: catalog + natural-language normalization.

CDT codes are never assigned silently: ambiguous matches return all candidates plus
`requires_confirmation`.
"""
from __future__ import annotations

import re
from typing import Optional

from schemas import Procedure, ProcedureMatch

_P = Procedure
CATALOG: dict[str, Procedure] = {p.code: p for p in [
    _P(code="D0120", name="Periodic oral evaluation", category="preventive", family="exam", clinical_priority=9),
    _P(code="D0274", name="Bitewing X-rays (four films)", category="preventive", family="xray", clinical_priority=9),
    _P(code="D1110", name="Adult cleaning (prophylaxis)", category="preventive", family="cleaning", clinical_priority=8),
    _P(code="D4341", name="Scaling and root planing (4+ teeth per quadrant)", category="basic", family="perio", clinical_priority=2,
       description="Deep cleaning below the gumline to treat gum disease."),
    _P(code="D4342", name="Scaling and root planing (1-3 teeth per quadrant)", category="basic", family="perio", clinical_priority=2),
    _P(code="D2391", name="Resin filling, one surface, back tooth", category="basic", family="filling", clinical_priority=3),
    _P(code="D7140", name="Simple extraction", category="basic", family="extraction", clinical_priority=3),
    _P(code="D3310", name="Root canal, front tooth", category="basic", family="endo", clinical_priority=2),
    _P(code="D3320", name="Root canal, premolar", category="basic", family="endo", clinical_priority=2),
    _P(code="D3330", name="Root canal, molar", category="basic", family="endo", clinical_priority=2,
       description="Removes infected pulp from inside the tooth and seals it."),
    _P(code="D2740", name="Crown, porcelain/ceramic", category="major", family="crown", clinical_priority=4,
       prerequisite_families=["endo"], min_gap_months=1),
    _P(code="D2750", name="Crown, porcelain fused to high noble metal", category="major", family="crown", clinical_priority=4,
       prerequisite_families=["endo"], min_gap_months=1),
]}

_MOLARS = {1, 2, 3, 14, 15, 16, 17, 18, 19, 30, 31, 32}
_PREMOLARS = {4, 5, 12, 13, 20, 21, 28, 29}

# phrase -> (display name, candidate codes, default code, base confidence)
_ALIASES: list[tuple[str, str, list[str], str, float]] = [
    (r"deep clean|scaling|root planing|gum (disease|treatment)", "Scaling and root planing", ["D4341", "D4342"], "D4341", 0.86),
    (r"root canal|endodontic", "Root canal", ["D3310", "D3320", "D3330"], "D3330", 0.75),
    (r"crown|cap\b", "Crown", ["D2740", "D2750"], "D2740", 0.80),
    (r"cleaning|prophy", "Cleaning", ["D1110"], "D1110", 0.95),
    (r"x-?ray|bitewing", "X-rays", ["D0274"], "D0274", 0.95),
    (r"filling|cavity", "Filling", ["D2391"], "D2391", 0.85),
    (r"extract|pulled|tooth removal", "Extraction", ["D7140"], "D7140", 0.85),
    (r"\bexam\b|checkup|check-up", "Exam", ["D0120"], "D0120", 0.95),
]


def tooth_type(tooth: int) -> str:
    if tooth in _MOLARS:
        return "molar"
    if tooth in _PREMOLARS:
        return "premolar"
    return "anterior"


def interpret(text: str, tooth: Optional[int] = None) -> list[ProcedureMatch]:
    low = text.lower()
    found: list[tuple[int, ProcedureMatch]] = []
    taken: list[tuple[int, int]] = []
    for pattern, name, codes, default, conf in _ALIASES:
        m = re.search(pattern, low)
        if not m or any(s <= m.start() < e for s, e in taken):
            continue
        taken.append((m.start(), m.end()))
        selected, confidence, confirm, note = default, conf, len(codes) > 1 or conf < 0.9, ""
        if name == "Root canal" and tooth:
            selected = {"molar": "D3330", "premolar": "D3320", "anterior": "D3310"}[tooth_type(tooth)]
            confidence, confirm = 0.95, False
            note = f"Tooth {tooth} is a {tooth_type(tooth)}."
        elif confirm:
            note = "Code assumed; confirm with your dentist's treatment plan."
        found.append((m.start(), ProcedureMatch(
            procedure=name, possible_codes=codes, selected_code=selected,
            confidence=confidence, requires_confirmation=confirm, note=note)))
    return [m for _, m in sorted(found, key=lambda x: x[0])]
