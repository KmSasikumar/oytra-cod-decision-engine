"""Working mock of the Oytra WhatsApp confirmation flow (Part 2).

No real WhatsApp account, no network. A state machine over scripted or
typed replies, so the whole flow can be watched end to end in a terminal.

Flows:
  - "Ship after confirmation": send confirmation -> YES ships the order,
    NO cancels it, an unclear reply gets ONE clarifying re-ask and then a
    manual hold, no reply gets a reminder at 12h and a hold at 24h
    (never shipped unconfirmed).
  - "Nudge to prepaid": offer the discount (5% capped at Rs 40, see
    config.json) -> YES sends a mock payment link -> paid ships as
    prepaid; NO falls back to the confirmation flow (the sale is not
    thrown away just because the discount was refused); no reply in 24h
    holds the order.

Language: Hinglish (Roman script) first, with a short English line. The
order data shows customers themselves write addresses in Hinglish, so
confirmation in the customer's own register is the one most likely to be
answered. Hinglish is never treated as a risk signal.

Usage:
    python3 whatsapp_sim.py --demo          # scripted scenarios
    python3 whatsapp_sim.py --interactive   # type replies yourself
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cod_engine import CONFIG, prepaid_discount  # noqa: E402

REMINDER_HOURS = CONFIG["whatsapp"]["reminder_after_hours"]
EXPIRY_HOURS = CONFIG["whatsapp"]["expiry_hours"]


def confirm_message(order):
    return (
        f"Namaste {order['customer_name']}! Aapka Oytra order {order['order_id']} "
        f"({order.get('items', 'your items')}) COD par book hua hai. Delivery se pehle "
        f"bas ek confirmation chahiye — kya aap ye order lena chahte hain? "
        f"Reply karein: YES (haan, bhej dijiye) ya NO (cancel kar dijiye). "
        f"[English: Please reply YES to confirm your COD order, or NO to cancel it.]"
    )


def nudge_message(order):
    discount = prepaid_discount(order["order_value"])
    return (
        f"Namaste {order['customer_name']}! Aap COD par order kar rahe hain. "
        f"Agar aap abhi online pay karte hain to aapko Rs {discount:g} ka discount "
        f"milega, aur delivery bhi jaldi hogi. Pay karne ke liye YES likhein, "
        f"COD hi rakhna hai to NO likhein. "
        f"[English: Pay online now and save Rs {discount:g}. Reply YES for the "
        f"prepaid link, or NO to keep COD.]"
    )


def clarifying_message():
    return ("Sorry, samajh nahi aaya — please reply YES ya NO likhein. "
            "[English: Sorry, I didn't understand — please reply YES or NO.]")


def reminder_message():
    return ("Reminder: aapka COD order abhi confirm nahi hua hai. Agar aap order "
            "lena chahte hain to YES reply karein, warna 24 ghante baad order "
            "hold par chala jayega. [English: Reminder: your COD order is still "
            "unconfirmed. Reply YES to confirm, otherwise it will be put on hold.]")


def _is_yes(text):
    return text.strip().lower() in ("yes", "y", "haan", "ha", "confirm", "ok", "okay")


def _is_no(text):
    return text.strip().lower() in ("no", "n", "nahi", "cancel", "mat bhejo")


def run_confirm(order, replies):
    """replies: list of customer texts in order. Returns (outcome, transcript)."""
    transcript = [("OUT", confirm_message(order))]
    unclear = 0
    for reply in replies:
        transcript.append(("IN", reply))
        if _is_yes(reply):
            return "SHIPPED (confirmed)", transcript + [("OUT", "Dhanyavaad! Aapka order dispatch ho raha hai.")]
        if _is_no(reply):
            return "CANCELLED (customer declined)", transcript + [("OUT", "Theek hai, order cancel kar diya gaya hai. Koi charge nahi lagega.")]
        unclear += 1
        if unclear == 1:
            transcript.append(("OUT", clarifying_message()))
        else:
            return "MANUAL HOLD (unclear replies)", transcript + [
                ("OUT", "Aapka order manual review ke liye hold par rakha gaya hai. Hamari team aapse sampark karegi.")]
    transcript.append(("OUT", f"[{REMINDER_HOURS}h reminder] " + reminder_message()))
    transcript.append(("OUT", f"[{EXPIRY_HOURS}h] No reply — order held, not shipped."))
    return "HELD (no reply in 24h)", transcript


def run_nudge(order, replies):
    """Nudge flow; declining the discount falls back to confirmation."""
    transcript = [("OUT", nudge_message(order))]
    for reply in replies:
        transcript.append(("IN", reply))
        if _is_yes(reply):
            transcript.append(("OUT", "Payment link: https://pay.mock/oytra/demo (mock — no real payment)."))
            transcript.append(("IN", "[customer pays online — mock]"))
            return "SHIPPED (prepaid, discount applied)", transcript
        if _is_no(reply):
            transcript.append(("OUT", "Theek hai, COD hi rakhte hain — bas ek confirmation chahiye."))
            outcome, sub = run_confirm(order, replies[replies.index(reply) + 1:])
            return f"Discount declined -> confirmation flow -> {outcome}", transcript + sub
        transcript.append(("OUT", clarifying_message()))
        break
    transcript.append(("OUT", f"[{EXPIRY_HOURS}h] No reply — order held, not shipped."))
    return "HELD (no reply in 24h)", transcript


def demo():
    order = {"order_id": "KT-DEMO-1", "customer_name": "Priya",
             "items": "Hair Oil 100ml", "order_value": 649}
    scenarios = [
        ("Confirm, customer says YES", run_confirm, ["yes"]),
        ("Confirm, customer says NO", run_confirm, ["no"]),
        ("Confirm, random reply then YES", run_confirm, ["hello??", "yes"]),
        ("Confirm, no reply at all", run_confirm, []),
        ("Nudge, customer accepts discount", run_nudge, ["yes"]),
        ("Nudge, customer declines discount then confirms COD", run_nudge, ["no", "yes"]),
    ]
    for title, fn, replies in scenarios:
        outcome, transcript = fn(order, replies)
        print(f"\n=== {title} => {outcome} ===")
        for who, text in transcript:
            print(f"  {who}: {text}")


def interactive():
    order = {"order_id": "KT-LIVE-1", "customer_name": "Customer",
             "items": "Hair Oil 100ml", "order_value": 649}
    print("Choose a flow: (1) Ship after confirmation  (2) Nudge to prepaid")
    flow = input("> ").strip()
    fn = run_confirm if flow != "2" else run_nudge
    print("Type customer replies one per line. Empty line = no further replies (24h passes).")
    replies = []
    while True:
        line = input("customer> ")
        if not line.strip():
            break
        replies.append(line)
    outcome, transcript = fn(order, replies)
    print(f"\nOutcome: {outcome}")
    for who, text in transcript:
        print(f"  {who}: {text}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Oytra WhatsApp flow mock")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--interactive", action="store_true")
    args = ap.parse_args(argv)
    if args.interactive:
        interactive()
    else:
        demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
