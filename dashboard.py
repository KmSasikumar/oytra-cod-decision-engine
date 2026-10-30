"""Founder morning dashboard (Part 3) — one screen, one day.

Reads a CSV of orders, runs the decision engine over one day's orders,
and writes a self-contained dashboard.html (no external assets, no
server) plus a terminal summary.

Money rules, stated on the page itself:
  - Rs saved = actual RTOs inside the Hold bucket x Rs 169.40 per RTO.
    (Those orders were held, so those returns never happened.)
  - Rs lost = gross margin (62%) on the actually-delivered orders inside
    the Hold bucket. (Those sales were given up.)
  - Nudge bucket: shown under a labelled 50%-conversion scenario, using
    the brief-given prepaid RTO rate (4%) — the data file has no prepaid
    orders, so this part is a scenario, not a measurement.
  - Confirmation bucket: size and actual RTO rate only. No rupee saving
    is claimed for it, because the file cannot show who would reply on
    WhatsApp. Its value (screening out unreachable customers) becomes
    measurable once reply rates are logged.

Usage:
    python3 dashboard.py                      # latest day in the file
    python3 dashboard.py --date 2026-09-30
    python3 dashboard.py --csv my_orders.csv --date 2026-10-01 --out dash.html
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cod_engine import CONFIG, decide, normalize_status  # noqa: E402

HERE = Path(__file__).resolve().parent
COST = CONFIG["costs"]["per_rto_cost"]
MARGIN = CONFIG["brief_figures"]["gross_margin_rate"]
PREPAID_RTO = CONFIG["brief_figures"]["prepaid_rto_rate"]
CONV = 0.5  # labelled scenario, not a measurement


def build(csv_path, day, days=1):
    rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
    from datetime import date, timedelta
    end = date.fromisoformat(day)
    start = end - timedelta(days=days - 1)
    day_rows = [r for r in rows if start.isoformat() <= r["order_datetime"][:10] <= day]
    buckets = defaultdict(list)
    for r in day_rows:
        r["status"] = normalize_status(r.get("final_status", ""))
        r["is_rto"] = r["status"] == "RTO"
        r["resolved"] = r["status"] in ("DELIVERED", "RTO")
        r["value"] = float(r.get("order_value") or 0)
        buckets[decide(r)["bucket"]].append(r)
    stats = {}
    for b, rs in buckets.items():
        res = [r for r in rs if r["resolved"]]
        stats[b] = {"n": len(rs), "rto": sum(r["is_rto"] for r in res),
                    "rate": (sum(r["is_rto"] for r in res) / len(res)) if res else 0.0}
    hold = buckets.get("Hold / cancel", [])
    saved = sum(1 for r in hold if r["is_rto"]) * COST
    lost = sum(r["value"] for r in hold if not r["is_rto"]) * MARGIN
    nudge = buckets.get("Nudge to prepaid", [])
    nudge_rate = stats.get("Nudge to prepaid", {}).get("rate", 0.0)
    nudge_avoided = len(nudge) * CONV * max(nudge_rate - PREPAID_RTO, 0)
    nudge_discount = sum(min(r["value"] * 0.05, 40) for r in nudge) * CONV
    nudge_net = nudge_avoided * COST - nudge_discount
    net = saved - lost + nudge_net
    return {"day": day, "days": days, "total": len(day_rows), "buckets": stats,
            "saved_rs": round(saved, 2), "lost_rs": round(lost, 2),
            "nudge_net_rs": round(nudge_net, 2), "net_rs": round(net, 2)}


HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Oytra COD dashboard — {day}</title>
<style>
body{{font-family:system-ui,Arial,sans-serif;max-width:760px;margin:32px auto;padding:0 16px;color:#222}}
h1{{font-size:22px}} .cards{{display:flex;gap:12px;flex-wrap:wrap}}
.card{{border:1px solid #ddd;border-radius:10px;padding:14px 18px;flex:1;min-width:150px}}
.card b{{font-size:26px;display:block}} table{{border-collapse:collapse;width:100%;margin-top:16px}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left}} .net{{font-size:20px;margin-top:16px}}
small{{color:#666}}
</style></head><body>
<h1>Good morning — COD decisions for {label}</h1>
<p>{total} COD orders in this period.</p>
<div class="cards">
<div class="card"><b>{ship}</b>Ship as-is</div>
<div class="card"><b>{confirm}</b>Ship after confirmation</div>
<div class="card"><b>{nudge}</b>Nudge to prepaid</div>
<div class="card"><b>{hold}</b>Hold / cancel</div>
</div>
<table>
<tr><th>Measure</th><th>Rs</th><th>How it is calculated</th></tr>
<tr><td>Estimated saved from avoided RTOs</td><td>{saved}</td><td>Actual RTOs inside the Hold bucket x Rs 169.40 per RTO</td></tr>
<tr><td>Estimated lost from cancelled genuine orders</td><td>{lost}</td><td>62% margin on actually-delivered orders inside the Hold bucket</td></tr>
<tr><td>Nudge-to-prepaid net (50% conversion scenario)</td><td>{nudge_net}</td><td>Scenario only: assumes half of nudged customers convert; prepaid RTO 4% is from the brief, not the data file</td></tr>
<tr><td><b>Net impact</b></td><td><b>{net}</b></td><td>Saved - lost + nudge net</td></tr>
</table>
<p class="net">Confirmation bucket: {confirm} orders, actual RTO rate {confirm_rate}%. No rupee saving is claimed for confirmations — the file cannot show who would reply on WhatsApp. Once reply rates are logged, this becomes measurable.</p>
<p><small>Assumptions, stated plainly: per-RTO cost Rs 169.40 (Rs 65 + Rs 65 + Rs 25 + 8% x Rs 180); margin 62%; prepaid RTO 4% is brief-given because the data file contains only COD orders. Bucket RTO rates above are the orders' actual outcomes.</small></p>
</body></html>"""


def render(d):
    b = d["buckets"]
    label = d["day"] if d["days"] == 1 else f"{d['day']} (last {d['days']} days)"
    return HTML.format(
        day=d["day"], label=label, total=d["total"],
        ship=b.get("Ship as-is", {}).get("n", 0),
        confirm=b.get("Ship after confirmation", {}).get("n", 0),
        nudge=b.get("Nudge to prepaid", {}).get("n", 0),
        hold=b.get("Hold / cancel", {}).get("n", 0),
        saved=f"Rs {d['saved_rs']:,.2f}", lost=f"Rs {d['lost_rs']:,.2f}",
        nudge_net=f"Rs {d['nudge_net_rs']:,.2f}", net=f"Rs {d['net_rs']:,.2f}",
        confirm_rate=f"{b.get('Ship after confirmation', {}).get('rate', 0.0):.1%}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Oytra founder dashboard")
    ap.add_argument("--csv", default=str(HERE / "data" / "orders_sample.csv"))
    ap.add_argument("--date", help="Last day to report, YYYY-MM-DD (default: latest day in file)")
    ap.add_argument("--days", type=int, default=1,
                    help="How many days to aggregate (default 1 = a single morning's view)")
    ap.add_argument("--out", default=str(HERE / "dashboard.html"))
    args = ap.parse_args(argv)
    rows = list(csv.DictReader(open(args.csv, newline="", encoding="utf-8")))
    day = args.date or max(r["order_datetime"][:10] for r in rows)
    d = build(args.csv, day, days=args.days)
    Path(args.out).write_text(render(d), encoding="utf-8")
    print(f"Period ending {day} ({args.days} day(s)): {d['total']} orders")
    for b, s in d["buckets"].items():
        print(f"  {b}: {s['n']} orders, actual RTO rate {s['rate']:.1%}")
    print(f"  Saved Rs {d['saved_rs']:,.2f} | Lost Rs {d['lost_rs']:,.2f} | "
          f"Nudge net Rs {d['nudge_net_rs']:,.2f} | NET Rs {d['net_rs']:,.2f}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
