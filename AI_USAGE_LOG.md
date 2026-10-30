# AI usage log

## Which AI tools were used, and for what

- **Muse (the AI agent that built this submission)** — used for
  everything in this package: reading the assignment PDF, analysing
  `orders_sample.csv`, designing the scoring rules, writing all code
  (decision engine, WhatsApp mock, dashboard, analysis, memo
  generator), and writing the memo itself. Every number in the memo was
  computed by `analysis.py` from the data file; the agent did not hand
  -write any data claim.
- **No other AI tool was used.** No external model API was called
  during this build, and no live LLM is wired into the shipped engine
  (see `llm_address_check` in `cod_engine.py` for the documented hook
  and the reason).
- **What the AI did not do:** it did not invent customer names,
  pincodes, outcomes, or conversion rates; it did not submit anything;
  it did not contact Oytra or any customer. Anything that could not be
  computed from the file is labelled as an assumption or as brief-given
  wherever it appears.

## Where the AI was wrong or weak, and how it was caught

1. **The AI's first instinct was to build the pincode blocking the
   Operations lead asked for.** It assumed pincode history would be a
   usable risk signal and nearly designed the engine around it. Caught
   by actually counting: the file has 1,067 distinct pincodes for 2,017
   resolved orders, the busiest pincode has only 12 orders, and none
   has 20 or more. A pincode rule on this data would be guessing, not
   scoring. Fixed by dropping pincode scoring entirely and moving
   geography to the state level, where rates are stable (Bihar 52.3%,
   UP 48.1%, MP 38.3% on Apr–Aug data). Lesson recorded: check the
   support (n) behind a rate before using it.

2. **The AI first counted order outcomes literally and undercounted
   RTOs.** The file spells the same outcome as `RTO`, `Rto`, `RTO `
   (trailing space) and `delivered`. A literal count gave 570 RTOs;
   normalising case and whitespace gives 573, plus one genuinely
   unresolved `IN_TRANSIT` row. Caught by listing the distinct raw
   status values before computing any rate. Fixed with
   `normalize_status` in `cod_engine.py`, applied before every count,
   and the unresolved row is reported separately instead of silently
   dropped. Lesson recorded: list distinct values before trusting a
   column.

3. **The AI's first discount design lost money on large orders.**
   The initial proposal was an uncapped 5% prepaid discount. Checking
   it against the maths showed 5% of a Rs 2,999 order is Rs 150 —
   nearly four times the ~Rs 41.33 expected RTO saving per converted
   order (28.4% x Rs 169.40 minus 4% x Rs 169.40). Caught by testing
   the discount against the highest order value in the file (Rs 2,999),
   not just the average (Rs 649). Fixed as 5% capped at Rs 40, which
   stays under the saving on every order value. Lesson recorded: test
   a money rule at the extremes of the data, not just the average.

## How AI output was verified in general

- Every data claim in the memo traces to `analysis.py` output
  (`analysis.json`), which anyone can re-run.
- The backtest is out-of-time (April–August trains, September tests),
  so the reported September numbers are not fitted to September.
- The engine's demo and dashboard outputs were run, not just read:
  `cod_engine.py --demo`, `whatsapp_sim.py --demo`, and
  `dashboard.py` were all executed and their outputs checked against
  the analysis before this package was finalised.
