"""Kavach's scam brain: the instant rule engine plus an LLM that reads the whole
conversation, fused into one green / yellow / red decision.
"""

import json
import logging
from dataclasses import dataclass, field

from . import rules

log = logging.getLogger("kavach.brain")

SCAM_TYPES = [
    "digital_arrest", "bank_kyc", "otp_or_upi_pin", "remote_access_app", "electricity_bill",
    "family_emergency", "lottery_prize", "investment", "none",
]

SCAM_TYPE_HINDI = {
    "digital_arrest": "डिजिटल अरेस्ट / नकली पुलिस",
    "bank_kyc": "नकली बैंक KYC",
    "otp_or_upi_pin": "OTP / UPI PIN माँगना",
    "remote_access_app": "स्क्रीन शेयर / ऐप डाउनलोड",
    "electricity_bill": "बिजली कटने की धमकी",
    "family_emergency": "नकली इमरजेंसी",
    "lottery_prize": "नकली इनाम / लॉटरी",
    "investment": "नकली निवेश",
    "none": "कोई खतरा नहीं",
}

LLM_SYSTEM_PROMPT = f"""You are Kavach, a scam detector protecting elderly people in India during live phone calls.
You get a transcript (Hindi, Hinglish or English, possibly with speech-to-text errors, speakers not labelled).
Decide how likely it is that the caller is running a scam on the elderly person.

Scam signs: pretending to be CBI, police, customs, RBI, TRAI, a bank or a court; "digital arrest"; threats of
arrest, jail or cutting a service; asking for OTP, UPI PIN, card or bank details; asking to install AnyDesk or
share the screen; asking to transfer money to a "safe" or "verification" account; demanding secrecy; urgency;
keeping the person on a video call; prizes that need a fee; fake family emergencies.
Normal family chats, doctor reminders and genuine service calls that ask for nothing are NOT scams.
If the transcript is short or unclear, give a lower score and confidence "low". Never invent facts.

Reply with ONLY a JSON object:
{{"risk_score": <integer 0-100>, "scam_type": <one of {SCAM_TYPES}>, "confidence": "low" | "medium" | "high",
"red_flags": [<exact short phrases from the transcript>], "reason": "<one short sentence in English>"}}"""


@dataclass
class LLMResult:
    score: int = 0
    scam_type: str = "none"
    confidence: str = "low"
    flags: list = field(default_factory=list)
    reason: str = ""


@dataclass
class Assessment:
    score: int
    level: str  # green | yellow | red
    scam_type: str
    flags: list
    reason: str
    source: str  # which detector drove the decision


def _level(score: int) -> str:
    if score >= 70:
        return "red"
    if score >= 40:
        return "yellow"
    return "green"


async def llm_score(client, transcript: str) -> LLMResult | None:
    """Ask Sarvam's LLM to judge the conversation. Returns None if it fails (rules still protect)."""
    if client is None or not transcript.strip():
        return None
    try:
        resp = await client.chat.completions(
            model="sarvam-105b-conversations",
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcript:\n{transcript}"},
            ],
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        scam_type = data.get("scam_type", "none")
        return LLMResult(
            score=max(0, min(100, int(data.get("risk_score", 0)))),
            scam_type=scam_type if scam_type in SCAM_TYPES else "none",
            confidence=str(data.get("confidence", "low")).lower(),
            flags=[str(f) for f in data.get("red_flags", [])][:6],
            reason=str(data.get("reason", ""))[:200],
        )
    except Exception as exc:  # timeout, bad JSON, no credits...
        log.warning("LLM check failed, using rules only: %s", exc)
        return None


def fuse(rule: rules.RuleResult, llm: LLMResult | None) -> Assessment:
    """Combine both detectors. Red needs a strong rule match, or a confident LLM plus some rule signal."""
    llm_score = 0
    if llm:
        llm_score = llm.score
        if llm.confidence == "low":
            llm_score = min(llm_score, 69)  # unsure -> never above yellow
        elif llm_score >= 70 and not rule.strong and rule.score < 20 and llm.confidence != "high":
            llm_score = 69  # red needs two signals

    if llm_score > rule.score:
        score, source = llm_score, "llm"
        scam_type = llm.scam_type if llm.scam_type != "none" else rule.scam_type
        reason = llm.reason
    else:
        score, source = rule.score, "rules"
        scam_type = rule.scam_type if rule.scam_type != "none" else (llm.scam_type if llm else "none")
        reason = "Scam phrases detected: " + ", ".join(rule.flags[:4]) if rule.flags else "No scam signs yet."

    flags = list(dict.fromkeys(rule.flags + (llm.flags if llm else [])))[:8]
    level = _level(score)
    if level == "green":
        scam_type = "none"
    return Assessment(score=score, level=level, scam_type=scam_type, flags=flags, reason=reason, source=source)
