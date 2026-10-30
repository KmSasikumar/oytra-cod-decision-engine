"""COD decision engine for the Oytra take-home assignment.

Pure standard library. No network calls, no model keys. The deterministic
checker below covers every fake-name and address pattern actually observed
in orders_sample.csv; the LLM hook at the bottom shows exactly where a
language model would plug in for judgement cases (novel fake names,
Hinglish address reading) without claiming a live model is wired in.

Usage:
    python3 cod_engine.py --order '{"customer_name": "Priya", "phone": "9876543210",
        "address": "12, MG Road", "city": "Pune", "state": "Maharashtra",
        "pincode": "411001", "order_value": 649, "customer_prior_orders": 0,
        "customer_prior_rto": 0}'
    python3 cod_engine.py --csv data/orders_sample.csv --out decisions.csv
    python3 cod_engine.py --demo
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

FAKE_NAMES = {
    "test", "asdf", "qwerty", "abc", "xyz", "test test", "test user",
    "dummy", "demo", "sample", "name", "user",
}
FAKE_PATTERN = re.compile(r"^(asdf|test|qwerty|xxx+|aaa+|zzz+|123+)[\s\W]*(asdf|test|qwerty|xxx+|aaa+|zzz+|123+)?$", re.IGNORECASE)


def normalize_status(raw):
    """The data file spells statuses inconsistently ('RTO', 'Rto', 'RTO ',
    'delivered'). Normalise before counting, or RTOs get undercounted."""
    s = (raw or "").strip().upper()
    if s in ("DELIVERED", "RTO"):
        return s
    return "UNKNOWN"


def looks_fake_name(name):
    n = (name or "").strip().lower()
    if n in FAKE_NAMES:
        return True
    if re.fullmatch(r"(.)\1{3,}", n):  # aaaa, zzzz, ...
        return True
    if FAKE_PATTERN.match(n):
        return True
    # Single gibberish token with no vowel and 4+ letters, e.g. 'zxqw'
    if re.fullmatch(r"[bcdfghjklmnpqrstvwxz]{4,}", n):
        return True
    return False


def address_flags(address):
    addr = (address or "").strip()
    short = len(addr) < 20
    no_digit = not re.search(r"\d", addr)
    return short, no_digit


def llm_address_check(order):
    """HOOK, not a live call. Where a language model would help, and what it
    would be asked:

      - "Is this address complete and real, or vague/fake?"
        (e.g. 'Station chowk se left, Hanuman Mandir ke saamne' is a real
        Hinglish landmark address, not a fake one — a fixed rule cannot
        tell that apart from 'asdf street'.)
      - "Does this name look like a real person's name or a test entry?"
        (novel gibberish the deterministic list has never seen.)
      - "Extract the house number / street / landmark from this Hinglish
        address, if present."

    Contract: returns dict with keys address_ok (bool), fake_name (bool),
    reason (str). The deterministic checker below is the fallback and is
    what actually runs in this submission; wire a real model behind this
    function only when you can log and audit its answers, because a wrong
    LLM call here cancels real orders.
    """
    short, no_digit = address_flags(order.get("address", ""))
    return {
        "address_ok": not (short and no_digit),
        "fake_name": looks_fake_name(order.get("customer_name", "")),
        "reason": "deterministic fallback (no live LLM wired in)",
    }


def score_order(order, config=None):
    """Return (score, [(points, plain-English reason), ...]).

    Scores are transparent on purpose: an operations person must be able to
    read why an order was held, and a threshold change must not need a
    redeploy. Weights live in config.json.
    """
    cfg = config or CONFIG
    w = cfg["score_weights"]
    pts = []
    priors = int(order.get("customer_prior_orders") or 0)
    prior_rto = int(order.get("customer_prior_rto") or 0)
    name = order.get("customer_name", "")
    short, no_digit = address_flags(order.get("address", ""))
    fake = looks_fake_name(name)

    if prior_rto >= 2:
        pts.append((w["prior_rto_2_or_more"],
                    f"Customer has {prior_rto} past returns (RTO) — the strongest warning sign in the data."))
    elif prior_rto == 1:
        pts.append((w["prior_rto_1"],
                    "Customer has 1 past return (RTO)."))
    if priors == 0:
        pts.append((w["first_time_buyer"],
                    "First-time buyer — no delivery history with us yet."))
    elif prior_rto == 0:
        pts.append((w["repeat_buyer_clean_history"],
                    "Repeat buyer with no past returns — the safest group in the data."))
    # Short and no-digit do NOT stack: in the data every short address
    # already lacks a digit, so adding both would double-count one signal.
    if short:
        pts.append((w["short_address_under_20_chars"],
                    "Address is very short (under 20 characters) — often undeliverable."))
    elif no_digit:
        pts.append((w["address_without_house_number"],
                    "Address has no house or building number — couriers struggle to deliver."))
    if fake:
        pts.append((w["fake_or_test_name"],
                    f"Name looks like a test or fake entry ('{name.strip()}')."))
    if order.get("state") in cfg["high_risk_states"]:
        pts.append((w["high_risk_state"],
                    f"Delivery state ({order.get('state')}) has a high past RTO rate."))
    try:
        value = float(order.get("order_value") or 0)
    except (TypeError, ValueError):
        value = 0
    if 500 <= value < 700:
        pts.append((w["order_value_500_to_700"],
                    "Order value Rs 500-700 — the value band with the highest past RTO rate."))
    return sum(p for p, _ in pts), pts


def decide(order, config=None):
    """Return dict: bucket, score, reasons (plain English), and the maths."""
    cfg = config or CONFIG
    th = cfg["thresholds"]
    score, pts = score_order(order, cfg)
    priors = int(order.get("customer_prior_orders") or 0)
    fake = looks_fake_name(order.get("customer_name", ""))
    capped = False
    if score >= th["hold_cancel"]:
        bucket = "Hold / cancel"
    elif score >= th["nudge_to_prepaid"]:
        bucket = "Nudge to prepaid"
    elif score >= th["ship_after_confirmation"]:
        bucket = "Ship after confirmation"
    else:
        bucket = "Ship as-is"
    # First-time-buyer protection: a genuine first order is never
    # auto-cancelled. Fake/test names are not genuine customers, so the
    # cap does not apply to them.
    if bucket == "Hold / cancel" and priors == 0 and not fake:
        bucket = "Nudge to prepaid"
        capped = True
    reasons = [r for _, r in pts] or ["No risk signals — clean history and a complete address."]
    if capped:
        reasons.append("Held back from auto-cancel because this is a genuine first-time "
                       "buyer — cancelling a first order wastes the Rs 300+ spent acquiring them.")
    return {"bucket": bucket, "score": score, "reasons": reasons, "capped": capped}


def prepaid_discount(order_value, config=None):
    """5% off, capped at Rs 40. See config.json for the maths."""
    cfg = config or CONFIG
    d = cfg["prepaid_discount"]
    return min(round(float(order_value) * d["percent"], 2), d["cap_rs"])


def decide_csv(in_path, out_path=None, config=None):
    rows = list(csv.DictReader(open(in_path, newline="", encoding="utf-8")))
    out = []
    for r in rows:
        d = decide(r, config)
        out.append({**r, "risk_score": d["score"], "bucket": d["bucket"],
                    "reasons": " | ".join(d["reasons"]),
                    "status_norm": normalize_status(r.get("final_status", ""))})
    if out_path:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            writer.writeheader()
            writer.writerows(out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Oytra COD decision engine")
    ap.add_argument("--order", help="Order as a JSON string")
    ap.add_argument("--csv", help="Input CSV of orders")
    ap.add_argument("--out", help="Output CSV path (with --csv)")
    ap.add_argument("--demo", action="store_true", help="Run three example orders")
    args = ap.parse_args(argv)
    if args.demo:
        examples = [
            {"customer_name": "Priya Sharma", "address": "45, Lake View Apartments, HSR Layout",
             "city": "Bengaluru", "state": "Karnataka", "order_value": 649,
             "customer_prior_orders": 2, "customer_prior_rto": 0},
            {"customer_name": "Rahul Verma", "address": "near temple",
             "city": "Gorakhpur", "state": "Uttar Pradesh", "order_value": 599,
             "customer_prior_orders": 0, "customer_prior_rto": 0},
            {"customer_name": "test", "address": "asdf",
             "city": "Patna", "state": "Bihar", "order_value": 899,
             "customer_prior_orders": 3, "customer_prior_rto": 2},
        ]
        for ex in examples:
            d = decide(ex)
            print(f"{ex['customer_name']!r:20} score={d['score']:3} -> {d['bucket']}")
            for r in d["reasons"]:
                print(f"    - {r}")
        return 0
    if args.order:
        d = decide(json.loads(args.order))
        print(json.dumps(d, indent=2, ensure_ascii=False))
        return 0
    if args.csv:
        rows = decide_csv(args.csv, args.out)
        buckets = {}
        for r in rows:
            buckets[r["bucket"]] = buckets.get(r["bucket"], 0) + 1
        print(f"Decided {len(rows)} orders: {buckets}")
        if args.out:
            print(f"Wrote {args.out}")
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
