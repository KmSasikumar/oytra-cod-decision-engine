"""Generate memo.pdf — the business memo to the founder (Part 4).

Every number below comes from analysis.py / analysis.json, computed from
orders_sample.csv. If a figure changes in the data, re-run analysis.py
and update the matching line here — do not edit numbers by hand from
memory.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.lib import colors

HERE = Path(__file__).resolve().parent

S = {
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=17, leading=20, spaceAfter=2 * mm),
    "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=9.5, leading=12, textColor=colors.HexColor("#444444"), spaceAfter=4 * mm),
    "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11, leading=13, spaceBefore=3.5 * mm, spaceAfter=1.5 * mm),
    "b": ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=13.5, spaceAfter=1.5 * mm),
    "bul": ParagraphStyle("bul", fontName="Helvetica", fontSize=10, leading=13.5, leftIndent=10, bulletIndent=2, spaceAfter=1.2 * mm),
    "box": ParagraphStyle("box", fontName="Helvetica", fontSize=10, leading=13.5),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=9.5, leading=12),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=9.5, leading=12),
    "foot": ParagraphStyle("foot", fontName="Helvetica-Oblique", fontSize=8.5, leading=11, textColor=colors.HexColor("#555555")),
}

P = Paragraph


def build():
    story = [
        P("Memo: a COD decision system that saves money without killing growth", S["title"]),
        P("To: Founder, Oytra &nbsp;|&nbsp; From: Sasi Kumar Yadav &nbsp;|&nbsp; 30 October 2026 &nbsp;|&nbsp; "
          "Based on 2,017 resolved orders from orders_sample.csv (April–September 2026)", S["sub"]),
        P("<b>Recommendation in one paragraph.</b> Do not cancel risky COD orders outright, and do not "
          "ship everything and absorb the returns. Score every COD order, confirm the doubtful ones on "
          "WhatsApp before shipping, offer the riskiest a small prepaid discount, and auto-cancel only "
          "the tiny group that is almost certainly not a real sale. On September's 334 sampled orders "
          "this would have netted <b>Rs 893.62</b> (holds plus prepaid nudges at a 50% conversion "
          "scenario) — a modest, honest saving, not a miracle. The bigger prize is the confirmation "
          "screen itself: it stops unreachable customers before dispatch, and its value becomes "
          "measurable within two weeks of logging reply rates.", S["b"]),
        P("1. What surprised me in the data", S["h"]),
        P("<b>(a) Pincode blocking cannot work on this data — and that kills the simplest version of "
          "the Operations plan.</b> The file has 1,067 distinct pincodes for 2,017 orders; the busiest "
          "pincode has just 12 orders and none has 20 or more. There is no such thing as a "
          "'bad-history pincode' here yet. Geography still matters, but at state and city level: "
          "Bihar 53.4% RTO, Uttar Pradesh 44.7% and Madhya Pradesh 38.5%, against Maharashtra 17.9% "
          "(Gorakhpur 63.0%, Bareilly 60.6%, Darbhanga 58.1% vs Mumbai 17.8%, Pune 18.1%).", S["bul"]),
        P("<b>(b) Address quality is the strongest single signal — and Hinglish is not the problem.</b> "
          "Orders with addresses under 20 characters returned 62.0% of the time (187 orders); "
          "addresses with no house or building number returned 40.4% (586 orders); names that look "
          "fake or test-like (test, asdf, qwerty) returned 62.5% (24 orders). But addresses written "
          "in Hinglish ('Station chowk se left, Hanuman Mandir ke saamne') returned 30.8% — barely "
          "above the 28.4% average. Penalising Hinglish would punish normal customers; penalising "
          "missing structure catches the real risk.", S["bul"]),
        P("<b>(c) History beats newness — but first-timers are the business.</b> Repeat buyers with a "
          "clean record returned only 13.8% of the time, while customers with 2+ past returns came "
          "back 76.5% of the time. Yet first-time buyers are 1,517 of 2,017 orders (75%) and return "
          "30.3% of the time. Any rule that cancels first-timers broadly cancels the company. "
          "First-timers from Meta ads are the riskiest large segment of all: 34.3% RTO (572 orders), "
          "against 22.7% for direct traffic.", S["bul"]),
        P("<b>(d) The file itself needs care before anyone trusts a dashboard built on it.</b> The "
          "same outcome is spelled 'RTO', 'Rto', 'RTO ' and 'delivered'; three delivered orders show "
          "order value Rs 0; 12 rows have no pincode; and prior-order counts top out at 5, which "
          "looks like a cap. None of this changes the conclusions, but any live system must "
          "normalise statuses on import or it will quietly undercount returns.", S["bul"]),
        P("2. The recommended rules", S["h"]),
        P("Every COD order gets a transparent score (weights in the repo's config file, changeable "
          "without touching code) and lands in one of four buckets:", S["b"]),
    ]
    tbl = Table([
        [P("<b>Bucket</b>", S["cellb"]), P("<b>Who lands here</b>", S["cellb"]), P("<b>What happens</b>", S["cellb"])],
        [P("Ship as-is", S["cell"]), P("Clean history, complete address", S["cell"]), P("Ship normally", S["cell"])],
        [P("Ship after confirmation", S["cell"]), P("Some risk: first-timer, weak address, high-risk state", S["cell"]), P("WhatsApp confirmation first; no reply in 24h = hold", S["cell"])],
        [P("Nudge to prepaid", S["cell"]), P("High risk but plausibly genuine", S["cell"]), P("Offer 5% off (capped at Rs 40) to pay online", S["cell"])],
        [P("Hold / cancel", S["cell"]), P("Repeat returners, fake names, worst combinations", S["cell"]), P("Do not ship", S["cell"])],
    ], colWidths=[32 * mm, 68 * mm, 62 * mm])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBBBBB")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [tbl, Spacer(1, 2 * mm),
        P("One protection is built in, not just scored: <b>a genuine first-time buyer is never "
          "auto-cancelled</b> — first orders are capped at the prepaid nudge. Fake or test names "
          "are exempt: they are not real customers.", S["b"]),
        P("3. What this would have done to last month's orders", S["h"]),
        P("Backtest method, stated plainly: rules were set from April–August data and tested on "
          "September's 334 orders, so September was not used to fit the rules. September actually "
          "had 87 returns, costing Rs 14,737.80 at Rs 169.40 per return "
          "(Rs 65 + Rs 65 + Rs 25 + 8% x Rs 180 damaged).", S["b"])]
    tbl2 = Table([
        [P("<b>Bucket</b>", S["cellb"]), P("<b>Orders</b>", S["cellb"]), P("<b>Actual RTO rate</b>", S["cellb"]), P("<b>Money effect</b>", S["cellb"])],
        [P("Ship as-is", S["cell"]), P("253", S["cell"]), P("21.7%", S["cell"]), P("—", S["cell"])],
        [P("Ship after confirmation", S["cell"]), P("68", S["cell"]), P("32.4%", S["cell"]), P("Not claimed (see below)", S["cell"])],
        [P("Nudge to prepaid", S["cell"]), P("10", S["cell"]), P("70.0%", S["cell"]), P("Rs 385.42 net at 50% conversion", S["cell"])],
        [P("Hold / cancel", S["cell"]), P("3", S["cell"]), P("100.0%", S["cell"]), P("Rs 508.20 saved, Rs 0 margin lost", S["cell"])],
    ], colWidths=[38 * mm, 20 * mm, 30 * mm, 74 * mm])
    tbl2.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBBBBB")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [tbl2, Spacer(1, 2 * mm),
        P("Two honest caveats. First, the score ranks risk correctly — rates rise bucket by bucket — "
          "but most September returns still looked ordinary on paper (55 of 87 sat in Ship as-is). "
          "That is why the claimed saving is small: this system trims the worst slice, it does not "
          "abolish returns. Second, <b>no rupee saving is claimed for confirmations</b>: the file "
          "cannot show who would reply on WhatsApp, so inventing a reply rate would be fiction. "
          "September's file is also a 334-order sample, not the full month; if it is representative "
          "of ~3,000 monthly orders, the same rules would be worth roughly Rs 8,000 a month before "
          "any confirmation-screening gains.", S["b"]),
        P("4. Balancing Operations vs Marketing, in rupees", S["h"]),
        P("A return costs Rs 169.40. A lost new customer costs Rs 300+ in acquisition spend, plus "
          "every future order they would have placed. So the system spends its strictness where a "
          "return is nearly certain — repeat returners, fake names, undeliverable addresses — and "
          "spends its gentleness where the customer is real but unproven: first-timers get a "
          "confirmation message or a discount, never an automatic cancellation. The prepaid "
          "discount maths: a COD order carries an expected return cost of 28.4% x Rs 169.40 = "
          "Rs 48.11; a prepaid order, at the brief's 4% return rate, carries Rs 6.78; so each "
          "conversion saves about Rs 41.33, which is why the discount is 5% capped at Rs 40 — it "
          "can never cost more than it saves. (Note: the 4% prepaid rate comes from the brief, "
          "not the data file, which contains only COD orders.)", S["b"]),
        P("5. What could go wrong, and how we would notice", S["h"]),
        P("<b>Threshold drift:</b> customer mix changes (festive season, new ad channel) and the "
          "buckets stop ranking risk. Notice it by watching each bucket's weekly return rate — if "
          "Ship as-is climbs toward the confirmation bucket's rate, retune. <b>Confirmation "
          "fatigue:</b> customers stop replying and genuine orders stall. Notice it in the reply "
          "rate; if replies fall, shorten the message and re-test the wording. <b>Discount "
          "gaming:</b> customers learn to pick COD to harvest the discount. Notice it in the "
          "repeat-nudge rate per phone number; cap nudges per customer. <b>Fake patterns evolve:</b> "
          "new gibberish names bypass the list. Notice it in the manual-hold queue and add the "
          "pattern — this is the one place a language model earns its keep. <b>Bad data in:</b> "
          "status spellings and zero-value orders recur. Notice it with a daily import check that "
          "fails loudly on unknown statuses instead of silently dropping rows.", S["bul"]),
        P("6. What I would build next with two more weeks", S["h"]),
        P("Wire the language-model address check behind the existing hook, with every answer logged "
          "and audited before it can cancel an order. Add a courier serviceability check so "
          "undeliverable pincodes are caught before dispatch, not after a return. Run the two "
          "experiments the data points to: confirm Meta-ads first-timers in high-risk states "
          "first, and A/B test the discount (Rs 30 vs 5% capped at Rs 40). Finally, accumulate "
          "real pincode history for a quarter — only then revisit the pincode question, with "
          "numbers instead of opinions.", S["b"]),
        Spacer(1, 3 * mm),
        P("All figures above are recomputed by analysis.py from orders_sample.csv; the code, "
          "WhatsApp mock, dashboard, decision log and AI usage log are in the accompanying repo, "
          "which runs in under 10 minutes with no dependencies beyond Python 3.10+.", S["foot"]),
    ]
    doc = BaseDocTemplate(str(HERE / "memo.pdf"), pagesize=A4,
                          leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=16 * mm, bottomMargin=16 * mm,
                          title="Oytra COD decision system — memo to the founder",
                          author="Sasi Kumar Yadav")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame])])
    doc.build(story)
    print("Wrote memo.pdf")


if __name__ == "__main__":
    build()
