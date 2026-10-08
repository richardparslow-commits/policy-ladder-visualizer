import math
import pytest
from model import build_df, mortgage_balance


def inputs(**overrides):
    values=dict(mortgage=0,mtg_rate=0,mtg_years=20,other_debt=0,debt_years=5,
                income_req=75000,income_years=15,college_total=100000,college_start=13,
                college_years=4,childcare_annual=15000,childcare_years=5,final_expenses=20000,
                liquid_assets=0,existing_life=0,existing_life_years=10,policies=[])
    return values | overrides


def test_capital_required_for_remaining_obligations():
    df=build_df(**inputs())
    assert df.loc[0,'Gap']==1_320_000
    assert df.loc[1,'Income']==1_050_000
    assert df.loc[4,'Childcare']==15000
    assert df.loc[5,'Childcare']==0
    assert df.loc[12,'College']==100000
    assert df.loc[13,'College']==100000
    assert df.loc[14,'College']==75000
    assert df.loc[17,'College']==0
    assert df.loc[40,'Gap']==20000


@pytest.mark.parametrize('rate',[0,1e-14,6,25])
@pytest.mark.parametrize('duration',[1,20,30])
def test_mortgage_matches_month_by_month_cashflows(rate,duration):
    principal=400000
    monthly=rate/1200
    n=duration*12
    payment=principal/n if monthly==0 else principal*monthly/(-math.expm1(-n*math.log1p(monthly)))
    balance=principal
    for month in range(n+1):
        if month%12==0:
            assert mortgage_balance(principal,rate,duration,month/12)==pytest.approx(max(balance,0),abs=1e-5)
        balance=balance*(1+monthly)-payment
    assert mortgage_balance(principal,rate,duration,40)==0


def test_overlapping_terms_same_expiry_and_permanent_policy():
    policies=[dict(amt=100000,prem=100,term=10),dict(amt=200000,prem=200,term=10),dict(amt=50000,prem=50,term=41)]
    df=build_df(**inputs(policies=policies,existing_life=100000,liquid_assets=10000))
    assert list(df.loc[[0,9,10,40],'Total Coverage'])==[350000,350000,50000,50000]
    assert list(df.loc[[0,9,10,40],'Premium'])==[350,350,50,50]
    assert list(df.loc[[9,10],'Existing Resources'])==[110000,10000]


@pytest.mark.parametrize('overrides',[{'income_req':-1},{'mortgage':float('inf')},
    {'mtg_rate':1e99},{'college_years':0},{'debt_years':0},{'income_years':1.5},
    {'policies':[dict(amt=100,prem=-1,term=20)]},
    {'policies':[dict(amt=100,prem=1,term=20)]*4}])
def test_rejects_invalid_or_unbounded_inputs(overrides):
    with pytest.raises(ValueError): build_df(**inputs(**overrides))


def test_no_liabilities_or_policies_and_permanent_existing_coverage():
    df=build_df(**inputs(income_req=0,childcare_annual=0,college_total=0,college_years=0,final_expenses=0,
                         existing_life=100000,existing_life_years=41))
    assert (df['Gap']==0).all()
    assert (df['Total Coverage']==0).all()
    assert (df['Existing Resources']==100000).all()
