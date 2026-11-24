"""After a scam: turn the call transcript and the elder's own spoken account into a
complaint draft for cybercrime.gov.in / the 1930 helpline. Never submitted automatically."""

import datetime as dt
import logging

log = logging.getLogger("kavach.complaint")

PROMPT = """You help an elderly person in India who was just targeted by a phone scam.
Write a clear cyber crime complaint draft they (or their family) can use on cybercrime.gov.in or when calling 1930.
Use ONLY facts from the material below; write "not known" for anything missing. Do not invent amounts or numbers.

Format exactly:
COMPLAINT DRAFT
Date and time of call: ...
Caller number: ...
Who the caller claimed to be: ...
What the caller said (short): ...
Money sent: ... (amount, method, account/UPI ID if mentioned)
What happened, in the victim's words: ...
Request: Please block the fraud account and help recover the money.

Then one line in simple Hindi starting with "सारांश:" summarising what happened."""


async def draft(client, call_lines: list, description: str) -> str:
    now = dt.datetime.now().strftime("%d %b %Y, %I:%M %p")
    material = (f"Complaint written at: {now}\n\nCall transcript:\n" + "\n".join(call_lines[-40:]) +
                f"\n\nWhat the elder said after the call:\n{description or 'not given'}")
    if client is None:
        return _fallback(now, call_lines, description)
    try:
        resp = await client.chat.completions(
            model="sarvam-105b-conversations",
            messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": material}],
            temperature=0.2,
            max_tokens=700,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or _fallback(now, call_lines, description)
    except Exception as exc:
        log.warning("Complaint drafting failed: %s", exc)
        return _fallback(now, call_lines, description)


def _fallback(now: str, call_lines: list, description: str) -> str:
    said = " / ".join(call_lines[-6:]) or "not known"
    return ("COMPLAINT DRAFT\n"
            f"Date and time of call: {now}\n"
            "Caller number: not known\n"
            "Who the caller claimed to be: see call transcript\n"
            f"What the caller said (short): {said}\n"
            "Money sent: not known\n"
            f"What happened, in the victim's words: {description or 'not given'}\n"
            "Request: Please block the fraud account and help recover the money.\n"
            "सारांश: मेरे साथ फ़ोन पर धोखाधड़ी हुई है, कृपया मदद कीजिए।")
