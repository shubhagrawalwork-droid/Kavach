// Kavach: big button -> mic -> server (Sarvam STT + scam brain) -> live risk, spoken warnings,
// family alert, and the after-call help flow.
const $ = (id) => document.getElementById(id);
const app = $("app");
const btn = $("kavachBtn");

let socket = null;
let audioCtx = null;
let micStream = null;
let workletNode = null;
let mode = "guard";
let callLines = [];
let audioQueue = Promise.resolve();

const LEVEL_TEXT = { green: "Sab theek hai", yellow: "Saavdhaan", red: "KHATRA: yeh fraud hai" };

function setState(state, statusText, subText) {
  app.dataset.state = state;
  $("status").textContent = statusText;
  if (subText) $("btnSub").textContent = subText;
  btn.setAttribute("aria-pressed", state === "listening" ? "true" : "false");
}

function showError(message) { $("error").textContent = message; $("error").hidden = false; }
function clearError() { $("error").hidden = true; $("error").textContent = ""; }

function addTranscriptLine(text) {
  const box = $("transcript");
  const placeholder = box.querySelector(".placeholder");
  if (placeholder) placeholder.remove();
  const p = document.createElement("p");
  p.textContent = text;
  box.appendChild(p);
  box.scrollTop = box.scrollHeight;
}

function resetCall() {
  callLines = [];
  $("transcript").innerHTML = '<p class="placeholder">Sun rahi hoon...</p>';
  ["alertCard", "afterCard", "speakCard", "helpBox", "complaintText", "complaintActions"].forEach((id) => ($(id).hidden = true));
  $("description").value = "";
  showRisk({ level: "green", score: 0, flags: [], scam_type_hindi: "" });
  $("riskCard").hidden = false;
}

function showRisk(r) {
  app.dataset.level = r.level;
  $("riskLabel").textContent = LEVEL_TEXT[r.level];
  $("riskScore").textContent = r.score;
  $("meterFill").style.width = `${Math.max(3, r.score)}%`;
  $("riskType").textContent = r.level === "green" ? "" : r.scam_type_hindi;
  $("flags").innerHTML = "";
  (r.flags || []).slice(0, 6).forEach((f) => {
    const s = document.createElement("span");
    s.className = "flag";
    s.textContent = f;
    $("flags").appendChild(s);
  });
}

// Play warnings one after another. Sarvam's Bulbul audio if we have it, else the browser's own Hindi voice.
function speak(msg) {
  $("speakText").textContent = msg.text;
  $("speakCard").hidden = false;
  audioQueue = audioQueue.then(() => new Promise((resolve) => {
    if (msg.audio) {
      const a = new Audio(`data:audio/wav;base64,${msg.audio}`);
      a.onended = resolve; a.onerror = resolve;
      a.play().catch(resolve);
    } else if ("speechSynthesis" in window) {
      const u = new SpeechSynthesisUtterance(msg.text);
      u.lang = "hi-IN"; u.rate = 0.95;
      u.onend = resolve; u.onerror = resolve;
      speechSynthesis.speak(u);
    } else resolve();
  }));
}

function handleMessage(event) {
  const msg = JSON.parse(event.data);
  if (msg.type === "status" && msg.message === "listening") {
    if (mode === "describe") setState("listening", "Boliye, main likh rahi hoon", "Ho gaya? Dabaiye");
    else setState("listening", "Kavach sun rahi hai", "Band karne ke liye dabaiye");
  } else if (msg.type === "transcript") {
    if (mode === "describe") {
      $("description").value = `${$("description").value} ${msg.text}`.trim();
    } else {
      callLines.push(msg.text);
      addTranscriptLine(msg.text);
    }
  } else if (msg.type === "risk") {
    showRisk(msg);
  } else if (msg.type === "speak") {
    speak(msg);
  } else if (msg.type === "alert") {
    $("alertTitle").textContent = msg.sent ? "✅ Parivaar ko WhatsApp bheja gaya"
      : msg.demo ? "Demo: parivaar ko yeh WhatsApp jaayega" : "WhatsApp nahi ja paaya";
    $("alertBody").textContent = msg.message + (msg.error ? `\n\n(${msg.error})` : "");
    $("alertCard").hidden = false;
  } else if (msg.type === "call_ended") {
    if (msg.peak !== "green") $("afterCard").hidden = false;
  } else if (msg.type === "error") {
    showError(msg.message);
  }
}

async function openSocket(wsMode) {
  mode = wsMode;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${location.host}/ws/listen?mode=${wsMode}`);
  socket.binaryType = "arraybuffer";
  socket.onmessage = handleMessage;
  socket.onclose = () => { if (app.dataset.state !== "idle") stopMic(); };
  const ok = await new Promise((resolve) => {
    socket.onopen = () => resolve(true);
    socket.onerror = () => resolve(false);
    setTimeout(() => resolve(socket.readyState === WebSocket.OPEN), 8000);
  });
  if (!ok) showError("Server se connection nahi ho paaya. Kya run.bat chal raha hai?");
  return ok;
}

async function startListening(wsMode = "guard") {
  clearError();
  setState("connecting", "Kavach jud rahi hai...", "Ruk jaiye");
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: false, noiseSuppression: true, autoGainControl: true },
    });
  } catch (err) {
    setState("idle", "Taiyaar hai", "Dabaiye aur call speaker pe rakhiye");
    showError("Microphone ki permission nahi mili. Address bar mein mic icon par click karke 'Allow' kijiye, phir dobara dabaiye.");
    return;
  }
  if (wsMode === "guard") resetCall();
  if (!(await openSocket(wsMode))) { stopMic(); return; }

  audioCtx = new AudioContext();
  await audioCtx.audioWorklet.addModule("/static/mic-worklet.js");
  const source = audioCtx.createMediaStreamSource(micStream);
  workletNode = new AudioWorkletNode(audioCtx, "mic-processor");
  workletNode.port.onmessage = (e) => {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(e.data);
  };
  source.connect(workletNode);
}

function stopMic() {
  if (workletNode) { workletNode.disconnect(); workletNode = null; }
  if (audioCtx) { audioCtx.close(); audioCtx = null; }
  if (micStream) { micStream.getTracks().forEach((t) => t.stop()); micStream = null; }
  setState("idle", "Taiyaar hai", "Dabaiye aur call speaker pe rakhiye");
}

function stopListening() {
  // Keep the socket open a few seconds so the last words and the after-call question arrive.
  if (socket && socket.readyState === WebSocket.OPEN) {
    try { socket.send("stop"); } catch (_) {}
    const s = socket;
    setTimeout(() => { try { s.close(); } catch (_) {} }, 8000);
  }
  stopMic();
}

btn.addEventListener("click", () => {
  if (app.dataset.state === "idle") startListening("guard");
  else stopListening();
});

// ----- after the call -----
$("sentNo").addEventListener("click", () => {
  speak({ text: "बहुत अच्छा। आप सुरक्षित हैं।" });
  $("afterCard").hidden = true;
});
$("sentYes").addEventListener("click", () => {
  speak({ text: "घबराइए मत। तुरंत 1930 पर कॉल कीजिए। मैं आपकी शिकायत तैयार कर रही हूँ।" });
  $("helpBox").hidden = false;
});
$("speakDesc").addEventListener("click", () => {
  if (app.dataset.state === "idle") startListening("describe");
  else stopListening();
});
$("makeComplaint").addEventListener("click", async () => {
  $("makeComplaint").disabled = true;
  $("makeComplaint").textContent = "Taiyaar ho rahi hai...";
  try {
    const r = await fetch("/api/complaint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lines: callLines, description: $("description").value }),
    });
    const data = await r.json();
    $("complaintText").textContent = data.text;
    $("complaintText").hidden = false;
    $("complaintActions").hidden = false;
  } catch (_) {
    showError("Shikayat taiyaar nahi ho paayi. Seedha 1930 par call kijiye.");
  }
  $("makeComplaint").disabled = false;
  $("makeComplaint").textContent = "Shikayat taiyaar kijiye";
});
$("copyComplaint").addEventListener("click", () => {
  navigator.clipboard.writeText($("complaintText").textContent).then(() => ($("copyComplaint").textContent = "Copy ho gaya ✓"));
});

// ----- demo mode: same brain, scripted call, no microphone -----
async function runDemo(script) {
  if (app.dataset.state !== "idle") return;
  clearError();
  resetCall();
  setState("connecting", "Demo shuru ho raha hai...", "Ruk jaiye");
  if (!(await openSocket("demo"))) { setState("idle", "Taiyaar hai"); return; }
  await new Promise((r) => setTimeout(r, 2500)); // let the intro play
  for (const line of script.lines) {
    socket.send(JSON.stringify({ type: "line", text: line }));
    await new Promise((r) => setTimeout(r, 3200));
  }
  socket.send(JSON.stringify({ type: "end" }));
  setState("idle", "Demo khatam", "Dabaiye aur call speaker pe rakhiye");
  const s = socket;
  setTimeout(() => { try { s.close(); } catch (_) {} }, 8000);
}

fetch("/api/demo-scripts").then((r) => r.json()).then((scripts) => {
  scripts.forEach((s) => {
    const b = document.createElement("button");
    b.className = "demo-btn";
    b.textContent = s.title;
    b.onclick = () => runDemo(s);
    $("demoButtons").appendChild(b);
  });
}).catch(() => {});

// Tell the user if the server can't see the Sarvam key.
fetch("/health").then((r) => r.json()).then((h) => {
  if (!h.sarvam_key_loaded) showError("Sarvam API key nahi mili. .env file mein SARVAM_API_KEY daaliye aur run.bat dobara chalaiye. (Demo mode phir bhi chalega.)");
}).catch(() => {});
