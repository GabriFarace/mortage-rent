"""
Streamlit entry point for the Rent vs Buy calculator.
"""

import numpy as np
import streamlit as st
from dataclasses import replace

from simulation import Params, simulate, sweep, find_breakeven
from charts import (
    fig_net_worth, fig_cash_flows, fig_contributions, fig_decomposition,
    fig_sweep, fig_breakeven_table, fig_scenarios,
    PARAM_LABELS, PERCENT_PARAMS,
)

st.set_page_config(page_title="Rent vs Buy", page_icon="🏠", layout="wide")
st.title("🏠 Rent vs Buy Calculator")
st.caption(
    "Equal total annual cash outflow: whoever pays less in a given year invests the difference. "
    "Adjust parameters on the left; all charts update instantly."
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")

    with st.expander("Property & Mortgage", expanded=True):
        home_price = st.slider("Home price", 50_000, 1_000_000, 150_000, step=5_000,
                               format="€%d")
        down_pct_ui = st.slider("Down payment", 5.0, 40.0, 20.0, step=1.0, format="%.0f%%")
        tx_cost_ui = st.slider("Transaction cost (one-time)", 0.0, 10.0, 5.0, step=0.5, format="%.1f%%")
        mortgage_rate_ui = st.slider("Mortgage rate", 0.5, 12.0, 3.0, step=0.25, format="%.2f%%")
        monthly_payment = st.slider("Monthly payment (= initial rent)", 200, 5_000, 650, step=50,
                                    format="€%d")

    with st.expander("Market Assumptions", expanded=True):
        home_appr_ui = st.slider("Home appreciation / year", 0.0, 10.0, 2.0, step=0.5, format="%.1f%%")
        rent_infl_ui = st.slider("Rent inflation / year", 0.0, 8.0, 2.0, step=0.5, format="%.1f%%")
        index_ret_ui = st.slider("Index fund return / year", 1.0, 15.0, 5.0, step=0.5, format="%.1f%%")
        own_cost_ui = st.slider("Annual ownership cost (maintenance + tax)", 0.5, 5.0, 2.0, step=0.25,
                                format="%.2f%%")
        horizon_years = st.slider("Time horizon (years)", 10, 50, 50, step=1)

    with st.expander("Advanced", expanded=False):
        use_cgt = st.toggle("Apply capital gains tax on investments", value=False)
        cgt_rate_ui = 0.0
        if use_cgt:
            cgt_rate_ui = st.slider("Capital gains tax rate", 0.0, 50.0, 26.0, step=1.0, format="%.0f%%")

        show_real = st.toggle("Show real (inflation-adjusted) values", value=False)
        cpi_ui = 2.0
        if show_real:
            cpi_ui = st.slider("CPI (general inflation)", 0.0, 6.0, 2.0, step=0.5, format="%.1f%%")

# Convert percentage sliders (0–100 scale) to decimal
params = Params(
    home_price=float(home_price),
    down_payment_pct=down_pct_ui / 100,
    transaction_cost_pct=tx_cost_ui / 100,
    mortgage_rate=mortgage_rate_ui / 100,
    monthly_payment=float(monthly_payment),
    annual_ownership_cost_pct=own_cost_ui / 100,
    home_appreciation=home_appr_ui / 100,
    rent_inflation=rent_infl_ui / 100,
    index_return=index_ret_ui / 100,
    horizon_years=horizon_years,
    capital_gains_tax_rate=cgt_rate_ui / 100,
    cpi=cpi_ui / 100,
)

try:
    sim = simulate(params)
except ValueError as exc:
    st.error(f"Invalid parameters: {exc}")
    st.stop()

# ── Top-line metrics ───────────────────────────────────────────────────────────
mort = sim["mortgage_years"]
owner_final = sim["owner_net_worth"][horizon_years]
renter_final = sim["renter_net_worth"][horizon_years]
gap = owner_final - renter_final
winner = "Owner" if gap > 0 else "Renter"
delta_color = "normal"  # green = good regardless of direction

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Mortgage paid off", f"Year {mort}")
col_b.metric(f"Owner net worth (yr {horizon_years})", f"€{owner_final:,.0f}")
col_c.metric(f"Renter net worth (yr {horizon_years})", f"€{renter_final:,.0f}")
col_d.metric("Lead at horizon", f"€{abs(gap):,.0f}", delta=f"{winner} wins", delta_color="off")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_analysis, tab_sensitivity, tab_scenarios = st.tabs(["📊 Analysis", "🎛 Sensitivity", "📋 Scenarios"])

# ──────────────────────────────────────────────────────────────────────────────
# Tab 1: Analysis
# ──────────────────────────────────────────────────────────────────────────────
with tab_analysis:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig_net_worth(sim, real=show_real, cpi=params.cpi),
                        use_container_width=True)
        st.plotly_chart(fig_contributions(sim), use_container_width=True)
    with c2:
        st.plotly_chart(fig_cash_flows(sim), use_container_width=True)
        st.plotly_chart(fig_decomposition(sim, real=show_real, cpi=params.cpi),
                        use_container_width=True)

    st.subheader("Net worth milestones")
    milestones = [y for y in [10, 15, 20, 25, 30, 35, 40, 50] if y <= horizon_years]
    milestone_data = []
    for y in milestones:
        o = sim["owner_net_worth"][y]
        r = sim["renter_net_worth"][y]
        g = o - r
        milestone_data.append({
            "Year": y,
            "Owner net worth": f"€{o:,.0f}",
            "Renter net worth": f"€{r:,.0f}",
            "Gap": f"€{g:+,.0f}",
            "Leader": "Owner ✓" if g > 0 else "Renter ✓",
        })
    st.table(milestone_data)

# ──────────────────────────────────────────────────────────────────────────────
# Tab 2: Sensitivity
# ──────────────────────────────────────────────────────────────────────────────
with tab_sensitivity:
    st.subheader("Parameter sweep — fan chart")
    st.caption(
        "Pick a parameter: the chart shows owner advantage (owner NW − renter NW) "
        "for 10 evenly-spaced values across its range. "
        "Positive = owner ahead; negative = renter ahead."
    )

    SWEEP_PARAMS = {
        "home_appreciation": (0.0, 0.08),
        "index_return": (0.02, 0.12),
        "rent_inflation": (0.0, 0.08),
        "mortgage_rate": (0.01, 0.10),
        "home_price": (50_000, 500_000),
        "down_payment_pct": (0.05, 0.40),
    }

    sweep_param = st.selectbox(
        "Parameter to sweep",
        options=list(SWEEP_PARAMS.keys()),
        format_func=lambda k: PARAM_LABELS.get(k, k),
    )

    lo_sweep, hi_sweep = SWEEP_PARAMS[sweep_param]
    sweep_values = np.linspace(lo_sweep, hi_sweep, 10)
    sweep_sims = sweep(params, sweep_param, sweep_values)
    st.plotly_chart(fig_sweep(sweep_sims, sweep_param, sweep_values), use_container_width=True)

    st.divider()
    st.subheader("Break-even thresholds")
    st.caption(f"At what value does the outcome flip? Computed at year {horizon_years}.")

    BREAKEVEN_CONFIGS = [
        ("home_appreciation", 0.0, 0.15),
        ("index_return", 0.0, 0.20),
        ("rent_inflation", 0.0, 0.10),
        ("mortgage_rate", 0.005, 0.15),
        ("home_price", 50_000, 800_000),
    ]

    with st.spinner("Computing break-even points…"):
        breakevens = []
        for param_name, lo_b, hi_b in BREAKEVEN_CONFIGS:
            unit = "%" if param_name in PERCENT_PARAMS else "€"

            # Who wins at each boundary?
            def _gap_at(v, pn=param_name):
                try:
                    p2 = replace(params, **{pn: v})
                    s2 = simulate(p2)
                    h2 = min(horizon_years, params.horizon_years)
                    return s2["owner_net_worth"][h2] - s2["renter_net_worth"][h2]
                except ValueError:
                    return None

            g_lo = _gap_at(lo_b)
            g_hi = _gap_at(hi_b)
            bv = find_breakeven(params, param_name, lo_b, hi_b, horizon_years)

            if bv is None:
                if g_lo is not None and g_lo > 0:
                    direction = "Owner wins across entire tested range"
                elif g_lo is not None and g_lo <= 0:
                    direction = "Renter wins across entire tested range"
                else:
                    direction = "Could not evaluate"
            else:
                w_lo = "Owner" if (g_lo is not None and g_lo > 0) else "Renter"
                w_hi = "Owner" if (g_hi is not None and g_hi > 0) else "Renter"
                if unit == "%":
                    val_str = f"{bv:.2%}"
                else:
                    val_str = f"€{bv:,.0f}"
                direction = f"{w_lo} wins below {val_str} → {w_hi} wins above"

            breakevens.append({
                "param_label": PARAM_LABELS.get(param_name, param_name),
                "breakeven_value": bv,
                "unit": unit,
                "direction": direction,
            })

    st.plotly_chart(fig_breakeven_table(breakevens), use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# Tab 3: Scenarios
# ──────────────────────────────────────────────────────────────────────────────
with tab_scenarios:
    st.subheader("Scenario comparison")
    st.caption("Save up to 4 parameter sets and overlay them on one chart.")

    if "scenarios" not in st.session_state:
        st.session_state.scenarios = []

    n_saved = len(st.session_state.scenarios)
    col_name, col_save, col_clear = st.columns([3, 1, 1])
    with col_name:
        scenario_name = st.text_input("Scenario name", value=f"Scenario {n_saved + 1}",
                                      label_visibility="collapsed",
                                      placeholder="Enter scenario name…")
    with col_save:
        if st.button("💾 Save current", disabled=n_saved >= 4, use_container_width=True):
            st.session_state.scenarios.append({
                "name": scenario_name or f"Scenario {n_saved + 1}",
                "sim": sim,
                "params": params,
            })
            st.rerun()
    with col_clear:
        if st.button("🗑 Clear all", disabled=n_saved == 0, use_container_width=True):
            st.session_state.scenarios = []
            st.rerun()

    if n_saved >= 4:
        st.warning("4 scenarios saved — clear some to add more.")

    if st.session_state.scenarios:
        st.plotly_chart(fig_scenarios(st.session_state.scenarios), use_container_width=True)

        st.subheader(f"Comparison at year {horizon_years}")
        comp_rows = []
        for sc in st.session_state.scenarios:
            sc_sim = sc["sim"]
            sc_h = min(horizon_years, sc["params"].horizon_years)
            o = sc_sim["owner_net_worth"][sc_h]
            r = sc_sim["renter_net_worth"][sc_h]
            comp_rows.append({
                "Scenario": sc["name"],
                f"Owner (yr {sc_h})": f"€{o:,.0f}",
                f"Renter (yr {sc_h})": f"€{r:,.0f}",
                "Gap": f"€{o - r:+,.0f}",
                "Leader": "Owner ✓" if o > r else "Renter ✓",
                "Mortgage off": f"Yr {sc_sim['mortgage_years']}",
            })
        st.table(comp_rows)

        # Individual scenario parameter summary
        with st.expander("Parameter details"):
            for sc in st.session_state.scenarios:
                p = sc["params"]
                st.markdown(f"**{sc['name']}**: Home €{p.home_price:,.0f} | "
                            f"Mortgage {p.mortgage_rate:.2%} | "
                            f"Appreciation {p.home_appreciation:.2%} | "
                            f"Index {p.index_return:.2%} | "
                            f"Rent inflation {p.rent_inflation:.2%} | "
                            f"CGT {p.capital_gains_tax_rate:.0%}")
    else:
        st.info("No scenarios saved yet. Adjust the parameters and click **Save current**.")
