"""
Core financial simulation for rent vs buy analysis.
No UI dependencies — importable standalone.

Model: equal total annual cash outflow between owner and renter.
Whoever pays less in a given year invests the difference at index_return.
"""

import numpy as np
from dataclasses import dataclass, replace
from typing import Optional


@dataclass(init=False)
class Params:
    home_price: float = 150_000
    down_payment_pct: float = 0.20
    transaction_cost_pct: float = 0.05       # one-time, paid by owner at year 0
    mortgage_rate: float = 0.03              # annual nominal
    monthly_mortgage_payment: float = 650    # fixed monthly mortgage instalment
    initial_monthly_rent: float = 650        # year-1 monthly rent before inflation
    annual_ownership_cost_pct: float = 0.02  # maintenance + property tax, % of home value
    home_appreciation: float = 0.02          # annual nominal
    rent_inflation: float = 0.02             # annual rent growth
    index_return: float = 0.05               # annual, before tax
    horizon_years: int = 50
    capital_gains_tax_rate: float = 0.0      # applied annually as a drag on returns
    cpi: float = 0.02                        # for real-value deflation only

    def __init__(
        self,
        home_price: float = 150_000,
        down_payment_pct: float = 0.20,
        transaction_cost_pct: float = 0.05,
        mortgage_rate: float = 0.03,
        monthly_mortgage_payment: float | None = None,
        initial_monthly_rent: float | None = None,
        monthly_payment: float | None = None,
        annual_ownership_cost_pct: float = 0.02,
        home_appreciation: float = 0.02,
        rent_inflation: float = 0.02,
        index_return: float = 0.05,
        horizon_years: int = 50,
        capital_gains_tax_rate: float = 0.0,
        cpi: float = 0.02,
    ):
        legacy_payment = 650 if monthly_payment is None else monthly_payment
        self.home_price = home_price
        self.down_payment_pct = down_payment_pct
        self.transaction_cost_pct = transaction_cost_pct
        self.mortgage_rate = mortgage_rate
        self.monthly_mortgage_payment = (
            legacy_payment if monthly_mortgage_payment is None else monthly_mortgage_payment
        )
        self.initial_monthly_rent = (
            legacy_payment if initial_monthly_rent is None else initial_monthly_rent
        )
        self.annual_ownership_cost_pct = annual_ownership_cost_pct
        self.home_appreciation = home_appreciation
        self.rent_inflation = rent_inflation
        self.index_return = index_return
        self.horizon_years = horizon_years
        self.capital_gains_tax_rate = capital_gains_tax_rate
        self.cpi = cpi


def mortgage_term_years(principal: float, monthly_payment: float, annual_rate: float) -> float:
    r = annual_rate / 12
    if r == 0:
        return principal / monthly_payment / 12
    if monthly_payment <= principal * r:
        raise ValueError("Monthly payment is too small to cover interest on this loan.")
    n_months = -np.log(1 - principal * r / monthly_payment) / np.log(1 + r)
    return n_months / 12


def simulate(p: Params) -> dict:
    down_payment = p.home_price * p.down_payment_pct
    mortgage_principal = p.home_price - down_payment
    transaction_cost = p.home_price * p.transaction_cost_pct
    annual_mortgage = p.monthly_mortgage_payment * 12
    annual_rent_year1 = p.initial_monthly_rent * 12
    renter_agency_cost = p.initial_monthly_rent * 2

    mortgage_years = int(round(mortgage_term_years(
        mortgage_principal,
        p.monthly_mortgage_payment,
        p.mortgage_rate,
    )))
    H = p.horizon_years

    # Capital gains tax is modelled as an annual drag on the gross return
    effective_return = p.index_return * (1.0 - p.capital_gains_tax_rate)

    years = np.arange(0, H + 1)
    home_value = p.home_price * (1 + p.home_appreciation) ** years

    owner_cost = np.zeros(H + 1)
    renter_cost = np.zeros(H + 1)
    owner_cost[0] = down_payment + transaction_cost
    renter_cost[0] = renter_agency_cost
    for t in range(1, H + 1):
        ownership_cost_t = p.annual_ownership_cost_pct * home_value[t - 1]
        if t <= mortgage_years:
            owner_cost[t] = annual_mortgage + ownership_cost_t
        else:
            owner_cost[t] = ownership_cost_t
        renter_cost[t] = annual_rent_year1 * (1 + p.rent_inflation) ** (t - 1)

    # diff > 0  → owner spends more, renter invests the surplus
    # diff < 0  → renter spends more, owner invests the surplus
    diff = owner_cost - renter_cost

    upfront = owner_cost[0]

    # Outstanding mortgage balance at the end of each year using the standard
    # amortization formula: B(n) = P(1+r)^n − PMT·((1+r)^n − 1)/r
    r_m = p.mortgage_rate / 12  # monthly rate
    mortgage_balance = np.zeros(H + 1)
    mortgage_balance[0] = mortgage_principal
    for t in range(1, H + 1):
        if t <= mortgage_years:
            n = t * 12
            if r_m > 0:
                bal = (mortgage_principal * (1 + r_m) ** n
                       - p.monthly_mortgage_payment * ((1 + r_m) ** n - 1) / r_m)
            else:
                bal = mortgage_principal - p.monthly_mortgage_payment * n
            mortgage_balance[t] = max(0.0, bal)
        # else remains 0 (mortgage paid off)

    # Owner equity = what the owner would pocket if they sold: market value minus debt
    owner_equity = home_value - mortgage_balance

    renter_portfolio = np.zeros(H + 1)
    owner_portfolio = np.zeros(H + 1)
    renter_portfolio[0] = max(0.0, diff[0])
    owner_portfolio[0] = max(0.0, -diff[0])

    for t in range(1, H + 1):
        renter_portfolio[t] = renter_portfolio[t - 1] * (1 + effective_return)
        owner_portfolio[t] = owner_portfolio[t - 1] * (1 + effective_return)
        if diff[t] > 0:
            renter_portfolio[t] += diff[t]
        else:
            owner_portfolio[t] += -diff[t]

    return {
        "years": years,
        "home_value": home_value,
        "mortgage_balance": mortgage_balance,
        "owner_equity": owner_equity,
        "owner_cost": owner_cost,
        "renter_cost": renter_cost,
        "diff": diff,
        "renter_portfolio": renter_portfolio,
        "owner_portfolio": owner_portfolio,
        "owner_net_worth": owner_equity + owner_portfolio,
        "renter_net_worth": renter_portfolio,
        "mortgage_years": mortgage_years,
        "upfront": upfront,
        "renter_agency_cost": renter_agency_cost,
    }


def sweep(base_params: Params, param_name: str, values) -> list:
    """Run simulate() for each value of one parameter; returns None for invalid combos."""
    results = []
    for v in values:
        try:
            p = replace(base_params, **{param_name: v})
            results.append(simulate(p))
        except ValueError:
            results.append(None)
    return results


def find_breakeven(
    base_params: Params,
    param_name: str,
    lo: float,
    hi: float,
    horizon_year: Optional[int] = None,
    tol: float = 1e-5,
) -> Optional[float]:
    """
    Binary-search for the value of param_name at which owner and renter net worths
    are equal at horizon_year. Returns None if no crossover exists in [lo, hi].
    """
    h = horizon_year if horizon_year is not None else base_params.horizon_years
    h = min(h, base_params.horizon_years)

    def gap(v: float) -> float:
        p = replace(base_params, **{param_name: v})
        sim = simulate(p)
        return sim["owner_net_worth"][h] - sim["renter_net_worth"][h]

    try:
        g_lo, g_hi = gap(lo), gap(hi)
    except ValueError:
        return None

    if g_lo * g_hi > 0:
        return None  # same sign → no crossover

    for _ in range(60):
        mid = (lo + hi) / 2
        try:
            g_mid = gap(mid)
        except ValueError:
            return None
        if abs(hi - lo) < tol:
            return mid
        if g_lo * g_mid <= 0:
            hi = mid
        else:
            lo = mid
            g_lo = g_mid

    return (lo + hi) / 2


def to_real(arr: np.ndarray, cpi: float, years: np.ndarray) -> np.ndarray:
    """Deflate a nominal array by (1+cpi)^t."""
    return arr / (1 + cpi) ** years
