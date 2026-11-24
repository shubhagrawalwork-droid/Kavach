"""One Guardian per call. It takes transcript lines (live from Sarvam or from demo mode),
keeps the risk up to date, and decides when to warn aloud and when to alert the family."""

import asyncio
import time

from . import alerts, brain, rules, voice

WARNING_COOLDOWN_S = 30
LLM_EVERY_S = 3.0
WINDOW_LINES = 14  # how much recent conversation the detectors look at


class Guardian:
    def __init__(self, client, send):
        self.client = client  # AsyncSarvamAI or None
        self.send = send  # async callable(dict)
        self.lines: list[str] = []
        self.llm_result: brain.LLMResult | None = None
        self.llm_task: asyncio.Task | None = None
        self.llm_last = 0.0
        self.llm_seen = 0
        self.level = "green"
        self.peak = "green"
        self.last_warning = 0.0
        self.alert_sent = False
        self.started = time.time()
        self.first_red_at: float | None = None

    def window(self) -> str:
        return "\n".join(self.lines[-WINDOW_LINES:])

    async def intro(self):
        await self.speak("intro")

    async def speak(self, key: str):
        audio = await voice.get_audio(self.client, key)
        await self.send({"type": "speak", "key": key, "text": voice.LINES[key], "audio": audio})

    async def add_line(self, text: str):
        text = text.strip()
        if not text:
            return
        self.lines.append(text)
        await self.reassess()
        self._maybe_run_llm()

    def _maybe_run_llm(self):
        if self.client is None or (self.llm_task and not self.llm_task.done()):
            return
        if len(self.lines) == self.llm_seen or time.time() - self.llm_last < LLM_EVERY_S:
            return
        self.llm_last = time.time()
        self.llm_seen = len(self.lines)
        self.llm_task = asyncio.create_task(self._run_llm(self.window()))

    async def _run_llm(self, text: str):
        result = await brain.llm_score(self.client, text)
        if result is not None:
            self.llm_result = result
            await self.reassess()
        self._maybe_run_llm()  # catch lines that arrived meanwhile

    async def reassess(self):
        rule = rules.evaluate(self.window())
        a = brain.fuse(rule, self.llm_result)
        await self.send({
            "type": "risk", "score": a.score, "level": a.level, "scam_type": a.scam_type,
            "scam_type_hindi": brain.SCAM_TYPE_HINDI.get(a.scam_type, ""), "flags": a.flags,
            "reason": a.reason, "source": a.source,
        })
        rank = {"green": 0, "yellow": 1, "red": 2}
        escalated = rank[a.level] > rank[self.level]
        self.level = a.level
        if rank[a.level] > rank[self.peak]:
            self.peak = a.level
        if a.level == "red" and self.first_red_at is None:
            self.first_red_at = time.time()

        now = time.time()
        if a.level != "green" and (escalated or now - self.last_warning > WARNING_COOLDOWN_S):
            self.last_warning = now
            await self.speak(voice.warning_key(a.level, a.scam_type))

        if a.level == "red" and not self.alert_sent:
            self.alert_sent = True
            body = alerts.build_message(brain.SCAM_TYPE_HINDI.get(a.scam_type, a.scam_type), a.flags)
            result = await alerts.send_whatsapp(body)
            await self.send({"type": "alert", **result})

    async def finish(self):
        """Call ended. If anything looked risky, start the after-call check."""
        if self.llm_task and not self.llm_task.done():
            try:
                await asyncio.wait_for(self.llm_task, timeout=5)
            except Exception:
                pass
        await self.send({"type": "call_ended", "peak": self.peak})
        if self.peak != "green":
            await self.speak("after_call")
