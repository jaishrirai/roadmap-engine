from roadmap_engine import tools


def test_exceptions_come_first_in_listed_order(config, result):
    ranked = result.use_cases_with_sources.sort_values("Priority")
    first_ids = ranked["use_case_id"].head(len(config.exception_use_cases)).tolist()
    assert first_ids == list(config.exception_use_cases)


def test_zero_cost_use_case_goes_right_after_exceptions(config, result):
    ranked = result.use_cases_with_sources.sort_values("Priority")
    zero_cost = ranked[ranked["initial_cost"] == 0]
    assert len(zero_cost) >= 1
    assert int(zero_cost["Priority"].iloc[0]) == len(config.exception_use_cases) + 1


def test_priorities_are_one_to_n_without_gaps(result):
    p = sorted(result.use_cases_with_sources["Priority"].astype(int))
    assert p == list(range(1, len(p) + 1))


def test_shared_sources_make_later_costs_drop(result):
    u = result.use_cases_with_sources
    assert (u["Anchor_Cost"] <= u["initial_cost"] + 1e-9).all()
    assert (u["Anchor_Cost"] < u["initial_cost"] - 1e-9).any()


def test_rank_tool_matches_engine(config, data, result):
    ranked = tools.rank_use_cases(config, data)
    want = result.use_cases_with_sources.sort_values("Priority")["use_case_id"].tolist()
    assert [r["use_case_id"] for r in ranked] == want
    assert [r["priority"] for r in ranked] == list(range(1, len(want) + 1))
