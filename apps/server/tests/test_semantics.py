"""语义校验规则单测。"""

from app.plan.checks import check_semantics, is_usable


def _base_plan() -> dict:
    return {
        "schemaVersion": "0.1",
        "meta": {"sourceType": "electronic", "floorHeight": 2.8},
        "walls": [
            {"id": "w-n", "p1": {"x": 0, "y": 0}, "p2": {"x": 4.0, "y": 0}, "thickness": 0.24, "openings": []},
            {"id": "w-e", "p1": {"x": 4.0, "y": 0}, "p2": {"x": 4.0, "y": 3.0}, "thickness": 0.24, "openings": []},
            {"id": "w-s", "p1": {"x": 4.0, "y": 3.0}, "p2": {"x": 0, "y": 3.0}, "thickness": 0.24, "openings": []},
            {"id": "w-w", "p1": {"x": 0, "y": 3.0}, "p2": {"x": 0, "y": 0}, "thickness": 0.24, "openings": []},
        ],
        "rooms": [{"id": "r-1", "name": "客厅"}],
        "scale": {
            "references": [
                {"id": "s-1", "valueM": 4.0, "p1": {"x": 0, "y": 0}, "p2": {"x": 4.0, "y": 0}, "source": "annotation"}
            ]
        },
    }


def test_clean_plan_has_no_errors() -> None:
    issues = check_semantics(_base_plan())
    assert is_usable(issues)


def test_duplicate_wall_id_rejected() -> None:
    plan = _base_plan()
    plan["walls"][1]["id"] = "w-n"
    issues = check_semantics(plan)
    assert not is_usable(issues)
    assert any(i.code == "duplicate_wall_id" for i in issues)


def test_opening_out_of_range_rejected() -> None:
    plan = _base_plan()
    plan["walls"][0]["openings"] = [
        {"id": "o-1", "type": "door", "t": 3.5, "width": 1.0, "height": 2.05, "sill": 0}
    ]
    issues = check_semantics(plan)
    assert not is_usable(issues)
    assert any(i.code == "opening_out_of_range" for i in issues)


def test_overlapping_openings_rejected() -> None:
    plan = _base_plan()
    plan["walls"][0]["openings"] = [
        {"id": "o-1", "type": "window", "t": 0.5, "width": 1.5, "height": 1.4, "sill": 0.9},
        {"id": "o-2", "type": "window", "t": 1.5, "width": 1.0, "height": 1.4, "sill": 0.9},
    ]
    issues = check_semantics(plan)
    assert not is_usable(issues)
    assert any(i.code == "openings_overlap" for i in issues)


def test_scale_deviation_beyond_tolerance_rejected() -> None:
    plan = _base_plan()
    plan["scale"]["references"][0]["valueM"] = 4.4  # 偏差 0.4 > 0.15
    issues = check_semantics(plan)
    assert not is_usable(issues)
    assert any(i.code == "scale_inconsistent" for i in issues)


def test_opening_above_ceiling_rejected() -> None:
    plan = _base_plan()
    plan["walls"][0]["openings"] = [
        {"id": "o-1", "type": "window", "t": 0.5, "width": 1.0, "height": 2.0, "sill": 1.5}
    ]
    issues = check_semantics(plan)
    assert not is_usable(issues)
    assert any(i.code == "opening_above_ceiling" for i in issues)


def test_door_with_sill_is_warning_not_error() -> None:
    plan = _base_plan()
    plan["walls"][0]["openings"] = [
        {"id": "o-1", "type": "door", "t": 0.5, "width": 0.9, "height": 2.05, "sill": 0.1}
    ]
    issues = check_semantics(plan)
    assert is_usable(issues)
    assert any(i.code == "door_with_sill" and i.level == "warning" for i in issues)


def test_unsupported_feature_is_info() -> None:
    plan = _base_plan()
    plan["meta"]["unsupportedFeatures"] = ["duplex"]
    issues = check_semantics(plan)
    assert is_usable(issues)
    assert any(i.code == "unsupported_feature" for i in issues)
