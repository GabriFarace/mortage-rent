"""
Plotly figure builders for the rent vs buy analysis.
Pure functions: simulation dict(s) + options → Plotly Figure.
No Streamlit imports here.
"""

import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from simulation import to_real

OWNER_COLOR = "#1f77b4"
RENTER_COLOR = "#d62728"
MORTGAGE_LINE = dict(line_dash="dash", line_color="gray", opacity=0.7)

PARAM_LABELS = {
    "home_price": "Home price",
    "down_payment_pct": "Down payment",
    "transaction_cost_pct": "Transaction cost",
    "mortgage_rate": "Mortgage rate",
    "monthly_payment": "Monthly payment",
    "annual_ownership_cost_pct": "Ownership cost",
    "home_appreciation": "Home appreciation",
    "rent_inflation": "Rent inflation",
    "index_return": "Index return",
    "horizon_years": "Horizon",
}

PERCENT_PARAMS = {
    "down_payment_pct", "transaction_cost_pct", "mortgage_rate",
    "annual_ownership_cost_pct", "home_appreciation", "rent_inflation",
    "index_return",
}

_BASE_LAYOUT = dict(
    margin=dict(l=10, r=10, t=44, b=36),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    plot_bgcolor="white",
    paper_bgcolor="white",
)


def _euro_axis(fig):
    fig.update_yaxes(tickformat=",.0f", tickprefix="€", gridcolor="#eeeeee")
    fig.update_xaxes(gridcolor="#eeeeee")


def _apply_real(sim, real: bool, cpi: float):
    years = sim["years"]
    if not real or cpi <= 0:
        return sim["owner_net_worth"], sim["renter_net_worth"], sim["home_value"], sim["owner_portfolio"]
    return (
        to_real(sim["owner_net_worth"], cpi, years),
        to_real(sim["renter_net_worth"], cpi, years),
        to_real(sim["home_value"], cpi, years),
        to_real(sim["owner_portfolio"], cpi, years),
    )


# ── Analysis tab charts ─────────────────────────────────────────────────────

def fig_net_worth(sim: dict, real: bool = False, cpi: float = 0.02) -> go.Figure:
    years = sim["years"]
    owner_nw, renter_nw, _, _ = _apply_real(sim, real, cpi)
    mort = sim["mortgage_years"]
    prefix = "Real " if real else ""

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years, y=owner_nw, name="Owner",
                             line=dict(color=OWNER_COLOR, width=2.5),
                             hovertemplate="Owner: €%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=years, y=renter_nw, name="Renter",
                             line=dict(color=RENTER_COLOR, width=2.5),
                             hovertemplate="Renter: €%{y:,.0f}<extra></extra>"))
    fig.add_vline(x=mort, annotation_text=f"Mortgage ends yr {mort}",
                  annotation_position="top left", **MORTGAGE_LINE)
    fig.update_layout(title=f"{prefix}Net worth over time", xaxis_title="Year", **_BASE_LAYOUT)
    _euro_axis(fig)
    return fig


def fig_cash_flows(sim: dict) -> go.Figure:
    years = sim["years"][1:]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years, y=sim["owner_cost"][1:], name="Owner annual cost",
                             line=dict(color=OWNER_COLOR, width=2),
                             hovertemplate="Owner: €%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=years, y=sim["renter_cost"][1:], name="Annual rent",
                             line=dict(color=RENTER_COLOR, width=2),
                             hovertemplate="Rent: €%{y:,.0f}<extra></extra>"))
    fig.add_vline(x=sim["mortgage_years"], **MORTGAGE_LINE)
    fig.update_layout(title="Annual cash outflows", xaxis_title="Year", **_BASE_LAYOUT)
    _euro_axis(fig)
    return fig


def fig_contributions(sim: dict) -> go.Figure:
    years = sim["years"][1:]
    diff = sim["diff"][1:]
    renter_inv = np.where(diff > 0, diff, 0.0)
    owner_inv = np.where(diff < 0, -diff, 0.0)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=renter_inv, name="Renter invests",
                         marker_color=RENTER_COLOR, opacity=0.75))
    fig.add_trace(go.Bar(x=years, y=-owner_inv, name="Owner invests",
                         marker_color=OWNER_COLOR, opacity=0.75))
    fig.add_hline(y=0, line_color="black", line_width=0.8)
    fig.add_vline(x=sim["mortgage_years"], **MORTGAGE_LINE)
    fig.update_layout(title="Annual investment contributions", xaxis_title="Year",
                      barmode="overlay", **_BASE_LAYOUT)
    _euro_axis(fig)
    return fig


def fig_decomposition(sim: dict, real: bool = False, cpi: float = 0.02) -> go.Figure:
    years = sim["years"]
    owner_nw, renter_nw, home_val, owner_port = _apply_real(sim, real, cpi)
    prefix = "Real " if real else ""

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=home_val, fill="tozeroy", name="Home value",
        fillcolor="rgba(31,119,180,0.30)", line=dict(color=OWNER_COLOR, width=1),
        hovertemplate="Home: €%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=owner_nw, fill="tonexty", name="Owner investments",
        fillcolor="rgba(44,160,44,0.30)", line=dict(color="#2ca02c", width=1),
        hovertemplate="Owner total: €%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=renter_nw, name="Renter net worth",
        line=dict(color=RENTER_COLOR, width=2.5),
        hovertemplate="Renter: €%{y:,.0f}<extra></extra>",
    ))
    fig.add_vline(x=sim["mortgage_years"], **MORTGAGE_LINE)
    fig.update_layout(title=f"{prefix}Owner decomposition vs Renter",
                      xaxis_title="Year", **_BASE_LAYOUT)
    _euro_axis(fig)
    return fig


# ── Sensitivity tab charts ───────────────────────────────────────────────────

def fig_sweep(sims: list, param_name: str, values) -> go.Figure:
    """
    Fan chart showing owner-advantage (owner NW − renter NW) over time
    for different values of one swept parameter.
    Positive = owner ahead; negative = renter ahead.
    """
    label = PARAM_LABELS.get(param_name, param_name)
    valid = [(s, v) for s, v in zip(sims, values) if s is not None]
    n = len(valid)
    if n == 0:
        return go.Figure()

    colors = px.colors.sample_colorscale("RdBu", [i / max(n - 1, 1) for i in range(n)])

    fig = go.Figure()
    for i, (sim, v) in enumerate(valid):
        gap = sim["owner_net_worth"] - sim["renter_net_worth"]
        val_label = f"{v:.1%}" if param_name in PERCENT_PARAMS else f"€{v:,.0f}"
        fig.add_trace(go.Scatter(
            x=sim["years"], y=gap,
            name=f"{val_label}",
            line=dict(color=colors[i], width=2),
            hovertemplate=f"{label}={val_label}: €%{{y:,.0f}}<extra></extra>",
        ))

    fig.add_hline(y=0, line_dash="dot", line_color="black", line_width=1.5,
                  annotation_text="Break-even", annotation_position="bottom right")
    fig.update_layout(
        title=f"Owner advantage when sweeping '{label}'<br>"
              "<sup>Positive = owner ahead | Negative = renter ahead</sup>",
        xaxis_title="Year",
        yaxis_title="Owner NW − Renter NW",
        coloraxis_showscale=False,
        **_BASE_LAYOUT,
    )
    _euro_axis(fig)
    return fig


def fig_breakeven_table(breakevens: list) -> go.Figure:
    n = len(breakevens)
    alt = ["#f0f5fb" if i % 2 == 0 else "white" for i in range(n)]

    def fmt_val(b):
        if b["breakeven_value"] is None:
            return "—"
        if b["unit"] == "%":
            return f"{b['breakeven_value']:.2%}"
        return f"€{b['breakeven_value']:,.0f}"

    col_param = [b["param_label"] for b in breakevens]
    col_val = [fmt_val(b) for b in breakevens]
    col_dir = [b["direction"] for b in breakevens]

    fig = go.Figure(data=[go.Table(
        columnwidth=[160, 140, 400],
        header=dict(
            values=["Parameter", "Break-even value", "Interpretation"],
            fill_color=OWNER_COLOR,
            font=dict(color="white", size=13),
            align="left",
            height=32,
        ),
        cells=dict(
            values=[col_param, col_val, col_dir],
            fill_color=[alt, alt, alt],
            align="left",
            font=dict(size=12),
            height=28,
        ),
    )])
    fig.update_layout(
        title="Break-even thresholds at selected horizon year",
        margin=dict(l=10, r=10, t=44, b=10),
    )
    return fig


# ── Scenarios tab chart ──────────────────────────────────────────────────────

def fig_scenarios(scenarios: list) -> go.Figure:
    colors = px.colors.qualitative.Set2
    fig = go.Figure()
    for i, sc in enumerate(scenarios):
        sim = sc["sim"]
        name = sc["name"]
        c = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=sim["years"], y=sim["owner_net_worth"],
            name=f"{name} — Owner",
            line=dict(color=c, width=2.5),
            hovertemplate=f"{name} Owner: €%{{y:,.0f}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=sim["years"], y=sim["renter_net_worth"],
            name=f"{name} — Renter",
            line=dict(color=c, width=2, dash="dash"),
            hovertemplate=f"{name} Renter: €%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(title="Scenario comparison — net worth", xaxis_title="Year", **_BASE_LAYOUT)
    _euro_axis(fig)
    return fig
