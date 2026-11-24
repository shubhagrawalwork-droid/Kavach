"""Kavach's voice: fixed Hindi lines, generated once with Sarvam Bulbul and cached,
so a warning plays instantly instead of waiting for speech generation."""

import asyncio
import logging

log = logging.getLogger("kavach.voice")

LINES = {
    "intro": "नमस्ते, मैं कवच हूँ। इस कॉल की सुरक्षा के लिए जुड़ी हूँ।",
    "yellow": "सावधान रहिए। किसी को OTP या पैसे मत दीजिए।",
    "red": "यह फ्रॉड है। पुलिस कभी फ़ोन पर अरेस्ट नहीं करती। फ़ोन काट दीजिए।",
    "red_otp_or_upi_pin": "रुकिए! OTP या UPI पिन किसी को मत बताइए। बैंक कभी नहीं पूछता। फ़ोन काट दीजिए।",
    "red_remote_access_app": "रुकिए! कोई ऐप डाउनलोड मत कीजिए, स्क्रीन शेयर मत कीजिए। यह फ्रॉड है। फ़ोन काट दीजिए।",
    "red_family_emergency": "रुकिए! पहले अपने परिवार वाले को सीधे उनके नंबर पर फ़ोन कीजिए। पैसे मत भेजिए।",
    "red_lottery_prize": "कोई इनाम पाने के लिए पैसे नहीं देने पड़ते। यह फ्रॉड है। फ़ोन काट दीजिए।",
    "red_electricity_bill": "बिजली विभाग ऐसे फ़ोन पर पैसे नहीं माँगता। यह फ्रॉड है। फ़ोन काट दीजिए।",
    "red_bank_kyc": "बैंक फ़ोन पर KYC या OTP नहीं माँगता। यह फ्रॉड है। फ़ोन काट दीजिए।",
    "after_call": "क्या आपने किसी को पैसे भेजे?",
    "money_sent": "घबराइए मत। तुरंत 1930 पर कॉल कीजिए। मैं आपकी शिकायत तैयार कर रही हूँ।",
    "safe": "बहुत अच्छा। आप सुरक्षित हैं।",
}

SPEAKER = "priya"
_cache: dict[str, str] = {}
_lock = asyncio.Lock()


def warning_key(level: str, scam_type: str) -> str:
    if level == "yellow":
        return "yellow"
    specific = f"red_{scam_type}"
    return specific if specific in LINES else "red"


async def get_audio(client, key: str) -> str | None:
    """Base64 WAV for a line, or None (the browser then speaks it with its own voice)."""
    if key in _cache:
        return _cache[key]
    if client is None or key not in LINES:
        return None
    async with _lock:
        if key in _cache:
            return _cache[key]
        try:
            resp = await client.text_to_speech.convert(
                text=LINES[key], language_code="hi-IN", speaker=SPEAKER, model="bulbul:v3", pace=0.95,
            )
            _cache[key] = resp.audios[0]
            return _cache[key]
        except Exception as exc:
            log.warning("Text-to-speech failed for %s: %s", key, exc)
            return None


async def warm_up(client):
    """Pre-generate every line at startup so warnings never wait."""
    for key in LINES:
        await get_audio(client, key)
    log.info("Voice ready: %d/%d lines cached", len(_cache), len(LINES))
