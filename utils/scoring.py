def calculate_points(correct: bool, response_time_ms: int) -> int:
    if not correct:
        return 0
    if response_time_ms <= 3000:
        speed_bonus = 500
    elif response_time_ms >= 15000:
        speed_bonus = 0
    else:
        speed_bonus = round(500 * (15000 - response_time_ms) / 12000)
    return 1000 + speed_bonus
