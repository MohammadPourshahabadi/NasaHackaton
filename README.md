# Healthy Astronauts: the Aboard crew health app

**Team SolutionFinders** (Mohammad Pourshahabadi, Parisa Aghaei, Kazi Rabiul Alam Nayan) · **NASA Space Apps Challenge 2026** · [Create Health Monitoring Software for Astronauts on Space Missions](https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/)

On a long mission, astronauts often have to notice health changes themselves. Earth may be minutes away by radio. Aboard turns a quick daily check-in into a clear answer: **how am I compared with my baseline, and what should I do next?**

- **Log it your way.** Type a sentence ("heart beat is 68, slept 6 hours"), photograph a device screen, or answer six wellbeing questions. A local AI model fills in the numbers for you.
- **Compare with NASA data.** Heart rate, blood pressure, serum labs and sleep are checked against NASA ranges from Apollo AP004, Apollo AP005 and NASA Standard Measures. Measurements without a NASA range use a clearly labelled simulated preflight baseline.
- **Know what to do.** Simple, visible rules give green, yellow or red with next steps: repeat a measurement, do a vision check for possible SANS, or call the crew medical officer. The AI explains in plain words but never changes the result.
- **Works offline.** The desktop app and its local AI run on a single computer, with no cloud service needed. The website version runs the same code on a server so judges can try it.

## What's in this repository

| Folder | What it is | Start here |
| --- | --- | --- |
| [`app/`](app/) | The **desktop app** for Windows, the full onboard experience | [app/README.md](app/README.md) |
| [`website/`](website/) | The **website version**, the same rules and local AI running on a server so anyone can try it in a browser | [website/README.md](website/README.md) |
| [`presentation/`](presentation/) | The 7-slide demo deck | [Aboard-Demo.pdf](presentation/Aboard-Demo.pdf) |
| [`docs/`](docs/) | NASA data sources, dataset inventory, the original NASA files we used, and our **AI declaration** | [docs/README.md](docs/README.md) · [AI-DECLARATION.md](docs/AI-DECLARATION.md) |

## Try it in 2 minutes

- **In a browser:** open **https://34-88-27-31.sslip.io** and pick Mo, Parisa or Nayan. AI answers take up to about 20–30 seconds because the model runs on a CPU server.
- **On Windows:** download [`app/release/Aboard.exe`](app/release/Aboard.exe) and double-click it. For the AI features, follow the 3 steps in [app/README.md](app/README.md#turn-on-the-local-ai-optional).

## NASA data we use

| NASA source | Used for |
| --- | --- |
| [Apollo AP004 Clinical Biochemistry](https://ntrs.nasa.gov/citations/19760005589) | Serum sodium, potassium, creatinine and glucose baselines (from the NASA workbook `JMAPAP004_127.xls`) |
| [Apollo AP005 Cardiovascular Evaluations](https://ntrs.nasa.gov/citations/19760005591) | Resting heart rate and blood pressure baselines |
| [NASA Standard Measures sleep study](https://ntrs.nasa.gov/citations/20230003916) | Sleep baseline |
| [ISS Tele-SUS](https://pmc.ncbi.nlm.nih.gov/articles/PMC8047175/) · [NASA Fluid Shifts](https://ntrs.nasa.gov/citations/20220007226) | Calf ultrasound and eye OCT measurement methods |
| [NASA Spaceflight Standard Measures](https://www.nasa.gov/humans-in-space/spaceflight-standard-measures-characterizing-how-humans-adapt-in-space/) | Topics of the daily wellbeing questions |

Details, file locations and what we verified are in [docs/README.md](docs/README.md).

## Use of Super Intelligence (SI)

| What | Tool | Marked how |
| --- | --- | --- |
| Code (app, website, scripts) | OpenAI **Codex** and Anthropic **Claude Code**, from our instructions. We reviewed and tested everything. | This section and [docs/AI-DECLARATION.md](docs/AI-DECLARATION.md) |
| Illustrations and animations (body map, characters, equipment, guide frames) | OpenAI **Codex** | Visible **SI-generated** watermark wherever they appear |
| Simulated data (demo crew histories, simulated preflight baselines) | Anthropic **Claude**: random values inside normal human ranges, around NASA means | Labelled **SIM** / simulated in the app |
| Presentation deck | Anthropic **Claude** | Slide 7 and the file properties |
| In-app assistant | Local **Llama 3.2 3B** (Gemma 3 4B fallback) through Ollama | Labelled "Local AI" in the app |

No NASA logos or branding appear in SI-generated content, and no real astronaut records are used. The full declaration and every source are in **[docs/AI-DECLARATION.md](docs/AI-DECLARATION.md)**.

Aboard is a hackathon prototype, not a medical device.
