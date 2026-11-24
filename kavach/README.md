# Kavach

A voice guardian that protects elderly Indians from scam calls (digital arrest, fake CBI/police/bank/KYC).
It listens to the call on speaker, warns aloud in Hindi, alerts the family on WhatsApp, and helps file a complaint with 1930.
Product spec: `SPEC.md`.

## Run it on Windows
1. Double-click `setup.bat` (first time only).
2. Open `.env` in Notepad, paste your Sarvam key after `SARVAM_API_KEY=`, save.
3. Optional: run `.venv\Scripts\python sarvam_hello.py` to check the key works.
4. Double-click `run.bat`. The browser opens http://localhost:8000.
5. Press **KAVACH**, allow the mic, and put the call on speaker next to the laptop.
   No call handy? Open **Demo mode** at the bottom and pick a scripted scam.

## What it does
- **Live listening**: browser mic -> Sarvam Saaras v4 streaming STT (Hindi/Hinglish codemix).
- **Scam brain** (`backend/rules.py`, `backend/brain.py`): instant rule engine (Devanagari, Roman Hindi, English)
  plus Sarvam LLM reading the whole conversation, fused into green / yellow / red.
  Red needs a strong signal (OTP, UPI PIN, AnyDesk, digital arrest, secrecy) or a confident LLM backed by rules.
- **Voice** (`backend/voice.py`): Hindi warnings made once with Sarvam Bulbul v3 and cached, so they play instantly.
  Falls back to the browser's Hindi voice. 30 second cooldown so it doesn't nag.
- **Family alert** (`backend/alerts.py`): WhatsApp via Twilio on the first red. Without Twilio keys it shows the demo message.
- **After the call**: "Kya aapne paise bheje?" -> 1930 call button, the elder describes what happened (voice or text),
  Kavach drafts a cybercrime.gov.in complaint. Nothing is submitted automatically.
- **Privacy**: audio is never stored; only the text of the current call lives in memory.

## Evals
```
.venv\Scripts\python -m evals.run_evals        # rules only, free
.venv\Scripts\python -m evals.run_evals --llm  # rules + Sarvam LLM
```
30 cases (20 scams, 10 normal calls). Rules only today: 95% of scams reach red, 100% get at least a warning,
0 false alarms on normal calls, red after about 2.6 lines on average.

## WhatsApp setup (optional)
Create a free Twilio account, open Messaging > Try it out > WhatsApp sandbox, send the join code from the family phone,
then fill `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and `FAMILY_WHATSAPP_TO` in `.env`.
