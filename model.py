"""Bounded, deterministic insurance needs model (all amounts in today's dollars).

Rows are death-benefit needs at the beginning of each year, not annual cash flows.
No investment return, inflation, taxes, new assets, or premium quote is assumed.
All proposed policies start today. A term N covers years [0, N).
"""
import math
from numbers import Real

import pandas as pd

MODEL_YEARS = 40
MAX_MONEY = 10_000_000


def _number(value, name, maximum=MAX_MONEY):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"{name} is outside the supported range")
    return float(value)


def _years(value, name, minimum=0, maximum=MODEL_YEARS):
    value = _number(value, name, maximum)
    if value != int(value) or value < minimum:
        raise ValueError(f"{name} must be a whole number in range")
    return int(value)


def mortgage_balance(principal, annual_rate_pct, years_left, elapsed_years):
    """Monthly level-payment amortization; stable even near a zero rate."""
    principal = _number(principal, "mortgage")
    rate = _number(annual_rate_pct, "mortgage rate", 25) / 1200
    n = _years(years_left, "mortgage years", 1) * 12
    t = min(_number(elapsed_years, "elapsed years", MODEL_YEARS) * 12, n)
    if t == n or principal == 0:
        return 0.0
    if rate == 0:
        return principal * (1 - t / n)
    # Algebraically equivalent to the usual formula, without subtracting
    # nearly equal powers or computing unnecessarily large intermediate powers.
    log_growth = math.log1p(rate)
    return principal * (-math.expm1((t - n) * log_growth)) / (-math.expm1(-n * log_growth))


def build_df(mortgage, mtg_rate, mtg_years, other_debt, debt_years, income_req, income_years,
             college_total, college_start, college_years, childcare_annual, childcare_years,
             final_expenses, liquid_assets, existing_life, existing_life_years, policies):
    """Capital required to fund all remaining obligations after death in year yr."""
    amounts = dict(mortgage=mortgage, other_debt=other_debt, income_req=income_req,
                   college_total=college_total, childcare_annual=childcare_annual,
                   final_expenses=final_expenses, liquid_assets=liquid_assets,
                   existing_life=existing_life)
    amounts = {k: _number(v, k) for k, v in amounts.items()}
    mortgage, other_debt, income_req, college_total, childcare_annual, final_expenses, liquid_assets, existing_life = amounts.values()
    mtg_rate = _number(mtg_rate, "mtg_rate", 25)
    mtg_years = _years(mtg_years, "mtg_years", 1, 30)
    debt_years = _years(debt_years, "debt_years", 1, 15)
    income_years = _years(income_years, "income_years", 0, 30)
    childcare_years = _years(childcare_years, "childcare_years", 0, 15)
    college_start = _years(college_start, "college_start", 0, 25)
    college_years = _years(college_years, "college_years", 0, 8)
    existing_life_years = _years(existing_life_years, "existing_life_years", 1, MODEL_YEARS + 1)
    if college_total > 0 and college_years == 0:
        raise ValueError("Set college years above zero when a college fund is entered")
    if not isinstance(policies, (list, tuple)) or len(policies) > 3:
        raise ValueError("At most three policies are supported")
    normalized = []
    for p in policies:
        if not isinstance(p, dict) or set(p) != {"amt", "prem", "term"}:
            raise ValueError("Invalid policy fields")
        normalized.append(dict(amt=_number(p["amt"], "policy amount"),
                               prem=_number(p["prem"], "policy premium", 1_000_000),
                               term=_years(p["term"], "policy term", 1, MODEL_YEARS + 1)))
    data = []
    for yr in range(MODEL_YEARS + 1):
        m = mortgage_balance(mortgage, mtg_rate, mtg_years, yr)
        income = income_req * max(income_years - yr, 0)
        childcare = childcare_annual * max(childcare_years - yr, 0)
        remaining_college = max(college_start + college_years - max(yr, college_start), 0)
        college = college_total * remaining_college / college_years if college_years else 0
        debt = other_debt * max(1 - yr / debt_years, 0)
        liabilities = m + income + childcare + college + debt + final_expenses
        resources = liquid_assets + (existing_life if yr < existing_life_years else 0)
        live = [p for p in normalized if yr < p["term"]]
        data.append({"Year": yr, "Mortgage": m, "Debt": debt, "Income": income,
                     "Childcare": childcare, "College": college, "Final Expenses": final_expenses,
                     "Total Liabilities": liabilities, "Existing Resources": resources,
                     "Gap": max(liabilities - resources, 0),
                     "Total Coverage": sum(p["amt"] for p in live),
                     "Premium": sum(p["prem"] for p in live)})
    return pd.DataFrame(data)
