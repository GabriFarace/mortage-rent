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
MORTGAGE_LINE = dict(line_dash="dash", line_color="#888888", opacity=0.8)

PERCENT_PARAMS = {
    "down_payment_pct", "transaction_cost_pct", "mortgage_rate",
    "annual_ownership_cost_pct", "home_appreciation", "rent_inflation",
    "index_return",
}

# English parameter labels (used as fallback when no label is passed)
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

# Chart-level translation strings
_T = {
    "en": {
        "net_worth": "Net worth over time",
        "real_net_worth": "Real net worth over time",
        "cash_flows": "Annual cash outflows",
        "contributions": "Annual investment contributions",
        "decomposition": "Owner wealth decomposition vs Renter",
        "real_decomposition": "Real owner wealth decomposition vs Renter",
        "scenarios": "Scenario comparison — net worth",
        "year": "Year",
        "owner": "Owner",
        "renter": "Renter",
        "owner_cost": "Owner annual cost",
        "annual_rent": "Annual rent",
        "renter_invests": "Renter invests",
        "owner_invests": "Owner invests",
        "owner_equity": "Owner equity (home − debt)",
        "owner_investments": "Owner investments",
        "renter_nw": "Renter net worth",
        "breakeven_line": "Break-even",
        "mortgage_ends": "Mortgage ends yr {n}",
        "owner_advantage": "Owner NW − Renter NW",
        "sweep_title": "Owner advantage when sweeping '{label}'",
        "sweep_subtitle": "Positive = owner ahead | Negative = renter ahead",
        "scenario_owner": "{name} — Owner",
        "scenario_renter": "{name} — Renter",
    },
    "it": {
        "net_worth": "Patrimonio nel tempo",
        "real_net_worth": "Patrimonio reale nel tempo",
        "cash_flows": "Uscite annuali",
        "contributions": "Contributi annui all'investimento",
        "decomposition": "Composizione patrimonio proprietario vs Affittuario",
        "real_decomposition": "Composizione patrimonio reale vs Affittuario",
        "scenarios": "Confronto scenari — patrimonio",
        "year": "Anno",
        "owner": "Proprietario",
        "renter": "Affittuario",
        "owner_cost": "Costo annuo proprietario",
        "annual_rent": "Affitto annuo",
        "renter_invests": "Affittuario investe",
        "owner_invests": "Proprietario investe",
        "owner_equity": "Patrimonio netto immobiliare (immobile − debito)",
        "owner_investments": "Investimenti proprietario",
        "renter_nw": "Patrimonio affittuario",
        "breakeven_line": "Indifferenza",
        "mortgage_ends": "Fine mutuo anno {n}",
        "owner_advantage": "NW Propr. − NW Affitt.",
        "sweep_title": "Vantaggio proprietario al variare di '{label}'",
        "sweep_subtitle": "Positivo = proprietario avanti | Negativo = affittuario avanti",
        "scenario_owner": "{name} — Proprietario",
        "scenario_renter": "{name} — Affittuario",
    },
}

# Base layout: plotly_white template ensures visible dark text on white background.
# Left margin increased so y-axis title is not clipped.
_BASE_LAYOUT = dict(
    template="plotly_white",
    margin=dict(l=80, r=20, t=65, b=55),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    font=dict(color="#1a1a2e", size=12),
    title_font=dict(size=14, color="#1a1a2e"),
)


def _t(lang: str, key: str, **kwargs) -> str:
    s = _T.get(lang, _T["en"]).get(key, _T["en"].get(key, key))
    return s.format(**kwargs) if kwargs else s


def _euro_axis(fig, lang: str = "en"):
    fig.update_yaxes(
        tickformat=",.0f",
        tickprefix="€",
        title_font=dict(color="#1a1a2e"),
        tickfont=dict(color="#1a1a2e"),
    )
    fig.update_xaxes(
        title_text=_t(lang, "year"),
        title_font=dict(color="#1a1a2e"),
        tickfont=dict(color="#1a1a2e"),
    )


def _apply_real(sim, real: bool, cpi: float):
    years = sim["years"]
    if not real or cpi <= 0:
        return sim["owner_net_worth"], sim["renter_net_worth"], sim["owner_equity"], sim["owner_portfolio"]
    return (
        to_real(sim["owner_net_worth"], cpi, years),
        to_real(sim["renter_net_worth"], cpi, years),
        to_real(sim["owner_equity"], cpi, years),
        to_real(sim["owner_portfolio"], cpi, years),
    )


# ── Analysis tab ─────────────────────────────────────────────────────────────

def fig_net_worth(sim: dict, real: bool = False, cpi: float = 0.02, lang: str = "en") -> go.Figure:
    years = sim["years"]
    owner_nw, renter_nw, _, _ = _apply_real(sim, real, cpi)
    mort = sim["mortgage_years"]
    title_key = "real_net_worth" if real else "net_worth"
    owner_lbl = _t(lang, "owner")
    renter_lbl = _t(lang, "renter")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=owner_nw, name=owner_lbl,
        line=dict(color=OWNER_COLOR, width=2.5),
        hovertemplate=f"{owner_lbl}: €%{{y:,.0f}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=renter_nw, name=renter_lbl,
        line=dict(color=RENTER_COLOR, width=2.5),
        hovertemplate=f"{renter_lbl}: €%{{y:,.0f}}<extra></extra>",
    ))
    fig.add_vline(
        x=mort,
        annotation_text=_t(lang, "mortgage_ends", n=mort),
        annotation_position="top left",
        annotation_font=dict(color="#555555", size=11),
        **MORTGAGE_LINE,
    )
    fig.update_layout(title=_t(lang, title_key), **_BASE_LAYOUT)
    _euro_axis(fig, lang)
    return fig


def fig_cash_flows(sim: dict, lang: str = "en") -> go.Figure:
    years = sim["years"][1:]
    owner_lbl = _t(lang, "owner_cost")
    renter_lbl = _t(lang, "annual_rent")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=sim["owner_cost"][1:], name=owner_lbl,
        line=dict(color=OWNER_COLOR, width=2),
        hovertemplate=f"{owner_lbl}: €%{{y:,.0f}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=sim["renter_cost"][1:], name=renter_lbl,
        line=dict(color=RENTER_COLOR, width=2),
        hovertemplate=f"{renter_lbl}: €%{{y:,.0f}}<extra></extra>",
    ))
    fig.add_vline(x=sim["mortgage_years"], **MORTGAGE_LINE)
    fig.update_layout(title=_t(lang, "cash_flows"), **_BASE_LAYOUT)
    _euro_axis(fig, lang)
    return fig


def fig_contributions(sim: dict, lang: str = "en") -> go.Figure:
    years = sim["years"][1:]
    diff = sim["diff"][1:]
    renter_inv = np.where(diff > 0, diff, 0.0)
    owner_inv = np.where(diff < 0, -diff, 0.0)
    renter_lbl = _t(lang, "renter_invests")
    owner_lbl = _t(lang, "owner_invests")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=renter_inv, name=renter_lbl,
                         marker_color=RENTER_COLOR, opacity=0.75))
    fig.add_trace(go.Bar(x=years, y=-owner_inv, name=owner_lbl,
                         marker_color=OWNER_COLOR, opacity=0.75))
    fig.add_hline(y=0, line_color="#333333", line_width=0.8)
    fig.add_vline(x=sim["mortgage_years"], **MORTGAGE_LINE)
    fig.update_layout(title=_t(lang, "contributions"), barmode="overlay", **_BASE_LAYOUT)
    _euro_axis(fig, lang)
    return fig


def fig_decomposition(sim: dict, real: bool = False, cpi: float = 0.02, lang: str = "en") -> go.Figure:
    years = sim["years"]
    owner_nw, renter_nw, equity_val, _ = _apply_real(sim, real, cpi)
    title_key = "real_decomposition" if real else "decomposition"
    equity_lbl = _t(lang, "owner_equity")
    inv_lbl = _t(lang, "owner_investments")
    renter_lbl = _t(lang, "renter_nw")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=equity_val, fill="tozeroy", name=equity_lbl,
        fillcolor="rgba(31,119,180,0.28)", line=dict(color=OWNER_COLOR, width=1),
        hovertemplate=f"{equity_lbl}: €%{{y:,.0f}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=owner_nw, fill="tonexty", name=inv_lbl,
        fillcolor="rgba(44,160,44,0.28)", line=dict(color="#2ca02c", width=1),
        hovertemplate=f"Total: €%{{y:,.0f}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=renter_nw, name=renter_lbl,
        line=dict(color=RENTER_COLOR, width=2.5),
        hovertemplate=f"{renter_lbl}: €%{{y:,.0f}}<extra></extra>",
    ))
    fig.add_vline(x=sim["mortgage_years"], **MORTGAGE_LINE)
    fig.update_layout(title=_t(lang, title_key), **_BASE_LAYOUT)
    _euro_axis(fig, lang)
    return fig


# ── Sensitivity tab ───────────────────────────────────────────────────────────

def fig_sweep(
    sims: list,
    param_name: str,
    values,
    param_label: str = None,
    lang: str = "en",
) -> go.Figure:
    """Fan chart: owner NW − renter NW for each swept parameter value."""
    label = param_label or PARAM_LABELS.get(param_name, param_name)
    valid = [(s, v) for s, v in zip(sims, values) if s is not None]
    if not valid:
        return go.Figure()

    n = len(valid)
    colors = px.colors.sample_colorscale("RdBu", [i / max(n - 1, 1) for i in range(n)])

    fig = go.Figure()
    for i, (sim, v) in enumerate(valid):
        gap = sim["owner_net_worth"] - sim["renter_net_worth"]
        val_label = f"{v:.1%}" if param_name in PERCENT_PARAMS else f"€{v:,.0f}"
        fig.add_trace(go.Scatter(
            x=sim["years"], y=gap,
            name=val_label,
            line=dict(color=colors[i], width=2),
            hovertemplate=f"{label}={val_label}: €%{{y:,.0f}}<extra></extra>",
        ))

    fig.add_hline(
        y=0, line_dash="dot", line_color="#333333", line_width=1.5,
        annotation_text=_t(lang, "breakeven_line"),
        annotation_position="bottom right",
        annotation_font=dict(color="#333333"),
    )
    fig.update_layout(
        title=(
            f"{_t(lang, 'sweep_title', label=label)}<br>"
            f"<sup>{_t(lang, 'sweep_subtitle')}</sup>"
        ),
        yaxis_title=_t(lang, "owner_advantage"),
        **_BASE_LAYOUT,
    )
    _euro_axis(fig, lang)
    return fig


# ── Scenarios tab ─────────────────────────────────────────────────────────────

def fig_scenarios(scenarios: list, lang: str = "en") -> go.Figure:
    colors = px.colors.qualitative.Set2
    fig = go.Figure()
    for i, sc in enumerate(scenarios):
        sim = sc["sim"]
        name = sc["name"]
        c = colors[i % len(colors)]
        owner_lbl = _t(lang, "scenario_owner", name=name)
        renter_lbl = _t(lang, "scenario_renter", name=name)
        fig.add_trace(go.Scatter(
            x=sim["years"], y=sim["owner_net_worth"],
            name=owner_lbl, line=dict(color=c, width=2.5),
            hovertemplate=f"{owner_lbl}: €%{{y:,.0f}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=sim["years"], y=sim["renter_net_worth"],
            name=renter_lbl, line=dict(color=c, width=2, dash="dash"),
            hovertemplate=f"{renter_lbl}: €%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(title=_t(lang, "scenarios"), **_BASE_LAYOUT)
    _euro_axis(fig, lang)
    return fig
