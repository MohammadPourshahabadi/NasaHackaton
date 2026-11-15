# Healthy Astronauts: AI (SI) declaration and sources

**Project:** Healthy Astronauts (Windows desktop app `Aboard.exe` and website https://34-88-27-31.sslip.io)
**Team SolutionFinders:** Mohammad Pourshahabadi, Parisa Aghaei, Kazi Rabiul Alam Nayan
**Challenge:** NASA Space Apps Challenge 2026: *Create Health Monitoring Software for Astronauts on Space Missions*

The Space Apps rules allow Super Intelligence (SI) tools but ask teams to say clearly where and how they were used. This page is our full declaration. The idea, the choice of health indicators and NASA datasets, the design decisions and the testing were done by the team.

## Where SI tools were used

| What | SI tool | How it was used | How it is marked |
| --- | --- | --- | --- |
| **Code** (desktop app, website, build and deploy scripts) | **OpenAI Codex** and **Anthropic Claude Code** | Wrote and edited code from our instructions. We reviewed, ran and tested the results (smoke tests, rule checks, local AI tests). | This declaration, the README and header comments in the AI-related files |
| **Illustrations and animations** (anatomy body map, character activity animations, measurement-step and equipment pictures) | **OpenAI Codex** | Generated the images used for the body map and the animated guides | A visible **SI-generated** watermark on every one of these images, wherever it appears in the app or website (`app/ai_label.py`) |
| **Simulated data** (demo crew Mo, Parisa and Nayan, their 60-day histories, simulated preflight baselines for calf ultrasound and eye OCT) | **Anthropic Claude** | Generated random values inside normal human ranges. Vital signs and labs are drawn around NASA AP005 and AP004 means and SDs. | Labelled **SIM** / "simulated" in the app and in `docs/README.md`; header comment in `app/demo_journal.py` and `app/baseline.py` |
| **Presentation** (7-slide demo deck) | **Anthropic Claude** | Drafted and laid out the slides from our project and screenshots | This declaration, slide 7 and the PDF/PPTX file properties |
| **In-app assistant** (feature of the product) | **Llama 3.2 3B** (Meta), with **Gemma 3 4B** (Google) as a fallback, run locally with **Ollama** | Reads typed entries, explains results in plain language, answers health questions. It never sets the green, yellow or red status. Rules do that. | Labelled "Local AI" in the interface |

No NASA logos, flags or mission identifiers were generated or used in any SI-generated content. No real astronaut records are used. In-app messages that a flight surgeon or psychologist "has been notified" are simulated: nothing is sent.

## NASA data and resources

| Resource | How we use it |
| --- | --- |
| [Apollo AP004 Clinical Biochemistry](https://ntrs.nasa.gov/citations/19760005589) | Serum sodium, potassium, creatinine and glucose baselines (preflight mean ± 2 SD, n=33), taken from the NASA workbook `JMAPAP004_127.xls` (in `docs/nasa-data/`) |
| [Apollo AP005 Cardiovascular Evaluations](https://ntrs.nasa.gov/citations/19760005591) | Resting heart rate and blood pressure baselines (preflight supine control, n=24) |
| [NASA Standard Measures: Astronaut Sleep Duration](https://ntrs.nasa.gov/citations/20230003916) | Sleep baseline (7.33 h average in flight) |
| [ISS Tele-SUS teleguided ultrasound study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8047175/) | Calf muscle ultrasound measurement method |
| [NASA Fluid Shifts: Optic Nerve Head and Retinal Morphology](https://ntrs.nasa.gov/citations/20220007226) | Eye OCT (TRT250) measurement method and a flight-day-50 reference value |
| [NASA Spaceflight Standard Measures](https://www.nasa.gov/humans-in-space/spaceflight-standard-measures-characterizing-how-humans-adapt-in-space/) | Topics of the daily wellbeing questions |
| [NASA Behavioral Health standardized measures](https://taskbook.nasaprs.com/tbp/index.cfm?action=taskbook_content&uid=0537B5A7B98A78002A73E5ECA86E55B1) | Topics of the daily wellbeing questions |
| [NASA Human Research Program: SANS risk](https://humanresearchroadmap.nasa.gov/risks/risk.aspx?i=105) | Why a reported vision change triggers an eye check |

## Other data, tools and references

| Resource | How we use it |
| --- | --- |
| [American Heart Association: home blood pressure](https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/monitoring-your-blood-pressure-at-home) | Blood-pressure measurement guide and very-high-pressure follow-up |
| [Ollama](https://ollama.com), [Llama 3.2](https://ollama.com/library/llama3.2), [Gemma 3](https://ollama.com/library/gemma3) | Local AI runtime and models |
| [Tesseract.js](https://github.com/naptha/tesseract.js) and Windows OCR | Reading text from device-screen photos |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | Optional offline speech-to-text |
| [Python](https://www.python.org), Tkinter, [Pillow](https://python-pillow.org), SQLite | Desktop app |
| [Caddy](https://caddyserver.com), [Google Cloud Compute Engine](https://cloud.google.com/compute) | Website hosting and HTTPS |
| [Google Fonts: Inter](https://fonts.google.com/specimen/Inter) | Website font |

## What is real and what is simulated

- **Real NASA data:** baseline means and ranges for heart rate, blood pressure, serum labs and sleep (sources above).
- **Simulated (SI-generated with Claude):** the three demo crew members, all their readings and questionnaire answers, and the preflight baselines for calf ultrasound and eye OCT, where NASA published no range. The simulated eye and calf ranges are approximations chosen for the demo, not clinical norms.
- **Prototype:** the alert rules and thresholds are for the hackathon. Aboard is not a medical device.
