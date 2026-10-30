"""Reproduce every number quoted in the memo, from orders_sample.csv.

Run:  python3 analysis.py
Writes: analysis.json (all figures) and prints a human-readable summary.

Method notes (these matter for honesty):
- final_status is normalised (strip + upper-case) because the file spells
  it as 'RTO', 'Rto', 'RTO ' and 'delivered'. One IN_TRANSIT row has no
  outcome yet and is excluded from RTO rates, but counted separately.
- Backtest is OUT-OF-TIME, not in-sample: state risk lists and all rates
  used to decide September orders are computed from April-August only.
  September is the "last month" in the file (334 orders, 2026-09-01..30).
- The prepaid RTO rate (4%) comes from the assignment brief, NOT this
  file: all 2,018 rows are COD, so no prepaid rate can be computed here.
  Every place it is used is labelled 'brief-given'.
- Confirmation-bucket savings are NOT claimed: the file cannot show who
  would have replied on WhatsApp, so that bucket is reported with its
  size and actual RTO rate only, and no rupee saving is attached to it.
"""

import collections
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cod_engine import CONFIG, decide, normalize_status, looks_fake_name  # noqa: E402

HERE = Path(__file__).resolve().parent
CSV = HERE / "data" / "orders_sample.csv"
COST = CONFIG["costs"]["per_rto_cost"]
MARGIN = CONFIG["brief_figures"]["gross_margin_rate"]
PREPAID_RTO = CONFIG["brief_figures"]["prepaid_rto_rate"]


def load():
    rows = list(csv.DictReader(open(CSV, newline="", encoding="utf-8")))
    for r in rows:
        r["status"] = normalize_status(r.get("final_status", ""))
        r["is_rto"] = r["status"] == "RTO"
        r["resolved"] = r["status"] in ("DELIVERED", "RTO")
        r["value"] = float(r.get("order_value") or 0)
        r["priors"] = int(r.get("customer_prior_orders") or 0)
        r["prior_rto"] = int(r.get("customer_prior_rto") or 0)
    return rows


def rate(rs):
    rs = [r for r in rs if r["resolved"]]
    return {"n": len(rs), "rto": sum(r["is_rto"] for r in rs),
            "rate": (sum(r["is_rto"] for r in rs) / len(rs)) if rs else 0.0}


def main():
    rows = load()
    res = [r for r in rows if r["resolved"]]
    out = {}
    out["rows_total"] = len(rows)
    out["rows_resolved"] = len(res)
    out["rows_unresolved"] = [r["order_id"] for r in rows if not r["resolved"]]
    out["overall"] = rate(res)
    out["payment_mix"] = dict(collections.Counter(r["payment_method"] for r in rows))
    out["status_raw_values"] = dict(collections.Counter(r["final_status"] for r in rows))
    out["months"] = dict(sorted(collections.Counter(r["order_datetime"][:7] for r in rows).items()))
    out["first_timer_share"] = {
        "n": sum(1 for r in res if r["priors"] == 0), "of": len(res),
        "rate": rate([r for r in res if r["priors"] == 0])["rate"]}
    out["clean_repeat_rate"] = rate([r for r in res if r["priors"] >= 1 and r["prior_rto"] == 0])
    out["prior_rto_2_rate"] = rate([r for r in res if r["prior_rto"] >= 2])
    out["prior_rto_1_rate"] = rate([r for r in res if r["prior_rto"] == 1])
    out["short_address"] = rate([r for r in res if len(r["address"].strip()) < 20])
    out["no_digit_address"] = rate([r for r in res if not re.search(r"\d", r["address"])])
    out["fake_name"] = rate([r for r in res if looks_fake_name(r["customer_name"])])
    out["hinglish_address"] = rate([r for r in res if any(
        w in r["address"].lower() for w in (" ke saamne", " se left", " ke paas", " gali ", " chowk "))])
    out["meta_first_timer"] = rate([r for r in res if r["priors"] == 0 and r["utm_source"] == "meta_ads"])
    out["meta_overall"] = rate([r for r in res if r["utm_source"] == "meta_ads"])
    out["direct_overall"] = rate([r for r in res if r["utm_source"] == "direct"])
    pincodes = collections.Counter(r["pincode"] for r in res)
    out["pincodes"] = {"distinct": len(pincodes), "max_orders_in_one": max(pincodes.values()),
                       "with_20_or_more": sum(1 for v in pincodes.values() if v >= 20),
                       "empty_pincode_rows": sum(1 for r in res if not r["pincode"].strip())}
    for key in ("state", "city"):
        g = collections.defaultdict(list)
        for r in res:
            g[r[key]].append(r)
        out[key + "_rates"] = {k: rate(v) for k, v in sorted(g.items()) if len(v) >= 30}
    out["value_bands"] = {}
    for lo, hi in [(0, 300), (300, 500), (500, 700), (700, 1000), (1000, 10 ** 9)]:
        out["value_bands"][f"{lo}-{hi}"] = rate([r for r in res if lo <= r["value"] < hi])
    out["zero_value_orders"] = [r["order_id"] for r in rows if r["value"] == 0]

    # ---- Out-of-time backtest: train Apr-Aug, test September ----
    train = [r for r in res if r["order_datetime"] < "2026-09"]
    test = [r for r in res if r["order_datetime"] >= "2026-09"]
    sg = collections.defaultdict(list)
    for r in train:
        sg[r["state"]].append(r)
    train_states = {k: rate(v)["rate"] for k, v in sg.items() if len(v) >= 50}
    high_risk_train = sorted(k for k, v in train_states.items() if v >= 0.35)
    cfg = json.loads(json.dumps(CONFIG))
    cfg["high_risk_states"] = high_risk_train
    buckets = collections.defaultdict(list)
    for r in test:
        buckets[decide(r, cfg)["bucket"]].append(r)
    bt = {}
    for b, rs in buckets.items():
        bt[b] = {**rate(rs),
                 "delivered_value_margin": round(sum(r["value"] for r in rs if not r["is_rto"]) * MARGIN, 2)}
    bt["train_high_risk_states"] = {k: round(train_states[k], 3) for k in high_risk_train}
    bt["test_overall"] = rate(test)
    bt["test_actual_rto_cost"] = round(rate(test)["rto"] * COST, 2)
    # Hold bucket: avoided RTOs are the actual RTOs in it; lost margin is
    # the margin on the actually-delivered orders in it.
    hold = buckets.get("Hold / cancel", [])
    bt["hold_saved_rs"] = round(sum(1 for r in hold if r["is_rto"]) * COST, 2)
    bt["hold_lost_margin_rs"] = round(sum(r["value"] for r in hold if not r["is_rto"]) * MARGIN, 2)
    # Nudge bucket: expected RTOs fall from the bucket's actual rate to the
    # brief-given prepaid rate, on the share that converts. Discount is
    # only paid on converted orders (5% capped at Rs 40, on actual values).
    nudge = buckets.get("Nudge to prepaid", [])
    nudge_rate = rate(nudge)["rate"] if nudge else 0
    bt["nudge"] = {}
    for conv in (0.3, 0.5):
        converted = len(nudge) * conv
        avoided = converted * max(nudge_rate - PREPAID_RTO, 0)
        discount_cost = sum(min(r["value"] * 0.05, 40) for r in nudge) * conv
        bt["nudge"][f"conversion_{int(conv*100)}pct"] = {
            "converted_orders": round(converted, 1),
            "expected_rtos_avoided": round(avoided, 1),
            "saved_rs": round(avoided * COST, 2),
            "discount_cost_rs": round(discount_cost, 2),
            "net_rs": round(avoided * COST - discount_cost, 2)}
    bt["net_hold_plus_nudge50"] = round(
        bt["hold_saved_rs"] - bt["hold_lost_margin_rs"]
        + bt["nudge"]["conversion_50pct"]["net_rs"], 2)
    out["september_backtest"] = bt
    out["costs"] = {"per_rto_rs": COST, "margin_rate": MARGIN,
                    "prepaid_rto_rate_brief_given": PREPAID_RTO}
    (HERE / "analysis.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str))
    print("\nWrote analysis.json")


if __name__ == "__main__":
    main()
