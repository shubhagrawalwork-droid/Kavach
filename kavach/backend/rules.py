"""Instant rule engine: catches well-known Indian scam phrases in Hindi
(Devanagari or Roman), Hinglish and English. Runs in microseconds, works offline.
"""

import re
from dataclasses import dataclass, field

# Strong phrases: on their own they mean danger (one strong match is enough for red).
STRONG = {
    "digital_arrest": [
        "digital arrest", "डिजिटल अरेस्ट", "arrest warrant", "अरेस्ट वारंट", "गिरफ्तार", "giraftar",
        "arrest kar", "अरेस्ट कर", "money laundering", "मनी लॉन्ड्रिंग",
    ],
    "otp_or_upi_pin": [
        "otp batao", "otp bataiye", "otp bata do", "otp share", "share the otp", "tell me the otp",
        "ओटीपी बताओ", "ओटीपी बताइए", "ओटीपी बता", "otp बताओ", "otp बताइए", "otp बता",
        r"\botp\b.{0,25}(बता|bata|share|bol|बोल|de do|दे दो)", r"(बताइए|bataiye|batao|बताओ).{0,15}\botp\b",
        "upi pin", "यूपीआई पिन", "upi पिन", "pin batao", "पिन बताओ", "pin बताओ", "cvv",
    ],
    "remote_access_app": [
        "anydesk", "any desk", "एनीडेस्क", "teamviewer", "team viewer", "quick support",
        "screen share", "स्क्रीन शेयर", "screen शेयर",
    ],
    "secrecy": [
        "kisi ko mat", "kisi ko na", "kisi ko nahi batana", "किसी को मत", "किसी को ना", "किसी को नहीं बताना",
        "don't tell anyone", "do not tell anyone", "dont tell anyone",
    ],
}

# Medium signals: each distinct kind adds suspicion; several together mean danger.
MEDIUM = {
    "impersonation": [
        r"\bcbi\b", "सीबीआई", r"\bpolice\b", "पुलिस", r"\bcustoms?\b", "कस्टम", r"\brbi\b", "आरबीआई",
        r"\btrai\b", "ट्राई", r"\bncb\b", "narcotics", "नारकोटिक्स", "income tax", "इनकम टैक्स",
        "cyber cell", "साइबर सेल", "crime branch", "क्राइम ब्रांच", r"\binspector\b", "इंस्पेक्टर",
        "enforcement directorate", r"\bjudge\b", "जज", "supreme court", "सुप्रीम कोर्ट",
    ],
    "threat": [
        r"\barrest\b", "अरेस्ट", r"\bjail\b", "जेल", r"\bwarrant\b", "वारंट", r"\bfir\b", "एफआईआर",
        "case darj", "केस दर्ज", "band ho jayega", "बंद हो जाएगा", "बंद कर दिया जाएगा", "kaat di jayegi",
        "काट दी जाएगी", "block ho jayega", "ब्लॉक हो जाएगा", "block kar", "ब्लॉक कर", "suspend",
    ],
    "money": [
        r"\btransfer\b", "ट्रांसफर", "paise bhej", "पैसे भेज", "safe account", "सेफ अकाउंट",
        "verification account", "processing fee", "प्रोसेसिंग फीस", r"\bfee\b", "फीस", "refund", "रिफंड",
        "payment kar", "पेमेंट कर", "payment ki", "पेमेंट की", "jama kar", "जमा कर", "jama ki", "जमा की",
        "penalty", "जुर्माना",
    ],
    "pressure": [
        "jaldi", "जल्दी", "turant", "तुरंत", "abhi ke abhi", "अभी के अभी", "immediately", "aaj hi", "आज ही",
        "2 ghante", "दो घंटे", "2 घंटे", "call mat kaat", "कॉल मत काट", "phone mat kaat", "फ़ोन मत काट",
        "फोन मत काट", "video call", "वीडियो कॉल",
    ],
    "parcel_drugs": [r"\bparcel\b", "पार्सल", r"\bdrugs?\b", "ड्रग्स", r"\bcourier\b", "कूरियर", "fedex"],
    "kyc": [r"\bkyc\b", "केवाईसी", "account block", "अकाउंट ब्लॉक", "update nahi", "अपडेट नहीं"],
    "electricity": ["bijli", "बिजली", "electricity", "light kaat", "लाइट काट", "meter", "मीटर"],
    "lottery": ["lottery", "लॉटरी", "inaam", "इनाम", "jeete hain", "जीते हैं", r"\bkbc\b", "prize"],
    "secrecy_soft": ["ko mat batana", "को मत बताना", "को मत बताइए", "ko mat bataiye", "confidential"],
    "family_emergency": ["accident", "एक्सीडेंट", "hospital mein", "हॉस्पिटल में", "thane mein", "थाने में"],
}

TYPE_FROM_MEDIUM = {
    "parcel_drugs": "digital_arrest",
    "impersonation": "digital_arrest",
    "kyc": "bank_kyc",
    "electricity": "electricity_bill",
    "lottery": "lottery_prize",
    "family_emergency": "family_emergency",
}

STRONG_SCORE = 85
MEDIUM_STEP = 20


def _compile(patterns):
    # entries that look like regex (contain \b or a group) are used as-is, the rest are literal phrases
    return [re.compile(p if ("\\b" in p or "(" in p) else re.escape(p), re.IGNORECASE) for p in patterns]


_STRONG_RE = {k: _compile(v) for k, v in STRONG.items()}
_MEDIUM_RE = {k: _compile(v) for k, v in MEDIUM.items()}


@dataclass
class RuleResult:
    score: int = 0
    strong: bool = False
    scam_type: str = "none"
    flags: list = field(default_factory=list)  # exact phrases heard
    kinds: list = field(default_factory=list)  # which signal kinds matched


def _find(regexes, text):
    hits = []
    for rx in regexes:
        m = rx.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def evaluate(text: str) -> RuleResult:
    text = " ".join(text.split())
    result = RuleResult()

    strong_kinds = []
    for kind, regexes in _STRONG_RE.items():
        hits = _find(regexes, text)
        if hits:
            strong_kinds.append(kind)
            result.flags.extend(hits)

    medium_kinds = []
    for kind, regexes in _MEDIUM_RE.items():
        hits = _find(regexes, text)
        if hits:
            medium_kinds.append(kind)
            result.flags.extend(hits)

    result.kinds = strong_kinds + medium_kinds
    medium_score = min(80, MEDIUM_STEP * len(medium_kinds))
    # a threat plus a demand for money plus anything else is the classic scam shape
    if "threat" in medium_kinds and "money" in medium_kinds and len(medium_kinds) >= 3:
        medium_score = max(medium_score, 70)
    if strong_kinds:
        result.strong = True
        result.score = min(100, STRONG_SCORE + 5 * (len(strong_kinds) - 1) + (5 if medium_kinds else 0))
    else:
        result.score = medium_score

    # best guess at the scam type
    for kind in ("otp_or_upi_pin", "remote_access_app", "digital_arrest"):
        if kind in strong_kinds:
            result.scam_type = kind
            break
    else:
        for kind in ("parcel_drugs", "impersonation", "kyc", "electricity", "lottery", "family_emergency"):
            if kind in medium_kinds:
                result.scam_type = TYPE_FROM_MEDIUM[kind]
                break
        else:
            if "secrecy" in strong_kinds:
                result.scam_type = "digital_arrest"

    # de-duplicate flags, keep order
    seen = set()
    result.flags = [f for f in result.flags if not (f.lower() in seen or seen.add(f.lower()))]
    return result
