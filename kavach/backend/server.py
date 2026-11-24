"""Kavach backend.

Browser mic -> WebSocket /ws/listen -> Sarvam Saaras streaming STT -> Guardian (rules + LLM)
-> live risk, spoken Hindi warnings (Bulbul), WhatsApp family alert, after-call complaint.

Modes for /ws/listen:
  guard     (default) live call protection
  describe  only transcribes (the elder describing what happened after a scam)
  demo      no microphone: the browser sends scripted lines as JSON, same brain
"""

import asyncio
import base64
import io
import logging
import os
import wave
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sarvamai import AsyncSarvamAI

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
load_dotenv(ROOT / ".env")

from . import alerts, complaint, demo_scripts, voice  # noqa: E402  (after .env is loaded)
from .guardian import Guardian  # noqa: E402

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
LANGUAGE = os.getenv("KAVACH_LANGUAGE", "hi-IN").strip() or "hi-IN"
SAMPLE_RATE = 16000  # the browser sends 16 kHz, 16-bit mono PCM

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("kavach")


def make_client():
    return AsyncSarvamAI(api_subscription_key=SARVAM_API_KEY) if SARVAM_API_KEY else None


@asynccontextmanager
async def lifespan(_app):
    client = make_client()
    task = asyncio.create_task(voice.warm_up(client)) if client else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Kavach", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
async def health():
    return {
        "ok": True,
        "sarvam_key_loaded": bool(SARVAM_API_KEY),
        "whatsapp_ready": alerts.configured(),
        "language": LANGUAGE,
    }


@app.get("/api/demo-scripts")
async def get_demo_scripts():
    return [{"id": k, "title": v["title"], "lines": v["lines"]} for k, v in demo_scripts.SCRIPTS.items()]


class ComplaintIn(BaseModel):
    lines: list[str] = []
    description: str = ""


@app.post("/api/complaint")
async def make_complaint(body: ComplaintIn):
    text = await complaint.draft(make_client(), body.lines, body.description)
    return {"text": text}


def pcm_to_wav_b64(pcm: bytes) -> str:
    """Wrap raw 16-bit mono PCM in a WAV header and base64-encode it for Sarvam."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def run_demo(ws: WebSocket, guardian: Guardian):
    await ws.send_json({"type": "status", "message": "listening"})
    await guardian.intro()
    while True:
        msg = await ws.receive_json()
        if msg.get("type") == "line":
            text = str(msg.get("text", ""))[:500]
            await ws.send_json({"type": "transcript", "text": text})
            await guardian.add_line(text)
        elif msg.get("type") == "end":
            break
    await guardian.finish()


async def run_live(ws: WebSocket, client, guardian: Guardian | None):
    stop = asyncio.Event()
    async with client.speech_to_text_streaming.connect(
        model="saaras:v4",
        mode="codemix",  # Hindi in Devanagari, English words in English
        language_code=LANGUAGE,
        high_vad_sensitivity="true",
    ) as stt:
        log.info("Connected to Sarvam (%s)", LANGUAGE)
        await ws.send_json({"type": "status", "message": "listening"})
        if guardian:
            await guardian.intro()

        async def browser_to_sarvam():
            while not stop.is_set():
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes"):
                    await stt.transcribe(audio=pcm_to_wav_b64(msg["bytes"]), encoding="audio/wav",
                                         sample_rate=SAMPLE_RATE)
                elif msg.get("text") == "stop":
                    await stt.flush()
                    await asyncio.sleep(1.5)  # give Sarvam time to send the last words
                    break
            stop.set()

        async def sarvam_to_browser():
            async for m in stt:
                if stop.is_set():
                    break
                data = getattr(m, "data", None)
                if m.type == "data":
                    text = (getattr(data, "transcript", "") or "").strip()
                    if text:
                        log.info("Heard: %s", text)
                        await ws.send_json({"type": "transcript", "text": text,
                                            "language": getattr(data, "language_code", None)})
                        if guardian:
                            await guardian.add_line(text)
                elif m.type == "error":
                    log.error("Sarvam error: %s", data)
                    await ws.send_json({"type": "error", "message": f"Sarvam error: {data}"})

        tasks = [asyncio.create_task(browser_to_sarvam()), asyncio.create_task(sarvam_to_browser())]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        stop.set()
        for t in tasks:
            t.cancel()
    if guardian:
        await guardian.finish()


@app.websocket("/ws/listen")
async def listen(ws: WebSocket):
    await ws.accept()
    mode = ws.query_params.get("mode", "guard")
    client = make_client()

    async def send(payload):
        await ws.send_json(payload)

    try:
        if mode == "demo":
            await run_demo(ws, Guardian(client, send))
        elif client is None:
            await ws.send_json({"type": "error",
                                "message": "SARVAM_API_KEY nahi mili. .env file mein apni Sarvam key daaliye."})
        else:
            await run_live(ws, client, Guardian(client, send) if mode == "guard" else None)
    except Exception as exc:  # bad key, no internet, browser closed...
        log.warning("Session ended with: %r", exc)
        try:
            await ws.send_json({"type": "error", "message": f"Connection problem: {exc}"})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
        log.info("Session ended (%s)", mode)
