# Space Apps submission: copy and paste

Ready-to-paste text for each field of the project form.

---

## Project Name
Healthy Astronauts

## Summary *(about 180 words, under 1500 characters)*
Healthy Astronauts is our project, and Aboard is its app: an offline health monitor that helps astronauts on long missions judge their own health. Earth may be minutes away by radio, so the crew needs a quick, trustworthy answer: how am I compared with my baseline, and what should I do next? Astronauts log readings their own way. They can type a sentence ("heart beat is 68, slept 6 hours"), photograph a device screen, or answer a six-question wellbeing check. A local AI model fills in the numbers. Every reading is compared with NASA data: Apollo AP005 preflight heart rate and blood pressure, Apollo AP004 serum labs, and NASA Standard Measures sleep. Measurements without a NASA range use a clearly labelled simulated preflight baseline. Transparent rules then give green, yellow or red with concrete next steps, such as repeating one measurement, a vision check for possible SANS, or contacting the crew medical officer. A glowing body map, readings-versus-baseline bars, a mood sticker and 60-day trends make the status clear at a glance. The Windows desktop app runs offline, including its local AI, and a website version lets anyone try it in a browser.

## Project Demonstration *(link)*
https://github.com/MohammadPourshahabadi/NasaHackaton/blob/main/presentation/Aboard-Demo.pdf
*(7 slides, including the title. GitHub shows the PDF without a login.)*

## Project *(link)*
https://34-88-27-31.sslip.io
*(If the website isn't live in time, use the GitHub repository instead: https://github.com/MohammadPourshahabadi/NasaHackaton)*

## Project Details
**What it does.** Aboard turns a daily health check-in into a clear decision for astronauts who cannot wait for Earth. It covers the indicators named in the challenge: blood pressure, heart rate, blood glucose (serum), sleep and mood. It also covers two spaceflight-specific measures: calf muscle ultrasound for muscle loss, and optic nerve OCT for spaceflight-associated neuro-ocular syndrome (SANS).

**How it works.**
1. *Log it your way.* Type a sentence or photograph a device screen. Speech input is experimental. A local language model (Llama 3.2 3B via Ollama) extracts readings and the body area. Photos are read by on-device OCR. A number is accepted only if it appears in the astronaut's words or on the screen, so the model cannot add readings that were never given.
2. *Compare with a baseline.* Heart rate and blood pressure use Apollo AP005 preflight values. Serum sodium, potassium, creatinine and glucose use Apollo AP004 (verified against the NASA workbook). Sleep uses NASA Standard Measures. Where NASA has no published range (calf ultrasound and OCT), Aboard uses a clearly labelled simulated preflight baseline. Each tile shows a NASA or SIM badge and a range bar.
3. *Act on it.* Transparent rules decide green, yellow or red and list the next steps. A flagged reading opens a guided repeat that asks only for that measurement. Vision symptoms trigger a SANS eye check. "I need help now" raises a crew alert with an Earth handoff. The AI explains the result in plain language and answers questions like "Is my blood pressure normal compared with NASA data?", but it never changes a status.

**Benefits.** Fast, explainable self-assessment that works offline and keeps data on the device, with NASA context for each reading where NASA data exists. It also tracks behavioural health through a daily questionnaire turned into a friendly mood sticker.

**Tools.** Python, Tkinter and Pillow (desktop app, packaged as a Windows EXE); a standard-library Python web server, HTML, CSS and JavaScript (website); Ollama with Llama 3.2 3B (and Gemma 3 4B as a fallback); Windows OCR and Tesseract.js for photos; whisper.cpp for offline speech; SQLite; Caddy and Google Cloud for hosting.

**What makes it creative.** It uses NASA historical data as a living baseline, AI that is boxed in by rules and by "no invented numbers" checks, a body map that glows by system, and a mood sticker that makes daily mental-health check-ins feel human.

## Use of Super Intelligence (SI) *(tick the matching options; the text below is for your reference)*
Tick every option that matches: **code**, **images/animation**, **data**, **text / presentation**, and **LLM inside the product** if the form lists it.
- **Code:** written with **OpenAI Codex** and **Anthropic Claude Code** from our instructions, then reviewed and tested by the team.
- **Illustrations and animations:** made with **OpenAI Codex**. Every one carries a visible **SI-generated** watermark in the app, on the website and in the deck.
- **Simulated data:** demo crew histories and simulated preflight baselines generated with **Anthropic Claude**, as random values inside normal human ranges around the NASA AP004/AP005 means. No real astronaut records are used.
- **Presentation:** the 7-slide deck was made with **Anthropic Claude**.
- **In the product:** a local LLM (Llama 3.2 3B, Gemma 3 4B fallback) reads entries, explains results and answers questions. It is labelled "Local AI" and never sets a status.
- No NASA logos or branding are used in any generated content. Full declaration: https://github.com/MohammadPourshahabadi/NasaHackaton/blob/main/docs/AI-DECLARATION.md

## NASA Data *(Link Text → Link Url)*
| Link Text | Link Url |
| --- | --- |
| Apollo AP004 Clinical Biochemistry | https://ntrs.nasa.gov/citations/19760005589 |
| Apollo AP005 Cardiovascular Evaluations | https://ntrs.nasa.gov/citations/19760005591 |
| NASA Standard Measures: Astronaut Sleep Duration | https://ntrs.nasa.gov/citations/20230003916 |
| NASA Fluid Shifts: Optic Nerve and Retinal Morphology | https://ntrs.nasa.gov/citations/20220007226 |
| NASA Spaceflight Standard Measures | https://www.nasa.gov/humans-in-space/spaceflight-standard-measures-characterizing-how-humans-adapt-in-space/ |
| NASA Behavioral Health Standardized Measures | https://taskbook.nasaprs.com/tbp/index.cfm?action=taskbook_content&uid=0537B5A7B98A78002A73E5ECA86E55B1 |
| NASA Human Research Program: SANS risk | https://humanresearchroadmap.nasa.gov/risks/risk.aspx?i=105 |
| NASA Life Sciences Data Archive (AP004 workbook) | https://nlsp.nasa.gov/ |

## Space Agency Partner & Other Data *(Link Text → Link Url)*
| Link Text | Link Url |
| --- | --- |
| ISS Tele-SUS teleguided ultrasound study (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC8047175/ |
| American Heart Association: home blood pressure monitoring | https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/monitoring-your-blood-pressure-at-home |
| Ollama (local AI runtime) | https://ollama.com |
| Meta Llama 3.2 3B model | https://ollama.com/library/llama3.2 |
| Google Gemma 3 4B model | https://ollama.com/library/gemma3 |
| Tesseract.js (browser OCR) | https://github.com/naptha/tesseract.js |
| whisper.cpp (offline speech) | https://github.com/ggerganov/whisper.cpp |
| Pillow (Python imaging) | https://python-pillow.org |
| Caddy web server | https://caddyserver.com |
| Aboard source code | https://github.com/MohammadPourshahabadi/NasaHackaton |
| AI declaration and full source list | https://github.com/MohammadPourshahabadi/NasaHackaton/blob/main/docs/AI-DECLARATION.md |
| OpenAI Codex (code, illustrations and animations) | https://openai.com/codex |
| Anthropic Claude and Claude Code (code, simulated data, presentation) | https://www.anthropic.com/claude |
