# Kavach product spec (from Round 1, Activity 2)

Okay so, you're a senior engineer and you're building a working prototype of Kavach using an agentic coding tool like Claude Code. Kavach is basically a voice guardian that protects elderly people in India from scam calls like fake CBI and digital arrest calls. Voice is the product, not a dashboard. Plan it, build it, test it against the evals at the end, then tell me the results.

Users and languages.
The main users are elders, a lot of them living alone, and they struggle to read or type. They speak Hindi, Hinglish and English with pretty strong regional accents, with more Indian languages later. Scammers talk fast and keep mixing languages. The second user is the son or daughter, who sets up Kavach and gets the alerts.

The voice flow.
Step 1, setup. The son or daughter just speaks the parent's name, language and the family WhatsApp number. Kavach repeats it back and asks "Sahi hai?" A "haan" saves it and counts as consent.
Step 2, start. Kavach runs in a browser on a laptop or a spare phone next to the elder, showing one huge red "Kavach" button. On a suspicious call, they put the call on speaker and tap it, or just say "Kavach, suno".
Step 3, join. Kavach says "Main Kavach hoon, is call ki suraksha ke liye judi hoon." The screen goes green and shows "Kavach sun rahi hai."
Step 4, listen. Audio streams to speech to text, and two detectors run at the same time. One is an instant rule engine for really strong phrases like "OTP batao", "digital arrest" and "kisi ko mat batana". The other is Jev, TypeSafe's fast decision model, which reads the last 60 seconds every 3 seconds and answers typed questions: how likely it is a scam from 0 to 100, which type of scam from a fixed list, and how confident it is.
Step 5, respond. Below 40, Kavach stays quiet. From 40 to 69, the screen turns yellow and Kavach says "Savdhaan rahiye. Kisi ko OTP ya paise mat dijiye." At 70 or above, the screen goes red and Kavach says "Yeh fraud hai. Police kabhi phone pe arrest nahi karti. Phone kaat dijiye."
Step 6, alert. On red, it WhatsApps the family: "Papa is on a suspected digital arrest scam call. Please call him now."
Step 7, after the call. Kavach asks "Kya aapne paise bheje?" If they say yes, it says "Ghabraiye mat. Turant 1930 par call kijiye." It shows a big 1930 button, lets the elder just tell what happened, uses a language model to write a cyber crime complaint draft, reads it out loud and sends it to the family. It never submits anything on its own.

When things go wrong.
Noise: don't escalate because of one unclear word. Red needs two signals, or one strong rule match.
Accents and mixed languages: use the transcription confidence and the full context, match phrases in Devanagari, Roman Hindi and English, and always reply in the elder's language.
If it's unsure or two people talk at once: yellow only, and never call anyone a criminal.
False alarm: if the elder says "yeh sahi call hai", Kavach goes quiet and marks that number as safe.
If Jev times out or has low confidence: fall back to the rule engine and never go above yellow.

Architecture.
Next.js, TypeScript and Tailwind for the app. The audio runs through Pipecat, the open source voice pipeline, with Sarvam Saaras for speech to text, AI4Bharat's open source IndicConformer as the backup, Sarvam Bulbul for the voice and Twilio for WhatsApp. Model the session as a typed state machine: idle, listening, caution, danger and after call. Use Jev through the Vercel AI Gateway for every scam decision, because it gives typed answers and can't make stuff up. Use a language model only for the complaint, validated with Zod. Pre-generate the warning audio so it plays in under 2 seconds. Trace every decision in Langfuse and add a demo mode with fake calls.

Privacy and safety.
Never store audio. Keep transcripts only for the complaint and delete them after 7 days, as per India's DPDP Act. Never hang up a call, and never ask for money, OTPs, PINs or passwords.

Evals and done when.
Make an eval set of 30 recorded calls: 20 scams of different types, plus 10 normal calls, including Hinglish and noisy audio. Run it in CI and report detection rate, false alarms and time to warning. It's done when at least 18 out of 20 scams turn red within 10 seconds, none of the 10 normal calls turn red, and the whole voice flow works end to end on a phone browser.
