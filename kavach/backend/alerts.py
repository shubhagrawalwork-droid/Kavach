"""Family alert over WhatsApp (Twilio). If Twilio isn't set up, Kavach shows a demo alert instead."""

import logging
import os

import httpx

log = logging.getLogger("kavach.alerts")


def configured() -> bool:
    return all(os.getenv(k, "").strip() for k in
               ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "FAMILY_WHATSAPP_TO"))


def build_message(scam_type_hindi: str, flags: list) -> str:
    elder = os.getenv("ELDER_NAME", "Papa").strip() or "Papa"
    heard = ", ".join(f'"{f}"' for f in flags[:3]) or "scam phrases"
    return (f"KAVACH ALERT: {elder} is on a suspected scam call right now.\n"
            f"Type: {scam_type_hindi}\nHeard: {heard}\nPlease call {elder} now.")


async def send_whatsapp(body: str) -> dict:
    if not configured():
        log.info("Twilio not configured, demo alert only")
        return {"sent": False, "demo": True, "message": body}
    sid = os.environ["TWILIO_ACCOUNT_SID"].strip()
    token = os.environ["TWILIO_AUTH_TOKEN"].strip()
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = {"From": os.environ["TWILIO_WHATSAPP_FROM"].strip(),
            "To": os.environ["FAMILY_WHATSAPP_TO"].strip(),
            "Body": body}
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.post(url, data=data, auth=(sid, token))
        if r.status_code in (200, 201):
            return {"sent": True, "demo": False, "message": body}
        log.warning("Twilio error %s: %s", r.status_code, r.text[:300])
        return {"sent": False, "demo": False, "message": body, "error": f"Twilio error {r.status_code}"}
    except Exception as exc:
        log.warning("WhatsApp alert failed: %s", exc)
        return {"sent": False, "demo": False, "message": body, "error": str(exc)}
