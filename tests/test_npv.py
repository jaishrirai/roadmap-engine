import pytest

from roadmap_engine import calculate_npv, tools


def test_npv_hand_calculated():
    # 100/1.1 + 200/1.21 + 300/1.331 - 50
    assert calculate_npv([100, 200, 300], 50, 0.10) == pytest.approx(431.5927874, rel=1e-8)


def test_npv_zero_rate_is_sum_minus_cost():
    assert calculate_npv([10, 20, 30], 5, 0.0) == pytest.approx(55)


def test_tool_matches_engine_and_lists_discounted_values():
    out = tools.calculate_npv([100, 200, 300], costs=50, rate=0.10)
    assert out["npv"] == pytest.approx(431.5927874, rel=1e-8)
    assert out["discounted_values"][0] == pytest.approx(100 / 1.1)
    assert sorted(out) == ["costs", "discounted_values", "npv", "rate"]


@pytest.mark.parametrize("values,costs,rate", [([], 0, 0.1), ([1], -1, 0.1), ([1], 0, -1)])
def test_tool_rejects_bad_input(values, costs, rate):
    with pytest.raises(ValueError):
        tools.calculate_npv(values, costs, rate)
