from services.procedures import interpret, tooth_type


def test_deep_cleaning_needs_confirmation():
    [m] = interpret("I need a deep cleaning")
    assert m.selected_code in ("D4341", "D4342")
    assert m.requires_confirmation
    assert set(m.possible_codes) == {"D4341", "D4342"}


def test_root_canal_tooth_disambiguates_molar():
    [m] = interpret("root canal on tooth 14", tooth=14)
    assert m.selected_code == "D3330"  # molar
    assert not m.requires_confirmation


def test_multiple_procedures_in_order():
    ms = interpret("I need a root canal and then a crown")
    assert [m.procedure for m in ms] == ["Root canal", "Crown"]


def test_tooth_type():
    assert tooth_type(14) == "molar"
    assert tooth_type(8) == "anterior"
