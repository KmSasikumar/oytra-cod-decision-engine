# Oytra COD Decision Engine — Take-Home Assignment

A system that looks at every Cash on Delivery order before it is shipped
and decides: **Ship as-is / Ship after confirmation / Nudge to prepaid /
Hold-cancel**. Built for a D2C haircare brand where ~28% of COD orders
come back as RTO (Return to Origin).

## Run it in under 10 minutes

No dependencies beyond Python 3.10+ (standard library only). No keys,
no network, no setup:

```bash
python3 cod_engine.py --demo            # three example decisions, with reasons
python3 whatsapp_sim.py --demo          # all six WhatsApp flows, scripted
python3 whatsapp_sim.py --interactive   # type the customer's replies yourself
python3 analysis.py                     # recompute every number in the memo
python3 dashboard.py --date 2026-09-30 --days 30   # founder dashboard (HTML)
```

`dashboard.py` with no `--days` flag reports a single day (the morning
view from the brief); the shipped `dashboard.html` is the September 2026
example (30 days, 334 orders). Try a single order:

```bash
python3 cod_engine.py --order '{"customer_name": "Priya", "address": "45, Lake View Apartments, HSR Layout", "city": "Bengaluru", "state": "Karnataka", "order_value": 649, "customer_prior_orders": 2, "customer_prior_rto": 0}'
```

Decide a whole file: `python3 cod_engine.py --csv data/orders_sample.csv --out decisions.csv`

## How decisions are made

A transparent points score (weights in `config.json`, editable without
touching code). Every decision carries plain-English reasons an
operations person can read:

| Signal | Points | Why (from the data file) |
|---|---|---|
| 2+ past RTOs | +45 | 76.5% of these orders became RTO again |
| 1 past RTO | +20 | 33.6% became RTO again |
| First-time buyer | +12 | 30.3% RTO, and 75% of all orders |
| Repeat buyer, clean history | −10 | 13.8% RTO — the safest group |
| Address under 20 characters | +25 | 62.0% RTO |
| Address with no house number | +15 | 40.4% RTO |
| Fake/test name | +30 | 62.5% RTO |
| High-risk state (Bihar, UP, MP) | +10 | 38–53% RTO in Apr–Aug |
| Order value Rs 500–700 | +5 | 36.8% RTO, the riskiest value band |

Thresholds (also in `config.json`): ≥70 Hold/cancel, 45–69 Nudge to
prepaid, 25–44 Ship after confirmation, below 25 Ship as-is.

**One protection is hard-coded, not just scored:** a genuine first-time
buyer is never auto-cancelled — first orders are capped at "Nudge to
prepaid". Cancelling a first order wastes the Rs 300+ spent acquiring
that customer. Fake/test names are exempt from this protection: they
are not real customers.

**Where an LLM helps vs where code does better** (see `config.json` and
`llm_address_check` in `cod_engine.py`): language judgement — whether
an address is complete and real, spotting novel fake names, reading
Hinglish addresses — is LLM work. Everything numeric and checkable
(counts, thresholds, discount maths, the decision itself) stays in
deterministic code so it is exact, repeatable and auditable. This
submission ships the deterministic checker plus the documented LLM hook;
no live model call is wired in and none is claimed.

## WhatsApp flows

`whatsapp_sim.py` mocks both flows. Messages go out in Hinglish (Roman
script) with a short English line — the order data shows customers
themselves write addresses in Hinglish, so confirmation in the
customer's own register is the one most likely to be answered. Replies:
YES ships (or sends the mock prepaid link), NO cancels (or, for a
declined discount, falls back to confirmation so the sale is not thrown
away), an unclear reply gets one clarifying re-ask and then a manual
hold, and no reply gets a reminder at 12h and a hold at 24h — never
shipped unconfirmed. Discount: 5% off capped at Rs 40 — the maths is in
`config.json` (expected RTO saving per converted order is ~Rs 41.33, so
the discount must stay under that; an uncapped 5% would cost Rs 150 on
a Rs 2,999 order and lose money).

## What the backtest actually showed (September 2026, out-of-time)

Rules trained on April–August, tested on September's 334 orders (the
backtest is in `analysis.py`, every number reproducible):

| Bucket | Orders | Actual RTO rate |
|---|---|---|
| Ship as-is | 253 | 21.7% |
| Ship after confirmation | 68 | 32.4% |
| Nudge to prepaid | 10 | 70.0% |
| Hold / cancel | 3 | 100.0% |

The score ranks risk correctly (rates rise bucket by bucket), but most
RTOs still look ordinary on paper — the honest headline is a modest,
measurable saving, not elimination: holds saved Rs 508.20 with Rs 0
lost margin, and nudges add Rs 385.42 net at a 50% conversion scenario,
for a **net of Rs 893.62 on September**. No rupee saving is claimed for
confirmations: the file cannot show who would reply on WhatsApp, so
that bucket's value (screening out unreachable customers) is reported
as unquantified until reply rates are logged. See the memo for the full
reasoning, including why pincode blocking was rejected and what would
be built next.

## Files

- `cod_engine.py` — decision engine + CLI
- `config.json` — every weight, threshold, cost and message rule
- `whatsapp_sim.py` — WhatsApp confirmation + nudge flows (mock)
- `dashboard.py` + `dashboard.html` — founder morning dashboard
- `analysis.py` + `analysis.json` — every memo number, recomputed
- `data/orders_sample.csv` — the shared data file, as received
- `memo.pdf` — the business memo to the founder
- `DECISION_LOG.md` — choices, alternatives, why
- `AI_USAGE_LOG.md` — which AI tools were used, and where the AI was wrong
