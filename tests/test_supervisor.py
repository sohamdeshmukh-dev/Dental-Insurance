from datetime import date

from services.supervisor import run


def test_end_to_end_demo_flow():
    out = run("I need a root canal and a crown. I have Lincoln Dental and live near 19122.",
              today=date(2026, 10, 1))
    codes = [p["selected_code"] for p in out["procedures"]]
    assert "D2740" in codes  # crown
    assert any(c.startswith("D33") for c in codes)  # root canal
    assert out["providers"], "should find in-network providers"
    assert out["care_plan"]["items"]
    assert out["validation"]["status"] in ("OK", "QUALIFIED")
    assert "losing" not in out["explanation"].lower()
    assert any(e["calculation_version"] == "coverage-1.0.0" for e in out["trace"] if e["calculation_version"])


def test_unrecognized_procedure_asks_for_info():
    out = run("hello there", today=date(2026, 10, 1))
    assert out["status"] == "NEEDS_INFORMATION"
