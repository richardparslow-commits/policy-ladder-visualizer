import math
import re

import pytest

from model import build_df, mortgage_balance


def inputs(**overrides):
    values = {
        "mortgage": 0,
        "mtg_rate": 0,
        "mtg_years": 20,
        "other_debt": 0,
        "debt_years": 5,
        "income_req": 75000,
        "income_years": 15,
        "college_total": 100000,
        "college_start": 13,
        "college_years": 4,
        "childcare_annual": 15000,
        "childcare_years": 5,
        "final_expenses": 20000,
        "liquid_assets": 0,
        "existing_life": 0,
        "existing_life_years": 10,
        "policies": [],
    }
    return values | overrides


def test_capital_required_for_remaining_obligations():
    df = build_df(**inputs())
    assert df.loc[0, "Gap"] == 1_320_000
    assert df.loc[1, "Income"] == 1_050_000
    assert df.loc[4, "Childcare"] == 15000
    assert df.loc[5, "Childcare"] == 0
    assert df.loc[12, "College"] == 100000
    assert df.loc[13, "College"] == 100000
    assert df.loc[14, "College"] == 75000
    assert df.loc[17, "College"] == 0
    assert df.loc[40, "Gap"] == 20000


@pytest.mark.parametrize("rate", [0, 1e-14, 6, 25])
@pytest.mark.parametrize("duration", [1, 20, 30])
def test_mortgage_matches_month_by_month_cashflows(rate, duration):
    principal = 400000
    monthly = rate / 1200
    n = duration * 12
    payment = (
        principal / n
        if monthly == 0
        else principal * monthly / (-math.expm1(-n * math.log1p(monthly)))
    )
    balance = principal
    for month in range(n + 1):
        if month % 12 == 0:
            assert mortgage_balance(
                principal, rate, duration, month / 12
            ) == pytest.approx(max(balance, 0), abs=1e-5)
        balance = balance * (1 + monthly) - payment
    assert mortgage_balance(principal, rate, duration, 40) == 0


def test_overlapping_terms_same_expiry_and_permanent_policy():
    policies = [
        {"amt": 100000, "prem": 100, "term": 10},
        {"amt": 200000, "prem": 200, "term": 10},
        {"amt": 50000, "prem": 50, "term": 41},
    ]
    df = build_df(
        **inputs(policies=policies, existing_life=100000, liquid_assets=10000)
    )
    assert list(df.loc[[0, 9, 10, 40], "Total Coverage"]) == [
        350000,
        350000,
        50000,
        50000,
    ]
    assert list(df.loc[[0, 9, 10, 40], "Premium"]) == [350, 350, 50, 50]
    assert list(df.loc[[9, 10], "Existing Resources"]) == [110000, 10000]


@pytest.mark.parametrize(
    "overrides",
    [
        {"income_req": -1},
        {"mortgage": float("inf")},
        {"mtg_rate": 1e99},
        {"college_years": 0},
        {"debt_years": 0},
        {"income_years": 1.5},
        {"policies": [{"amt": 100, "prem": -1, "term": 20}]},
        {"policies": [{"amt": 100, "prem": 1, "term": 20}] * 4},
        {"real_rate_pct": 11},
        {"real_rate_pct": -1},
    ],
)
def test_rejects_invalid_or_unbounded_inputs(overrides):
    with pytest.raises(ValueError):
        build_df(**inputs(**overrides))


def test_blank_mortgage_rate_allowed_only_without_a_mortgage():
    assert build_df(**inputs(mtg_rate=None)).loc[0, "Gap"] == 1_320_000
    with pytest.raises(ValueError):
        build_df(**inputs(mortgage=400000, mtg_rate=None))


def test_blank_mortgage_amount_means_no_mortgage():
    assert build_df(**inputs(mortgage=None, mtg_rate=None)).loc[0, "Gap"] == 1_320_000
    assert build_df(**inputs(mortgage=None, mtg_rate=6)).loc[0, "Gap"] == 1_320_000


def test_validation_errors_name_the_on_screen_labels():
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Years until those debts are paid off must be a whole number of years from 1 to 15 years"
        ),
    ):
        build_df(**inputs(debt_years=0.5))
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Your mortgage interest rate (%) must be a number from 0 to 25"
        ),
    ):
        build_df(**inputs(mortgage=400000, mtg_rate=None))
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Your mortgage interest rate (%) must be a number from 0 to 25"
        ),
    ):
        build_df(**inputs(mortgage=400000, mtg_rate=30))
    with pytest.raises(
        ValueError,
        match=re.escape(
            'Set "Years of college to cover" above zero when "Total college fund for the kids" is entered'
        ),
    ):
        build_df(**inputs(college_years=0))
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Policy #2: Cost per year ($) must be a number from 0 to 1,000,000"
        ),
    ):
        build_df(
            **inputs(
                policies=[
                    {"amt": 100, "prem": 1, "term": 20},
                    {"amt": 100, "prem": -1, "term": 20},
                ]
            )
        )
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Policy #1: How long it lasts (years) must be a whole number of years from 1 to 40 years, or 41 for permanent"
        ),
    ):
        build_df(**inputs(policies=[{"amt": 100, "prem": 1, "term": 41.5}]))


def test_no_liabilities_or_policies_and_permanent_existing_coverage():
    df = build_df(
        **inputs(
            income_req=0,
            childcare_annual=0,
            college_total=0,
            college_years=0,
            final_expenses=0,
            existing_life=100000,
            existing_life_years=41,
        )
    )
    assert (df["Gap"] == 0).all()
    assert (df["Total Coverage"] == 0).all()
    assert (df["Existing Resources"] == 100000).all()


def test_real_rate_discounts_income_and_college_to_present_value():
    df = build_df(**inputs(real_rate_pct=5))
    v = lambda t: 1.05**-t
    # Income is paid at the start of each remaining year; tuition is 25,000 a year in years 13-16.
    assert df.loc[0, "Income"] == pytest.approx(75000 * sum(v(t) for t in range(15)))
    assert df.loc[1, "Income"] == pytest.approx(75000 * sum(v(t) for t in range(14)))
    assert df.loc[0, "College"] == pytest.approx(
        25000 * sum(v(t) for t in range(13, 17))
    )
    assert df.loc[13, "College"] == pytest.approx(25000 * sum(v(t) for t in range(4)))
    assert df.loc[14, "College"] == pytest.approx(25000 * sum(v(t) for t in range(3)))
    # Childcare and final expenses are not discounted.
    assert df.loc[0, "Childcare"] == 75000
    assert df.loc[0, "Final Expenses"] == 20000
    assert df.loc[0, "Gap"] < 1_320_000


def test_zero_real_rate_matches_undiscounted_model():
    assert build_df(**inputs(real_rate_pct=0)).equals(build_df(**inputs()))


def coverage_by_year(policies):
    from model import MODEL_YEARS

    return [
        sum(p["amt"] for p in policies if yr < p["term"])
        for yr in range(MODEL_YEARS + 1)
    ]


def test_optimal_ladder_matches_stepped_gap_exactly():
    from model import optimal_ladder

    gap = [300_000] * 10 + [200_000] * 10 + [100_000] * 10 + [0] * 11
    policies, excess = optimal_ladder(gap)
    assert excess == 0
    assert sorted(p["term"] for p in policies if p["amt"] > 0) == [10, 20, 30]
    assert all(c >= g for c, g in zip(coverage_by_year(policies), gap))


def test_optimal_ladder_uses_permanent_for_lifetime_gap():
    from model import MODEL_YEARS, optimal_ladder

    gap = [0] * (MODEL_YEARS + 1)
    gap[MODEL_YEARS] = 50_000
    policies, excess = optimal_ladder(gap)
    # A permanent policy must pay in every year, so the only excess is its extra years of cover.
    assert excess == 50_000 * MODEL_YEARS
    assert [(p["amt"], p["term"]) for p in policies if p["amt"]] == [
        (50_000, MODEL_YEARS + 1)
    ]


def test_optimal_ladder_is_feasible_and_no_worse_than_one_permanent_policy():
    from model import MODEL_YEARS, optimal_ladder

    gap = [max(0, 400_000 - 9_000 * yr) for yr in range(MODEL_YEARS + 1)]
    policies, excess = optimal_ladder(gap)
    cover = coverage_by_year(policies)
    assert all(c >= g for c, g in zip(cover, gap))
    single_permanent_excess = sum(max(gap) - g for g in gap)
    assert excess <= single_permanent_excess
    assert excess == pytest.approx(sum(c - g for c, g in zip(cover, gap)))


def test_optimal_ladder_zero_gap_buys_nothing():
    from model import MODEL_YEARS, optimal_ladder

    policies, excess = optimal_ladder([0] * (MODEL_YEARS + 1))
    assert excess == 0
    assert all(p["amt"] == 0 for p in policies)


def test_optimal_ladder_rejects_amounts_above_policy_limit():
    from model import MAX_MONEY, MODEL_YEARS, optimal_ladder

    gap = [0] * (MODEL_YEARS + 1)
    gap[MODEL_YEARS] = MAX_MONEY + 1
    with pytest.raises(ValueError):
        optimal_ladder(gap)


def test_optimal_ladder_requires_one_gap_value_per_year():
    from model import optimal_ladder

    with pytest.raises(ValueError):
        optimal_ladder([0, 0, 0])
