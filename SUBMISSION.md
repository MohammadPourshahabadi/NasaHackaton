# Space Apps submission: copy and paste

Ready-to-paste text for each field of the project form. Fill in the two links marked **TODO** once the website is live.

---

## Project Name
Aboard: Crew Health, Checked On Board

## Summary *(about 180 words, under 1500 characters)*
Aboard is an offline health monitor that helps astronauts on long missions judge their own health. Earth may be minutes away by radio, so the crew needs a quick, trustworthy answer: how am I compared with my baseline, and what should I do next? Astronauts log readings their own way. They can type a sentence ("heart beat is 68, slept 6 hours"), photograph a device screen, or answer a six-question wellbeing check. A local AI model fills in the numbers. Every reading is compared with NASA data: Apollo AP005 preflight heart rate and blood pressure, Apollo AP004 serum labs, and NASA Standard Measures sleep. Measurements without a NASA range use a clearly labelled simulated preflight baseline. Transparent rules then give green, yellow or red with concrete next steps, such as repeating one measurement, a vision check for possible SANS, or contacting the crew medical officer. A glowing body map, readings-versus-baseline bars, a mood sticker and 60-day trends make the status clear at a glance. Everything, including the AI, runs offline on the spacecraft computer, with a Windows app and a website version.

## Project Demonstration *(link)*
https://github.com/MohammadPourshahabadi/NasaHackaton/blob/main/presentation/Aboard-Demo.pdf
*(7 slides, including the title. GitHub shows the PDF without a login.)*

## Project *(link)*
**TODO: your website, e.g. https://yourdomain.com**
*(If the website isn't live in time, use the GitHub repository instead: https://github.com/MohammadPourshahabadi/NasaHackaton)*

## Project Details
**What it does.** Aboard turns a daily health check-in into a clear decision for astronauts who cannot wait for Earth. It covers the indicators named in the challenge: blood pressure, heart rate, blood glucose (serum), sleep and mood. It also covers two spaceflight-specific measures: calf muscle ultrasound for muscle loss, and optic nerve OCT for spaceflight-associated neuro-ocular syndrome (SANS).

**How it works.**
1. *Log it your way.* Type, speak or photograph a device screen. A local language model (Llama 3.2 3B via Ollama) extracts readings and the body area. Photos are read by on-device OCR. A number is accepted only if it appears in the astronaut's words or on the screen, so the model cannot invent values.
2. *Compare with a baseline.* Heart rate and blood pressure use Apollo AP005 preflight values. Serum sodium, potassium, creatinine and glucose use Apollo AP004 (verified against the NASA workbook). Sleep uses NASA Standard Measures. Where NASA has no published range (calf ultrasound and OCT), Aboard uses a clearly labelled simulated preflight baseline. Each tile shows a NASA or SIM badge and a range bar.
3. *Act on it.* Transparent rules decide green, yellow or red and list the next steps. A flagged reading opens a guided repeat that asks only for that measurement. Vision symptoms trigger a SANS eye check. "I need help now" raises a crew alert with an Earth handoff. The AI explains the result in plain language and answers questions like "Is my blood pressure normal compared with NASA data?", but it never changes a status.

**Benefits.** Fast, explainable self-assessment that works offline and keeps data on board, with NASA context for every number. It also tracks behavioural health through a daily questionnaire turned into a friendly mood sticker.

**Tools.** Python, Tkinter and Pillow (desktop app, packaged as a Windows EXE); a standard-library Python web server, HTML, CSS and JavaScript (website); Ollama with Llama 3.2 3B (and Gemma 3 4B as a fallback); Windows OCR and Tesseract.js for photos; whisper.cpp for offline speech; SQLite; Caddy and Google Cloud for hosting.

**What makes it creative.** It uses NASA historical data as a living baseline, AI that is boxed in by rules and by "no invented numbers" checks, a body map that glows by system, and a mood sticker that makes daily mental-health check-ins feel human.

## Use of Super Intelligence (SI) *(select options, then this is a note for you)*
Select: **images**, **text/LLM**, **code**.
- **Images:** the anatomy, character and equipment illustrations were made with an image-generation model. Every one carries a visible **SI-generated** watermark in the app and on the website.
- **Language models:** a local LLM (Llama 3.2 3B, plus Gemma 3 4B as a fallback) runs inside the product to read entries, explain results and answer questions. These outputs are labelled "Local AI" in the interface.
- **Code:** written with help from an AI coding assistant (Claude). This is disclosed in the README and in the header comments of the AI files.
- **Data:** demo crew histories are simulated, drawn from NASA AP004/AP005 and Standard Measures means and SDs. No real astronaut records are used. No NASA logos or branding are used in any generated content.

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
