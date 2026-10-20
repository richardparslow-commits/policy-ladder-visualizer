"""Bounded, deterministic insurance needs model (all amounts in today's dollars).

Rows are death-benefit needs at the beginning of each year, not annual cash flows.
Income and college are discounted to today's dollars at an optional inflation-adjusted
return (default 0). No inflation, taxes, new assets, or premium quote is assumed.
All proposed policies start today. A term N covers years [0, N).
"""

import itertools
import math
from numbers import Real

import pandas as pd

MODEL_YEARS = 40
MAX_MONEY = 10_000_000
LADDER_TERMS = (10, 15, 20, 25, 30, MODEL_YEARS + 1)  # MODEL_YEARS + 1 = permanent
LADDER_STEP = 10_000  # Auto-built amounts round up to the same step the inputs use

# On-screen labels, so validation errors name the fields the user actually sees.
LABELS = {
    "mortgage": "Money still owed on your mortgage",
    "mtg_rate": "Your mortgage interest rate (%)",
    "mtg_years": "Years left on your mortgage",
    "other_debt": "Other debts (car, cards, loans)",
    "debt_years": "Years until those debts are paid off",
    "income_req": "Yearly income your family would need",
    "income_years": "How many years it must last",
    "college_total": "Total college fund for the kids",
    "college_start": "Years until college starts",
    "college_years": "Years of college to cover",
    "childcare_annual": "Childcare cost per year",
    "childcare_years": "Years of childcare needed",
    "final_expenses": "Funeral / final expenses",
    "liquid_assets": "Cash, savings & investments",
    "existing_life": "Life insurance you already own",
    "existing_life_years": "Years left on that policy",
    "real_rate_pct": "Inflation-adjusted return (%)",
}


def _amount_range(maximum):
    """Describes the allowed amounts, e.g. 'from 0 to 1,000,000'."""
    return "0 or more" if math.isinf(maximum) else f"from 0 to {maximum:,.0f}"


def _year_range(minimum, maximum):
    """Describes the allowed years; the top model term is permanent coverage."""
    if maximum == MODEL_YEARS + 1:
        return f"from {minimum} to {MODEL_YEARS} years, or {maximum} for permanent"
    return f"from {minimum} to {maximum} years"


def _number(value, name, maximum=MAX_MONEY):
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
        or not 0 <= value <= maximum
    ):
        raise ValueError(f"{name} must be a number {_amount_range(maximum)}")
    return float(value)


def _years(value, name, minimum=0, maximum=MODEL_YEARS):
    message = f"{name} must be a whole number of years {_year_range(minimum, maximum)}"
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
    ):
        raise ValueError(message)
    if value != int(value) or not minimum <= value <= maximum:
        raise ValueError(message)
    return int(value)


def mortgage_balance(principal, annual_rate_pct, years_left, elapsed_years):
    """Monthly level-payment amortization; stable even near a zero rate."""
    principal = _number(principal, LABELS["mortgage"])
    rate = _number(annual_rate_pct, LABELS["mtg_rate"], 25) / 1200
    n = _years(years_left, LABELS["mtg_years"], 1) * 12
    t = min(_number(elapsed_years, "elapsed years", MODEL_YEARS) * 12, n)
    if t == n or principal == 0:
        return 0.0
    if rate == 0:
        return principal * (1 - t / n)
    # Algebraically equivalent to the usual formula, without subtracting
    # nearly equal powers or computing unnecessarily large intermediate powers.
    log_growth = math.log1p(rate)
    return (
        principal * (-math.expm1((t - n) * log_growth)) / (-math.expm1(-n * log_growth))
    )


def _present_value(amount, first, count, rate_pct):
    """Value at the start of the current year of `count` payments of `amount`, the first `first` years out."""
    v = 1 / (1 + rate_pct / 100)
    return amount * sum(v**t for t in range(first, first + count))


def build_df(
    mortgage,
    mtg_rate,
    mtg_years,
    other_debt,
    debt_years,
    income_req,
    income_years,
    college_total,
    college_start,
    college_years,
    childcare_annual,
    childcare_years,
    final_expenses,
    liquid_assets,
    existing_life,
    existing_life_years,
    policies,
    real_rate_pct=0.0,
):
    """Capital required to fund all remaining obligations after death in year yr."""
    if mortgage is None:  # Blank mortgage amount means no mortgage.
        mortgage = 0
    amounts = {
        "mortgage": mortgage,
        "other_debt": other_debt,
        "income_req": income_req,
        "college_total": college_total,
        "childcare_annual": childcare_annual,
        "final_expenses": final_expenses,
        "liquid_assets": liquid_assets,
        "existing_life": existing_life,
    }
    amounts = {k: _number(v, LABELS[k]) for k, v in amounts.items()}
    (
        mortgage,
        other_debt,
        income_req,
        college_total,
        childcare_annual,
        final_expenses,
        liquid_assets,
        existing_life,
    ) = amounts.values()
    if mtg_rate is None and mortgage == 0:  # No mortgage, so the rate does not apply.
        mtg_rate = 0.0
    mtg_rate = _number(mtg_rate, LABELS["mtg_rate"], 25)
    mtg_years = _years(mtg_years, LABELS["mtg_years"], 1, 30)
    debt_years = _years(debt_years, LABELS["debt_years"], 1, 15)
    income_years = _years(income_years, LABELS["income_years"], 0, 30)
    childcare_years = _years(childcare_years, LABELS["childcare_years"], 0, 15)
    college_start = _years(college_start, LABELS["college_start"], 0, 25)
    college_years = _years(college_years, LABELS["college_years"], 0, 8)
    existing_life_years = _years(
        existing_life_years, LABELS["existing_life_years"], 1, MODEL_YEARS + 1
    )
    real_rate_pct = _number(real_rate_pct, LABELS["real_rate_pct"], 10)
    if college_total > 0 and college_years == 0:
        raise ValueError(
            f'Set "{LABELS["college_years"]}" above zero when "{LABELS["college_total"]}" is entered'
        )
    if not isinstance(policies, (list, tuple)) or len(policies) > 3:
        raise ValueError("You can enter up to 3 policies")
    normalized = []
    for i, p in enumerate(policies, start=1):
        if not isinstance(p, dict) or set(p) != {"amt", "prem", "term"}:
            raise ValueError("Each policy needs an amount, a yearly cost and a term")
        normalized.append(
            {
                "amt": _number(p["amt"], f"Policy #{i}: Amount it pays out ($)"),
                "prem": _number(
                    p["prem"], f"Policy #{i}: Cost per year ($)", 1_000_000
                ),
                "term": _years(
                    p["term"],
                    f"Policy #{i}: How long it lasts (years)",
                    1,
                    MODEL_YEARS + 1,
                ),
            }
        )
    data = []
    for yr in range(MODEL_YEARS + 1):
        m = mortgage_balance(mortgage, mtg_rate, mtg_years, yr)
        income = _present_value(income_req, 0, max(income_years - yr, 0), real_rate_pct)
        childcare = childcare_annual * max(childcare_years - yr, 0)
        remaining_college = max(
            college_start + college_years - max(yr, college_start), 0
        )
        college = (
            _present_value(
                college_total / college_years,
                max(college_start - yr, 0),
                remaining_college,
                real_rate_pct,
            )
            if college_years
            else 0
        )
        debt = other_debt * max(1 - yr / debt_years, 0)
        liabilities = m + income + childcare + college + debt + final_expenses
        resources = liquid_assets + (existing_life if yr < existing_life_years else 0)
        live = [p for p in normalized if yr < p["term"]]
        data.append(
            {
                "Year": yr,
                "Mortgage": m,
                "Debt": debt,
                "Income": income,
                "Childcare": childcare,
                "College": college,
                "Final Expenses": final_expenses,
                "Total Liabilities": liabilities,
                "Existing Resources": resources,
                "Gap": max(liabilities - resources, 0),
                "Total Coverage": sum(p["amt"] for p in live),
                "Premium": sum(p["prem"] for p in live),
            }
        )
    return pd.DataFrame(data)


def optimal_ladder(gap, slots=3, step=LADDER_STEP):
    """Exact minimum-excess ladder that covers `gap` in every model year.

    `gap` holds the required death benefit for years 0..MODEL_YEARS. Each slot is a
    term from LADDER_TERMS (or permanent) with an amount, and policy i pays in years
    before its term. For a fixed set of terms the cheapest amounts are a suffix-sum
    greedy from the longest term back, so every term combination is searched exactly.
    Returns (policies, excess): policies is a list of {"amt", "term"} dicts sorted by
    term (amt 0 = unused slot) and excess is coverage above the gap summed over the
    model years, in dollar-years. Amounts are rounded up to `step` and stay feasible.
    """
    gap = [_number(g, "gap", math.inf) for g in gap]
    if len(gap) != MODEL_YEARS + 1:
        raise ValueError(
            f"gap must have exactly {MODEL_YEARS + 1} values, one for each year from 0 to {MODEL_YEARS}"
        )
    best = None
    for terms in itertools.combinations_with_replacement(LADDER_TERMS, slots):
        # Year y is covered by policies whose term exceeds y. Segment j is the years
        # [terms[j-1], terms[j]) where policies j.. are alive; the tail after the last
        # term is covered by nothing, so the gap there must already be zero.
        bounds = [0, *terms, MODEL_YEARS + 1]
        need = [
            max(gap[bounds[j] : bounds[j + 1]], default=0.0) for j in range(slots + 1)
        ]
        if need[slots] > 0:
            continue
        suffix = [0.0] * (
            slots + 1
        )  # coverage in segment j, built from the longest term back
        for j in range(slots - 1, -1, -1):
            suffix[j] = max(need[j], suffix[j + 1])
        amounts = [
            math.ceil(round(suffix[j] - suffix[j + 1], 2) / step) * step
            for j in range(slots)
        ]
        if any(a > MAX_MONEY for a in amounts):
            continue
        policies = [{"amt": float(a), "term": t} for a, t in zip(amounts, terms)]
        cover = [
            sum(p["amt"] for p in policies if yr < p["term"])
            for yr in range(MODEL_YEARS + 1)
        ]
        excess = sum(c - g for c, g in zip(cover, gap))
        key = (excess, sum(p["amt"] > 0 for p in policies), sum(amounts))
        if best is None or key < best[0]:
            best = (key, policies, excess)
    if best is None:
        terms = ", ".join(str(t) for t in LADDER_TERMS[:-1])
        raise ValueError(
            f"No ladder fits: each policy amount must be at most {MAX_MONEY:,.0f}, and the gap must be covered by terms of {terms} years or permanent"
        )
    return best[1], best[2]
