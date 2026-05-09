"""
Streamlit entry point for the Rent vs Buy calculator.
"""

import numpy as np
import pandas as pd
import streamlit as st
from dataclasses import replace

from simulation import Params, simulate, sweep, find_breakeven
from charts import (
    fig_net_worth, fig_cash_flows, fig_contributions, fig_decomposition,
    fig_sweep, fig_scenarios,
    PARAM_LABELS, PERCENT_PARAMS,
)

# ── Translations ───────────────────────────────────────────────────────────────
STRINGS = {
    "en": {
        # Page
        "page_title": "Rent vs Buy",
        "app_title": "🏠 Rent vs Buy Calculator",
        "app_subtitle": (
            "Equal annual cash outflow: whoever pays less in a given year invests the difference. "
            "Adjust parameters on the left — all charts update instantly."
        ),
        # Assumptions box
        "assumptions_header": "ℹ️ How the model works",
        "assumptions_body": """\
### Core rule — equal annual cash outflow

Each year the model calculates the spending gap:

> `diff(t) = owner_cashflow(t) − renter_cashflow(t)`

* **diff > 0** → owner spends more → **renter invests** `diff(t)` in an index fund that year
* **diff < 0** → renter spends more → **owner invests** `|diff(t)|` in an index fund that year

Both parties always face the same total annual outflow. Nobody gets "free money".

> ⚠️ **Sign convention**: `cashflow(t)` is always **negative** — it represents money *leaving* your pocket (an outflow). Throughout the formulas below it is written as a positive number for readability; mentally prepend a minus sign if you prefer strict financial notation.

---

### 🏠 Owner

**Phase 1 — Year 0 (upfront costs)**

The owner pays the down payment plus one-time transaction costs (notary, stamp duty, agency fees). Transaction costs are a sunk expense — they buy no asset and create no equity.

```
cashflow(0) = down_payment + transaction_cost

NW(0) = down_payment
      = home_price × down_payment_pct
```

*(NW(0) < cashflow(0) because transaction_cost disappears into fees with no residual value)*

---

**Phase 2 — During the mortgage (1 ≤ t ≤ payoff year)**

The owner pays the fixed mortgage instalment plus annual maintenance/tax on the current home value. Depending on the rent and mortgage inputs, either side may be the one investing the annual difference.

```
cashflow(t) = 12 × monthly_mortgage_payment
            + ownership_cost_pct × home_value(t−1)
```

Net worth is the **true equity** — what the owner would receive after selling and repaying the bank, plus any financial portfolio:

```
NW(t) = owner_equity(t) + owner_portfolio(t)

owner_equity(t)       = home_value(t) − mortgage_balance(t)
home_value(t)         = home_price × (1 + appreciation)^t
mortgage_balance(t)   = principal × (1+r_m)^(12t)
                        − monthly_mortgage_payment × [(1+r_m)^(12t) − 1] / r_m
r_m                   = mortgage_rate / 12   (monthly rate)
```

*Check: NW(0) = home_price − principal = down_payment ✓  |  NW(payoff) = home_value(payoff) ✓*

---

**Phase 3 — After the mortgage (t > payoff year)**

No more mortgage instalments. Annual cost drops to maintenance/tax only — far below rent. The owner now invests the large yearly surplus and the portfolio grows fast from zero.

```
cashflow(t) = ownership_cost_pct × home_value(t−1)

NW(t) = home_value(t) + owner_portfolio(t)
```

*(mortgage_balance = 0 from the payoff year onward)*

---

### 🧳 Renter

**Phase 1 — Year 0 (agency cost + upfront investment)**

The renter pays an initial agency cost equal to two monthly rent payments. To preserve equal year-0 cash outflow, the renter invests the difference between the owner's upfront cash outflow and this agency cost.

```
renter_cost(0) = 2 × initial_monthly_rent
renter_invested(0) = max(0, owner_cost(0) − renter_cost(0))
owner_invested(0) = max(0, renter_cost(0) − owner_cost(0))

NW(0) = portfolio(0)
      = renter_invested(0)
```

---

**Phase 2 — During the mortgage (1 ≤ t ≤ owner's payoff year)**

The renter pays rent, which starts from its own configurable value and then grows with rent inflation. When rent is below the owner's total cost the renter invests the difference; when rent is above the owner's cost, the owner invests the difference.

```
cashflow(t) = 12 × initial_monthly_rent × (1 + rent_inflation)^(t−1)

NW(t) = portfolio(t)
      = portfolio(t−1) × (1 + r_eff)
        + max(0, owner_cashflow(t) − renter_cashflow(t))

r_eff = index_return × (1 − capital_gains_tax_rate)
```

---

**Phase 3 — After the mortgage (t > owner's payoff year)**

Rent keeps growing while the owner's cost has usually fallen to maintenance/tax only. If rent is above the owner's cost, the owner invests the surplus; otherwise the renter continues investing the difference.

```
cashflow(t) = 12 × initial_monthly_rent × (1 + rent_inflation)^(t−1)   (same formula)

NW(t) = portfolio(t)
      = portfolio(t−1) × (1 + r_eff)
        + max(0, owner_cashflow(t) − renter_cashflow(t))
```

*(when rent is higher, the owner's portfolio receives the surplus instead)*

---

### What the charts show

| Chart | What to read |
|---|---|
| **Net worth over time** | Owner equity + portfolio vs Renter portfolio only |
| **Annual cash outflows** | `cashflow(t)` for each party; lines cross when rent overtakes owner cost |
| **Investment contributions** | `max(0, diff(t))` for each party each year |
| **Owner decomposition** | Stacked: equity (blue, = home_value − debt, grows as mortgage is repaid + appreciation) + financial investments (green) vs renter portfolio (red) |
""",
        "model_assumptions_header": "📌 Model assumptions",
        "model_assumptions_body": """\
The model intentionally compares the same person living in the same functional home under two choices: buying it or renting it. Any extra assumption added to one side should also apply to the other.

1. **Same person, same housing need.** The owner lives in the home they buy. They do not rent it out after the mortgage is finished unless the renter is also assumed to own another home, which would break the comparison.
2. **Equal cash outflow is the core rule.** Every year, owner and renter are forced to have the same total cash outflow. Whoever has the lower housing cost invests the difference.
3. **Maintenance costs are constant as a percentage.** Owner maintenance/tax costs are applied every year over the full period. This can penalize the owner because real maintenance may be lower early on and higher later.
4. **Rent grows with inflation every year.** This can penalize the renter, especially in markets such as Italy where some contracts can keep rent fixed for several years.
5. **The two simplifications partly offset.** Constant maintenance weighs against the owner; annually increasing rent weighs against the renter. They may cancel only partially.
6. **Stock market returns are constant.** This is a strong simplification. A bad sequence of returns during the mortgage period could hurt the renter materially, but future returns cannot be predicted.
7. **Initial rent and fixed mortgage payment are separate inputs.** They can be equal, but the model no longer forces them to be equal.
8. **The mortgage has a fixed interest rate.** This is typical enough for the comparison and keeps the amortization deterministic.
9. **Renter agency costs are included at the start.** They are modelled as two monthly rent payments in year 0. Other moving or contract-renewal costs are omitted by assuming the renter stays in the same home.
10. **Owner maintenance is proportional to current home value.** This reflects the idea that labor and materials rise with the same broad forces that lift property values.
11. **Maintenance prevents depreciation; it is not renovation.** It keeps the owner home functionally comparable to the rented home. Renovation-driven appreciation is excluded.
12. **No psychological utility is modelled.** Stability, pride of ownership, fear of eviction, flexibility, and other non-monetary preferences are intentionally outside the model.
""",
        # Sidebar
        "sidebar_header": "Parameters",
        "expander_property": "Property & Mortgage",
        "expander_market": "Market Assumptions",
        "expander_advanced": "Advanced",
        # Parameter labels & help
        "home_price": "Home price",
        "help_home_price": "Total purchase price of the property.",
        "down_payment": "Down payment",
        "help_down_payment": (
            "Percentage of the home price paid upfront. "
            "The renter invests this same amount at year 0."
        ),
        "transaction_cost": "Transaction cost (one-time)",
        "help_transaction_cost": (
            "One-time buying costs: notary, stamp duty, agency fees. "
            "The renter invests this amount too."
        ),
        "mortgage_rate": "Mortgage rate",
        "help_mortgage_rate": "Annual nominal interest rate on the mortgage loan.",
        "monthly_mortgage_payment": "Monthly mortgage payment",
        "help_monthly_mortgage_payment": "Fixed monthly mortgage instalment paid by the owner.",
        "initial_monthly_rent": "Initial monthly rent",
        "help_initial_monthly_rent": (
            "Monthly rent in year 1. It grows afterwards with rent inflation and is no longer tied "
            "to the mortgage payment."
        ),
        "home_appreciation": "Home appreciation / year",
        "help_home_appreciation": (
            "Annual nominal growth rate of the property's market value. "
            "Historical European average: ~2–3 %."
        ),
        "rent_inflation": "Rent inflation / year",
        "help_rent_inflation": (
            "Annual growth rate applied to the renter's rent. "
            "Typically tracks general CPI."
        ),
        "index_return": "Index fund return / year",
        "help_index_return": (
            "Expected gross annual return of the index fund the renter (and later the owner) invests in. "
            "Global equity long-run average: ~7–8 % nominal before tax."
        ),
        "ownership_cost": "Annual ownership cost (maintenance + tax)",
        "help_ownership_cost": (
            "Costs borne only by the owner each year: maintenance, property tax, insurance. "
            "Expressed as a percentage of the current home value. Typical range: 1–3 %."
        ),
        "horizon": "Time horizon (years)",
        "help_horizon": "Total number of years to simulate.",
        "toggle_cgt": "Apply capital gains tax on investments",
        "help_cgt": (
            "Models an annual tax drag on investment returns "
            "(e.g. 26 % Italian 'imposta sostitutiva'). "
            "Applies to both renter and owner portfolios."
        ),
        "cgt_rate": "Capital gains tax rate",
        "toggle_real": "Show real (inflation-adjusted) values",
        "help_real": (
            "Deflates all values by CPI so you see purchasing-power-equivalent wealth "
            "rather than nominal euros."
        ),
        "cpi": "CPI (general inflation)",
        "help_cpi": "Annual general inflation used to deflate nominal values to real values.",
        # Metrics
        "metric_mort_end": "Mortgage ends",
        "metric_owner_at_mort": "Owner NW at mortgage end",
        "metric_renter_at_mort": "Renter NW at mortgage end",
        "metric_owner_final": "Owner net worth (yr {h})",
        "metric_renter_final": "Renter net worth (yr {h})",
        "metric_gap": "Lead at year {h}",
        "wins": "{w} wins",
        # Tabs
        "tab_analysis": "📊 Analysis",
        "tab_sensitivity": "🎛 Sensitivity",
        "tab_scenarios": "📋 Scenarios",
        # Analysis tab
        "milestones_title": "Net worth milestones",
        "col_year": "Year",
        "col_owner": "Owner NW",
        "col_renter": "Renter NW",
        "col_gap": "Gap",
        "col_leader": "Leader",
        "owner_wins": "Owner ✓",
        "renter_wins": "Renter ✓",
        # Sensitivity tab
        "sweep_title": "Parameter sweep — fan chart",
        "sweep_caption": (
            "Pick a parameter: the chart shows owner advantage (owner NW − renter NW) "
            "for 10 evenly-spaced values across its range. "
            "Positive = owner ahead; negative = renter ahead."
        ),
        "sweep_select": "Parameter to sweep",
        "breakeven_title": "Break-even thresholds",
        "breakeven_caption": "At what value does the outcome flip? Computed at year {h}.",
        "be_col_param": "Parameter",
        "be_col_val": "Break-even value",
        "be_col_interp": "Interpretation",
        "be_owner_wins_all": "Owner wins across entire tested range",
        "be_renter_wins_all": "Renter wins across entire tested range",
        "be_no_eval": "Could not evaluate (parameter range invalid)",
        "be_direction": "{w_lo} wins below {val} → {w_hi} wins above",
        "be_owner": "Owner",
        "be_renter": "Renter",
        # Scenarios tab
        "scenarios_title": "Scenario comparison",
        "scenarios_caption": "Save up to 4 parameter sets and overlay them on one chart.",
        "scenario_placeholder": "Enter scenario name…",
        "btn_save": "💾 Save current",
        "btn_clear": "🗑 Clear all",
        "max_scenarios_warn": "4 scenarios saved — clear some to add more.",
        "no_scenarios": "No scenarios saved yet. Adjust the parameters and click **Save current**.",
        "comp_title": "Comparison at year {h}",
        "param_details": "Parameter details",
        # Param labels for sensitivity selects
        "param_labels": {
            "home_price": "Home price",
            "down_payment_pct": "Down payment",
            "transaction_cost_pct": "Transaction cost",
            "mortgage_rate": "Mortgage rate",
            "monthly_mortgage_payment": "Mortgage payment",
            "initial_monthly_rent": "Initial rent",
            "annual_ownership_cost_pct": "Ownership cost",
            "home_appreciation": "Home appreciation",
            "rent_inflation": "Rent inflation",
            "index_return": "Index return",
        },
    },
    "it": {
        "page_title": "Affitto vs Acquisto",
        "app_title": "🏠 Calcolatore Affitto vs Acquisto",
        "app_subtitle": (
            "Stessa uscita annuale: chi spende meno investe la differenza. "
            "Modifica i parametri a sinistra — i grafici si aggiornano istantaneamente."
        ),
        "assumptions_header": "ℹ️ Come funziona il modello",
        "assumptions_body": """\
### Regola base — stessa uscita annuale

Ogni anno il modello calcola il differenziale di spesa:

> `diff(t) = cashflow_proprietario(t) − cashflow_affittuario(t)`

* **diff > 0** → il proprietario spende di più → **l'affittuario investe** `diff(t)` in un fondo indice
* **diff < 0** → l'affittuario spende di più → **il proprietario investe** `|diff(t)|` in un fondo indice

Entrambi affrontano sempre la stessa uscita totale annua. Nessuno riceve denaro gratis.

> ⚠️ **Convenzione di segno**: `cashflow(t)` è sempre **negativo** — rappresenta denaro che *esce* dal portafoglio (un'uscita). Nelle formule sottostanti è scritto come numero positivo per leggibilità; in notazione finanziaria rigorosa va preceduto da un segno meno.

---

### 🏠 Proprietario

**Fase 1 — Anno 0 (costi iniziali)**

Il proprietario paga l'anticipo più i costi una tantum di acquisto (notaio, imposte, agenzia). I costi di acquisto sono una spesa senza valore residuo — non generano equity.

```
cashflow(0) = anticipo + costi_acquisto

NW(0) = anticipo
      = prezzo_immobile × percentuale_anticipo
```

*(NW(0) < cashflow(0) perché i costi_acquisto evaporano in spese senza controvalore patrimoniale)*

---

**Fase 2 — Durante il mutuo (1 ≤ t ≤ fine mutuo)**

Il proprietario paga la rata fissa del mutuo più i costi annui di manutenzione/tasse sul valore corrente dell'immobile. In base agli input di affitto e mutuo, una delle due parti investirà la differenza annua.

```
cashflow(t) = 12 × rata_mutuo_mensile
            + costo_proprietà% × valore_immobile(t−1)
```

Il patrimonio netto è il **vero equity** — quanto incasserebbe il proprietario vendendo e rimborsando la banca, più l'eventuale portafoglio finanziario:

```
NW(t) = equity_proprietario(t) + portafoglio_proprietario(t)

equity_proprietario(t) = valore_immobile(t) − saldo_mutuo(t)
valore_immobile(t)     = prezzo × (1 + rivalutazione)^t
saldo_mutuo(t)         = capitale × (1+r_m)^(12t)
                         − rata_mutuo_mensile × [(1+r_m)^(12t) − 1] / r_m
r_m                    = tasso_mutuo / 12   (tasso mensile)
```

*Verifica: NW(0) = prezzo − capitale = anticipo ✓  |  NW(fine mutuo) = valore_immobile(fine mutuo) ✓*

---

**Fase 3 — Dopo il mutuo (t > fine mutuo)**

Non ci sono più rate. L'uscita annua scende ai soli costi di proprietà — molto meno dell'affitto. Il proprietario investe ora il grande surplus e il portafoglio cresce rapidamente partendo da zero.

```
cashflow(t) = costo_proprietà% × valore_immobile(t−1)

NW(t) = valore_immobile(t) + portafoglio_proprietario(t)
```

*(saldo_mutuo = 0 dal momento del saldo finale in poi)*

---

### 🧳 Affittuario

**Fase 1 — Anno 0 (costo agenzia + investimento iniziale)**

L'affittuario paga un costo iniziale di agenzia pari a due mensilità di affitto. Per mantenere la stessa uscita di cassa all'anno 0, investe la differenza tra l'esborso iniziale del proprietario e questo costo di agenzia.

```
costo_affittuario(0) = 2 × affitto_mensile_iniziale
investito_affittuario(0) = max(0, costo_proprietario(0) − costo_affittuario(0))
investito_proprietario(0) = max(0, costo_affittuario(0) − costo_proprietario(0))

NW(0) = portafoglio(0)
      = investito_affittuario(0)
```

---

**Fase 2 — Durante il mutuo (1 ≤ t ≤ fine mutuo del proprietario)**

L'affittuario paga l'affitto, che parte da un valore configurabile separato e poi cresce con l'inflazione. Quando l'affitto è inferiore al costo del proprietario, l'affittuario investe la differenza; quando è superiore, il proprietario investe la differenza.

```
cashflow(t) = 12 × affitto_mensile_iniziale × (1 + inflazione_affitto)^(t−1)

NW(t) = portafoglio(t)
      = portafoglio(t−1) × (1 + r_netto)
        + max(0, cashflow_proprietario(t) − cashflow_affittuario(t))

r_netto = rendimento_fondo × (1 − aliquota_plusvalenze)
```

---

**Fase 3 — Dopo il mutuo (t > fine mutuo del proprietario)**

L'affitto continua a crescere mentre il costo del proprietario di solito scende ai soli costi di manutenzione/tasse. Se l'affitto supera il costo del proprietario, il proprietario investe il surplus; altrimenti l'affittuario continua a investire la differenza.

```
cashflow(t) = 12 × affitto_mensile_iniziale × (1 + inflazione_affitto)^(t−1)   (stessa formula)

NW(t) = portafoglio(t)
      = portafoglio(t−1) × (1 + r_netto)
        + max(0, cashflow_proprietario(t) − cashflow_affittuario(t))
```

*(quando l'affitto è più alto, il surplus va invece nel portafoglio del proprietario)*

---

### Cosa mostrano i grafici

| Grafico | Come leggerlo |
|---|---|
| **Patrimonio nel tempo** | `NW(t)` per entrambi: equity + portafoglio (propr.) vs solo portafoglio (affitt.) |
| **Uscite annuali** | `cashflow(t)` per entrambi; le linee si incrociano quando l'affitto supera il costo del proprietario |
| **Contributi all'investimento** | `max(0, diff(t))` per ciascuna parte ogni anno |
| **Composizione patrimonio** | Stratificato: equity (blu, = valore − debito, cresce con rimborso mutuo + rivalutazione) + investimenti (verde) vs portafoglio affittuario (rosso) |
""",
        "model_assumptions_header": "📌 Ipotesi del modello",
        "model_assumptions_body": """\
Il modello confronta intenzionalmente la stessa persona che vive nella stessa casa funzionale sotto due scelte: acquistare o affittare. Qualsiasi ipotesi extra aggiunta a una parte dovrebbe valere anche per l'altra.

1. **Stessa persona, stessa esigenza abitativa.** Il proprietario vive nella casa che compra. Non la mette a reddito dopo la fine del mutuo, a meno di assumere che anche l'affittuario possieda un'altra casa, cosa che romperebbe il confronto.
2. **La stessa uscita di cassa è la regola centrale.** Ogni anno proprietario e affittuario hanno la stessa uscita totale. Chi sostiene il costo abitativo più basso investe la differenza.
3. **I costi di manutenzione sono costanti in percentuale.** I costi annui del proprietario sono applicati per tutto il periodo. Questo può penalizzare il proprietario, perché nella realtà la manutenzione può essere più bassa all'inizio e più alta alla fine.
4. **L'affitto cresce ogni anno con l'inflazione.** Questo può penalizzare l'affittuario, soprattutto in mercati come l'Italia dove alcuni contratti possono mantenere il canone fisso per diversi anni.
5. **Le due semplificazioni si compensano in parte.** La manutenzione costante pesa sul proprietario; l'affitto che cresce ogni anno pesa sull'affittuario. La compensazione può essere solo parziale.
6. **Il rendimento azionario è costante.** È una forte semplificazione. Una sequenza negativa di rendimenti durante il mutuo potrebbe danneggiare molto l'affittuario, ma i rendimenti futuri non sono prevedibili.
7. **Affitto iniziale e rata fissa del mutuo sono input separati.** Possono essere uguali, ma il modello non li forza più a coincidere.
8. **Il mutuo è a tasso fisso.** È un'ipotesi tipica e mantiene deterministica l'ammortizzazione.
9. **I costi di agenzia dell'affittuario sono inclusi all'inizio.** Sono modellati come due mensilità all'anno 0. Altri costi di trasloco o rinnovo sono omessi assumendo che l'affittuario resti nella stessa casa.
10. **La manutenzione del proprietario è proporzionale al valore corrente della casa.** Questo riflette l'idea che manodopera e materiali crescano con forze simili a quelle che rivalutano gli immobili.
11. **La manutenzione evita il deprezzamento; non è ristrutturazione.** Mantiene la casa del proprietario funzionalmente comparabile alla casa in affitto. La rivalutazione da ristrutturazione è esclusa.
12. **Nessuna utilità psicologica è modellata.** Stabilità, orgoglio di possesso, paura dello sfratto, flessibilità e altre preferenze non monetarie restano fuori dal modello.
""",
        "sidebar_header": "Parametri",
        "expander_property": "Immobile & Mutuo",
        "expander_market": "Ipotesi di Mercato",
        "expander_advanced": "Avanzate",
        "home_price": "Prezzo dell'immobile",
        "help_home_price": "Prezzo totale di acquisto dell'immobile.",
        "down_payment": "Anticipo",
        "help_down_payment": (
            "Percentuale del prezzo versata subito. "
            "L'affittuario investe questa stessa cifra all'anno 0."
        ),
        "transaction_cost": "Costi di acquisto (una tantum)",
        "help_transaction_cost": (
            "Costi una tantum: notaio, imposte di registro, agenzia. "
            "Anche questi vengono investiti dall'affittuario."
        ),
        "mortgage_rate": "Tasso del mutuo",
        "help_mortgage_rate": "Tasso d'interesse annuo nominale del mutuo.",
        "monthly_mortgage_payment": "Rata mensile mutuo",
        "help_monthly_mortgage_payment": "Rata mensile fissa del mutuo pagata dal proprietario.",
        "initial_monthly_rent": "Affitto mensile iniziale",
        "help_initial_monthly_rent": (
            "Affitto mensile del primo anno. Poi cresce con l'inflazione dell'affitto e non è più "
            "legato alla rata del mutuo."
        ),
        "home_appreciation": "Rivalutazione immobile / anno",
        "help_home_appreciation": (
            "Tasso di crescita annuo nominale del valore dell'immobile. "
            "Media storica europea: circa 2–3 %."
        ),
        "rent_inflation": "Inflazione affitto / anno",
        "help_rent_inflation": (
            "Tasso di crescita annuo dell'affitto pagato dall'inquilino. "
            "Di solito segue l'inflazione generale (IPC)."
        ),
        "index_return": "Rendimento fondo indice / anno",
        "help_index_return": (
            "Rendimento annuo lordo atteso del fondo indice in cui investono affittuario e, poi, proprietario. "
            "Media storica azionario globale: circa 7–8 % nominale lordo."
        ),
        "ownership_cost": "Costo annuo proprietà (manutenzione + tasse)",
        "help_ownership_cost": (
            "Costi annui a carico del solo proprietario: manutenzione, IMU, assicurazione. "
            "In percentuale del valore corrente dell'immobile. Intervallo tipico: 1–3 %."
        ),
        "horizon": "Orizzonte temporale (anni)",
        "help_horizon": "Numero totale di anni da simulare.",
        "toggle_cgt": "Applica tassazione plusvalenze sugli investimenti",
        "help_cgt": (
            "Modella un'imposta annua sul rendimento degli investimenti "
            "(es. 26 % imposta sostitutiva italiana). "
            "Si applica ai portafogli sia dell'affittuario che del proprietario."
        ),
        "cgt_rate": "Aliquota imposta sostitutiva",
        "toggle_real": "Mostra valori reali (corretti per inflazione)",
        "help_real": (
            "Deflaziona tutti i valori con l'IPC per mostrare la ricchezza "
            "in termini di potere d'acquisto anziché in euro nominali."
        ),
        "cpi": "IPC (inflazione generale)",
        "help_cpi": "Tasso di inflazione generale annuo usato per deflazionare i valori nominali.",
        "metric_mort_end": "Fine mutuo",
        "metric_owner_at_mort": "Patrimonio propr. a fine mutuo",
        "metric_renter_at_mort": "Patrimonio affitt. a fine mutuo",
        "metric_owner_final": "Patrimonio proprietario (anno {h})",
        "metric_renter_final": "Patrimonio affittuario (anno {h})",
        "metric_gap": "Vantaggio all'anno {h}",
        "wins": "{w} vince",
        "tab_analysis": "📊 Analisi",
        "tab_sensitivity": "🎛 Sensibilità",
        "tab_scenarios": "📋 Scenari",
        "milestones_title": "Tappe del patrimonio",
        "col_year": "Anno",
        "col_owner": "NW Proprietario",
        "col_renter": "NW Affittuario",
        "col_gap": "Differenza",
        "col_leader": "Chi vince",
        "owner_wins": "Proprietario ✓",
        "renter_wins": "Affittuario ✓",
        "sweep_title": "Analisi di sensibilità — grafico a ventaglio",
        "sweep_caption": (
            "Scegli un parametro: il grafico mostra il vantaggio del proprietario "
            "(NW propr. − NW affitt.) per 10 valori equidistanti. "
            "Positivo = proprietario avanti; negativo = affittuario avanti."
        ),
        "sweep_select": "Parametro da variare",
        "breakeven_title": "Soglie di indifferenza",
        "breakeven_caption": "A che valore si ribalta l'esito? Calcolato all'anno {h}.",
        "be_col_param": "Parametro",
        "be_col_val": "Soglia di indifferenza",
        "be_col_interp": "Interpretazione",
        "be_owner_wins_all": "Proprietario vince sull'intero intervallo testato",
        "be_renter_wins_all": "Affittuario vince sull'intero intervallo testato",
        "be_no_eval": "Impossibile valutare (intervallo parametro non valido)",
        "be_direction": "{w_lo} vince sotto {val} → {w_hi} vince sopra",
        "be_owner": "Proprietario",
        "be_renter": "Affittuario",
        "scenarios_title": "Confronto scenari",
        "scenarios_caption": "Salva fino a 4 configurazioni e sovrapponile in un unico grafico.",
        "scenario_placeholder": "Inserisci nome scenario…",
        "btn_save": "💾 Salva corrente",
        "btn_clear": "🗑 Cancella tutto",
        "max_scenarios_warn": "4 scenari salvati — cancellane alcuni per aggiungerne altri.",
        "no_scenarios": "Nessuno scenario salvato. Modifica i parametri e clicca su **Salva corrente**.",
        "comp_title": "Confronto all'anno {h}",
        "param_details": "Dettagli parametri",
        "param_labels": {
            "home_price": "Prezzo immobile",
            "down_payment_pct": "Anticipo",
            "transaction_cost_pct": "Costi acquisto",
            "mortgage_rate": "Tasso mutuo",
            "monthly_mortgage_payment": "Rata mutuo",
            "initial_monthly_rent": "Affitto iniziale",
            "annual_ownership_cost_pct": "Costo proprietà",
            "home_appreciation": "Rivalutazione immobile",
            "rent_inflation": "Inflazione affitto",
            "index_return": "Rendimento fondo",
        },
    },
}

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Rent vs Buy", page_icon="🏠", layout="wide")

# ── Language toggle (top of sidebar) ──────────────────────────────────────────
with st.sidebar:
    italiano = st.toggle("🇮🇹 Italiano", value=False)

lang = "it" if italiano else "en"
s = STRINGS[lang]

st.title(s["app_title"])
st.caption(s["app_subtitle"])

# ── Model assumptions (always visible, collapsed by default) ─────────────────
with st.expander(s["assumptions_header"], expanded=False):
    st.markdown(s["assumptions_body"])

with st.expander(s["model_assumptions_header"], expanded=False):
    st.markdown(s["model_assumptions_body"])

# ── Sidebar parameters ────────────────────────────────────────────────────────
with st.sidebar:
    st.header(s["sidebar_header"])

    with st.expander(s["expander_property"], expanded=True):
        home_price = st.slider(
            s["home_price"], 50_000, 1_000_000, 150_000, step=5_000,
            format="€%d", help=s["help_home_price"],
        )
        down_pct_ui = st.slider(
            s["down_payment"], 5.0, 40.0, 20.0, step=1.0, format="%.0f%%",
            help=s["help_down_payment"],
        )
        tx_cost_ui = st.slider(
            s["transaction_cost"], 0.0, 10.0, 5.0, step=0.5, format="%.1f%%",
            help=s["help_transaction_cost"],
        )
        mortgage_rate_ui = st.slider(
            s["mortgage_rate"], 0.5, 12.0, 3.0, step=0.25, format="%.2f%%",
            help=s["help_mortgage_rate"],
        )
        monthly_mortgage_payment = st.slider(
            s["monthly_mortgage_payment"], 200, 5_000, 650, step=50, format="€%d",
            help=s["help_monthly_mortgage_payment"],
        )
        initial_monthly_rent = st.slider(
            s["initial_monthly_rent"], 200, 5_000, 650, step=50, format="€%d",
            help=s["help_initial_monthly_rent"],
        )

    with st.expander(s["expander_market"], expanded=True):
        home_appr_ui = st.slider(
            s["home_appreciation"], 0.0, 10.0, 2.0, step=0.5, format="%.1f%%",
            help=s["help_home_appreciation"],
        )
        rent_infl_ui = st.slider(
            s["rent_inflation"], 0.0, 8.0, 2.0, step=0.5, format="%.1f%%",
            help=s["help_rent_inflation"],
        )
        index_ret_ui = st.slider(
            s["index_return"], 1.0, 15.0, 5.0, step=0.5, format="%.1f%%",
            help=s["help_index_return"],
        )
        own_cost_ui = st.slider(
            s["ownership_cost"], 0.5, 5.0, 2.0, step=0.25, format="%.2f%%",
            help=s["help_ownership_cost"],
        )
        horizon_years = st.slider(
            s["horizon"], 10, 50, 50, step=1,
            help=s["help_horizon"],
        )

    with st.expander(s["expander_advanced"], expanded=False):
        use_cgt = st.toggle(s["toggle_cgt"], value=False, help=s["help_cgt"])
        cgt_rate_ui = 0.0
        if use_cgt:
            cgt_rate_ui = st.slider(s["cgt_rate"], 0.0, 50.0, 26.0, step=1.0, format="%.0f%%")

        show_real = st.toggle(s["toggle_real"], value=False, help=s["help_real"])
        cpi_ui = 2.0
        if show_real:
            cpi_ui = st.slider(s["cpi"], 0.0, 6.0, 2.0, step=0.5, format="%.1f%%",
                               help=s["help_cpi"])

# ── Build Params (convert % sliders from 0–100 to 0–1) ───────────────────────
params = Params(
    home_price=float(home_price),
    down_payment_pct=down_pct_ui / 100,
    transaction_cost_pct=tx_cost_ui / 100,
    mortgage_rate=mortgage_rate_ui / 100,
    monthly_mortgage_payment=float(monthly_mortgage_payment),
    initial_monthly_rent=float(initial_monthly_rent),
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

# ── Top-line metrics ──────────────────────────────────────────────────────────
mort = sim["mortgage_years"]
owner_final = sim["owner_net_worth"][horizon_years]
renter_final = sim["renter_net_worth"][horizon_years]
gap = owner_final - renter_final
winner_word = s["be_owner"] if gap > 0 else s["be_renter"]

# Row 1: at mortgage end (only if mortgage completes within the simulation horizon)
mort_within_horizon = mort <= horizon_years
mort_label = (f"Year {mort}" if lang == "en" else f"Anno {mort}")
if not mort_within_horizon:
    mort_label += " ⚠️" if lang == "en" else " ⚠️"

m1, m2, m3 = st.columns(3)
m1.metric(s["metric_mort_end"], mort_label)
if mort_within_horizon:
    owner_at_mort = sim["owner_net_worth"][mort]
    renter_at_mort = sim["renter_net_worth"][mort]
    m2.metric(s["metric_owner_at_mort"], f"€{owner_at_mort:,.0f}")
    m3.metric(s["metric_renter_at_mort"], f"€{renter_at_mort:,.0f}")
else:
    beyond = "beyond horizon" if lang == "en" else "oltre orizzonte"
    m2.metric(s["metric_owner_at_mort"], "—", help=beyond)
    m3.metric(s["metric_renter_at_mort"], "—", help=beyond)

# Row 2: at horizon
m4, m5, m6 = st.columns(3)
m4.metric(s["metric_owner_final"].format(h=horizon_years), f"€{owner_final:,.0f}")
m5.metric(s["metric_renter_final"].format(h=horizon_years), f"€{renter_final:,.0f}")
m6.metric(
    s["metric_gap"].format(h=horizon_years),
    f"€{abs(gap):,.0f}",
    delta=s["wins"].format(w=winner_word),
    delta_color="off",
)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_analysis, tab_sensitivity, tab_scenarios = st.tabs([
    s["tab_analysis"], s["tab_sensitivity"], s["tab_scenarios"],
])

# ─────────────────────────────────────────────────────────────────────────────
# Tab 1: Analysis
# ─────────────────────────────────────────────────────────────────────────────
with tab_analysis:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            fig_net_worth(sim, real=show_real, cpi=params.cpi, lang=lang),
            width="stretch",
        )
        st.plotly_chart(fig_contributions(sim, lang=lang), width="stretch")
    with c2:
        st.plotly_chart(fig_cash_flows(sim, lang=lang), width="stretch")
        st.plotly_chart(
            fig_decomposition(sim, real=show_real, cpi=params.cpi, lang=lang),
            width="stretch",
        )

    st.subheader(s["milestones_title"])
    milestones = [y for y in [mort, 10, 15, 20, 25, 30, 35, 40, 50]
                  if y <= horizon_years and y > 0]
    milestones = sorted(set(milestones))
    rows = []
    for y in milestones:
        o = sim["owner_net_worth"][y]
        r = sim["renter_net_worth"][y]
        g = o - r
        label = f"★ {y}" if y == mort else str(y)  # highlight mortgage-end year
        rows.append({
            s["col_year"]: label,
            s["col_owner"]: f"€{o:,.0f}",
            s["col_renter"]: f"€{r:,.0f}",
            s["col_gap"]: f"€{g:+,.0f}",
            s["col_leader"]: s["owner_wins"] if g > 0 else s["renter_wins"],
        })
    st.table(rows)

# ─────────────────────────────────────────────────────────────────────────────
# Tab 2: Sensitivity
# ─────────────────────────────────────────────────────────────────────────────
with tab_sensitivity:
    st.subheader(s["sweep_title"])
    st.caption(s["sweep_caption"])

    # Dynamically cap mortgage_rate and home_price sweep to avoid invalid combos.
    # Constraint: monthly_mortgage_payment > (home_price*(1-dp)) * rate/12
    mortgage_principal = params.home_price * (1 - params.down_payment_pct)
    min_valid_mortgage_payment = (mortgage_principal * (params.mortgage_rate / 12)) * 1.03
    max_valid_rate = (params.monthly_mortgage_payment / mortgage_principal * 12) * 0.97
    max_valid_price = (
        params.monthly_mortgage_payment / (params.mortgage_rate / 12)
    ) / (1 - params.down_payment_pct) * 0.97

    SWEEP_PARAMS = {
        "home_appreciation": (0.0, 0.08),
        "index_return": (0.01, 0.12),
        "rent_inflation": (0.0, 0.08),
        "initial_monthly_rent": (200, 3_000),
        "monthly_mortgage_payment": (max(200, min_valid_mortgage_payment), 3_000),
        "mortgage_rate": (0.005, min(0.10, max_valid_rate)),
        "home_price": (50_000, min(600_000, max_valid_price)),
        "down_payment_pct": (0.05, 0.40),
    }

    param_label_map = s["param_labels"]

    sweep_param = st.selectbox(
        s["sweep_select"],
        options=list(SWEEP_PARAMS.keys()),
        format_func=lambda k: param_label_map.get(k, PARAM_LABELS.get(k, k)),
    )

    lo_sw, hi_sw = SWEEP_PARAMS[sweep_param]
    sweep_values = np.linspace(lo_sw, hi_sw, 10)
    sweep_sims = sweep(params, sweep_param, sweep_values)
    plabel = param_label_map.get(sweep_param, PARAM_LABELS.get(sweep_param, sweep_param))
    st.plotly_chart(
        fig_sweep(sweep_sims, sweep_param, sweep_values, param_label=plabel, lang=lang),
        width="stretch",
    )

    st.divider()
    st.subheader(s["breakeven_title"])
    st.caption(s["breakeven_caption"].format(h=horizon_years))

    # Break-even config: use valid ranges so find_breakeven never hits ValueError
    BREAKEVEN_CONFIGS = [
        ("home_appreciation", 0.0, 0.12),
        ("index_return", 0.0, 0.20),
        ("rent_inflation", 0.0, 0.10),
        ("initial_monthly_rent", 200, 4_000),
        ("monthly_mortgage_payment", max(200, min_valid_mortgage_payment), 4_000),
        ("mortgage_rate", 0.005, min(0.12, max_valid_rate)),
        ("home_price", 50_000, min(700_000, max_valid_price)),
    ]

    with st.spinner("Computing…"):
        be_rows = []
        for param_name, lo_b, hi_b in BREAKEVEN_CONFIGS:
            unit = "%" if param_name in PERCENT_PARAMS else "€"

            def _gap(v, pn=param_name):
                try:
                    p2 = replace(params, **{pn: v})
                    s2 = simulate(p2)
                    return s2["owner_net_worth"][horizon_years] - s2["renter_net_worth"][horizon_years]
                except ValueError:
                    return None

            g_lo = _gap(lo_b)
            g_hi = _gap(hi_b)
            bv = find_breakeven(params, param_name, lo_b, hi_b, horizon_years)

            if bv is None:
                if g_lo is not None and g_lo > 0:
                    direction = s["be_owner_wins_all"]
                elif g_lo is not None and g_lo <= 0:
                    direction = s["be_renter_wins_all"]
                else:
                    direction = s["be_no_eval"]
            else:
                w_lo = s["be_owner"] if (g_lo is not None and g_lo > 0) else s["be_renter"]
                w_hi = s["be_owner"] if (g_hi is not None and g_hi > 0) else s["be_renter"]
                val_str = f"{bv:.2%}" if unit == "%" else f"€{bv:,.0f}"
                direction = s["be_direction"].format(w_lo=w_lo, val=val_str, w_hi=w_hi)

            param_lbl = param_label_map.get(param_name, PARAM_LABELS.get(param_name, param_name))
            val_display = ("—" if bv is None else
                           (f"{bv:.2%}" if unit == "%" else f"€{bv:,.0f}"))
            be_rows.append({
                s["be_col_param"]: param_lbl,
                s["be_col_val"]: val_display,
                s["be_col_interp"]: direction,
            })

    df_be = pd.DataFrame(be_rows)
    st.dataframe(
        df_be,
        width="stretch",
        hide_index=True,
        column_config={
            s["be_col_param"]: st.column_config.TextColumn(width="medium"),
            s["be_col_val"]: st.column_config.TextColumn(width="small"),
            s["be_col_interp"]: st.column_config.TextColumn(width="large"),
        },
    )

# ─────────────────────────────────────────────────────────────────────────────
# Tab 3: Scenarios
# ─────────────────────────────────────────────────────────────────────────────
with tab_scenarios:
    st.subheader(s["scenarios_title"])
    st.caption(s["scenarios_caption"])

    if "scenarios" not in st.session_state:
        st.session_state.scenarios = []

    n_saved = len(st.session_state.scenarios)
    col_name, col_save, col_clear = st.columns([3, 1, 1])
    with col_name:
        scenario_name = st.text_input(
            "name", value=f"Scenario {n_saved + 1}",
            label_visibility="collapsed",
            placeholder=s["scenario_placeholder"],
        )
    with col_save:
        if st.button(s["btn_save"], disabled=n_saved >= 4, width="stretch"):
            st.session_state.scenarios.append({
                "name": scenario_name or f"Scenario {n_saved + 1}",
                "sim": sim,
                "params": params,
            })
            st.rerun()
    with col_clear:
        if st.button(s["btn_clear"], disabled=n_saved == 0, width="stretch"):
            st.session_state.scenarios = []
            st.rerun()

    if n_saved >= 4:
        st.warning(s["max_scenarios_warn"])

    if st.session_state.scenarios:
        st.plotly_chart(
            fig_scenarios(st.session_state.scenarios, lang=lang),
            width="stretch",
        )

        st.subheader(s["comp_title"].format(h=horizon_years))
        comp_rows = []
        for sc in st.session_state.scenarios:
            sc_sim = sc["sim"]
            sc_h = min(horizon_years, sc["params"].horizon_years)
            o = sc_sim["owner_net_worth"][sc_h]
            r = sc_sim["renter_net_worth"][sc_h]
            comp_rows.append({
                "Scenario": sc["name"],
                s["col_owner"]: f"€{o:,.0f}",
                s["col_renter"]: f"€{r:,.0f}",
                s["col_gap"]: f"€{o - r:+,.0f}",
                s["col_leader"]: s["owner_wins"] if o > r else s["renter_wins"],
                ("Mortgage end" if lang == "en" else "Fine mutuo"):
                    f"Yr {sc_sim['mortgage_years']}" if lang == "en"
                    else f"Anno {sc_sim['mortgage_years']}",
            })
        st.table(comp_rows)

        with st.expander(s["param_details"]):
            for sc in st.session_state.scenarios:
                p = sc["params"]
                st.markdown(
                    f"**{sc['name']}**: "
                    f"€{p.home_price:,.0f} | "
                    f"Mutuo €{p.monthly_mortgage_payment:,.0f}/mo | "
                    f"Affitto €{p.initial_monthly_rent:,.0f}/mo | "
                    f"{p.mortgage_rate:.2%} | "
                    f"↑{p.home_appreciation:.2%} | "
                    f"📈{p.index_return:.2%} | "
                    f"🏠{p.rent_inflation:.2%} | "
                    f"CGT {p.capital_gains_tax_rate:.0%}"
                )
    else:
        st.info(s["no_scenarios"])
