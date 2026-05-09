# 🏠 Rent vs Buy Calculator

> **Should you buy a home with a mortgage, or keep renting and invest the difference?**  
> This tool runs the full 50-year simulation so you don't have to guess.

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

---

## What it does

The model enforces a strict **equal cash outflow** rule: both the owner and the renter spend the same total amount every year. Whoever pays less in a given year invests the difference in an index fund. This makes the comparison genuinely fair.

```
diff(t) = owner_cost(t) − rent(t)

diff > 0  →  renter  invests the surplus
diff < 0  →  owner   invests the surplus
```

**Owner net worth** = home equity (appreciating market value minus outstanding mortgage debt) + financial portfolio  
**Renter net worth** = index fund portfolio only

---

## Features

| | |
|---|---|
| 📊 **4 interactive charts** | Net worth, cash flows, investment contributions, wealth decomposition |
| 🎛 **Live parameter sliders** | Every chart updates instantly as you move any slider |
| 🌊 **Fan-chart sensitivity** | Sweep any parameter across its range and see all trajectories at once |
| ⚖️ **Break-even finder** | Automatically computes the threshold at which renting wins |
| 📋 **Scenario comparison** | Save up to 4 named parameter sets and overlay them |
| 🇮🇹 **Italiano / English** | Full UI translation toggle |
| 📐 **Correct equity model** | Owner NW uses home equity (home value − remaining mortgage), not the full home price |
| 💶 **Capital gains tax** | Optional annual tax drag (e.g. 26% Italian *imposta sostitutiva*) |
| 📉 **Real value toggle** | CPI-deflated wealth for inflation-adjusted comparison |

---

## Model assumptions

- **Year 0** — Owner pays down payment + transaction costs. Renter pays agency costs equal to two monthly rent payments and invests the remaining upfront surplus.
- **During mortgage** — Owner pays instalment + maintenance/tax. Rent starts from its own configurable value and grows with rent inflation.
- **After mortgage** — Owner's cost collapses to maintenance/tax only; owner invests the surplus. Renter portfolio compounds without new contributions.
- **Year 0 renter cost** — Renter agency cost is modelled as two monthly rent payments before investing the remaining upfront surplus.

See the **"How the model works"** panel inside the app for the full formulas.

---

## Quick start (local)

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/<your-username>/mortgage-rent.git
cd mortgage-rent
uv sync
uv run streamlit run app.py
```

App opens at **http://localhost:8501**.

### Without uv (plain pip)

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Project structure

```
mortgage-rent/
├── app.py           # Streamlit UI — layout, widgets, tabs
├── simulation.py    # Pure financial model (no UI dependency)
├── charts.py        # Plotly figure builders (pure functions)
└── requirements.txt
```

`simulation.py` has zero UI imports — you can import and call `simulate()` from any Python script or notebook.

---

## Tech stack

- **[Streamlit](https://streamlit.io)** — reactive Python web UI
- **[Plotly](https://plotly.com/python/)** — interactive charts
- **[NumPy](https://numpy.org)** — simulation math
- **[pandas](https://pandas.pydata.org)** — break-even table rendering

---

## Deploy for free on Streamlit Community Cloud

### 1 — Push to GitHub

```bash
git remote add origin https://github.com/<your-username>/mortgage-rent.git
git push -u origin main
```

### 2 — Connect Streamlit Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub
2. Click **"Create app"**
3. Select your repo, branch `main`, main file `app.py`
4. Click **Deploy**

Your app will be live at:

```
https://<your-username>-mortgage-rent-app-<hash>.streamlit.app
```

Streamlit Cloud reads `requirements.txt` automatically — no extra configuration needed.  
Every `git push` to `main` triggers an automatic redeploy.

**Free tier includes**: unlimited public apps · 1 GB RAM · always-on (no sleep)

---

## License

MIT — do whatever you want with it.
