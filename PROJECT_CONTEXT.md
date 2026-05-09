# Project Context

This app compares buying a home with a mortgage against renting the same functional home and investing the cash-flow difference. Use this note as durable context for future prompts; implementation details may change, but these model choices should remain explicit unless the user asks to change them.

## Core Model

- The owner and renter represent the same person facing two mutually exclusive housing choices.
- The comparison is monetary only: net worth and cash outflows matter; psychological utility does not.
- The model enforces equal total annual cash outflow. Each year, whoever has lower direct housing costs invests the difference in an index fund.
- Owner net worth is home equity plus any financial portfolio.
- Renter net worth is the financial portfolio only.

## Current Assumptions

- The owner lives in the purchased home and does not rent it out after the mortgage ends.
- Initial monthly rent and fixed monthly mortgage payment are separate configurable inputs.
- The mortgage is fixed-rate.
- Rent grows annually with the rent inflation input.
- Owner maintenance/tax costs are proportional to the current home value.
- Maintenance avoids depreciation and keeps the owned home functionally comparable to the rented home; renovation-driven appreciation is excluded.
- Stock market return is constant for simplicity and applies to both renter and owner portfolios when they invest.
- Renter agency cost is included at year 0 as two monthly rent payments.
- Other renter moving or renewal costs are omitted by assuming the renter stays in the same home.
- Any extra assumption added to the owner side should also be mirrored for the renter side, and vice versa, unless the purpose is explicitly to test an asymmetric scenario.

## Product Notes

- The app supports English and Italian copy, so user-facing model explanations should be updated in both languages.
- The "How the model works" section should describe formulas and mechanics.
- The "Model assumptions" section should describe hypotheses, simplifications, and interpretive boundaries.
