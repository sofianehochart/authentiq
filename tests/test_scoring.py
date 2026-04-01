from utils.scoring import calculate_points


def test_wrong_answer_always_zero():
    assert calculate_points(False, 500) == 0
    assert calculate_points(False, 15000) == 0


def test_correct_under_3s_max_points():
    assert calculate_points(True, 0) == 1500
    assert calculate_points(True, 3000) == 1500


def test_correct_at_15s_base_only():
    assert calculate_points(True, 15000) == 1000


def test_correct_midpoint_partial_bonus():
    # At 9000ms: speed_bonus = round(500 * (15000-9000) / 12000) = round(250.0) = 250
    assert calculate_points(True, 9000) == 1250


def test_timeout_treated_as_wrong():
    # Timeout passes response_time_ms=15000 and correct=False
    assert calculate_points(False, 15000) == 0
