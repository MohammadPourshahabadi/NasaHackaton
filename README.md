# Aboard: crew health, checked on board

**NASA Space Apps Challenge 2026 · [Create Health Monitoring Software for Astronauts on Space Missions](https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/)**

On a long mission, astronauts often have to notice health changes themselves. Earth may be minutes away by radio. Aboard turns a quick daily check-in into a clear answer: **how am I compared with my baseline, and what should I do next?**

- **Log it your way.** Type a sentence ("heart beat is 68, slept 6 hours"), photograph a device screen, or answer six wellbeing questions. A local AI model fills in the numbers for you.
- **Compare with NASA data.** Heart rate, blood pressure, serum labs and sleep are checked against NASA ranges from Apollo AP004, Apollo AP005 and NASA Standard Measures. Measurements without a NASA range use a clearly labelled simulated preflight baseline.
- **Know what to do.** Simple, visible rules give green, yellow or red with next steps: repeat a measurement, do a vision check for possible SANS, or call the crew medical officer. The AI explains in plain words but never changes the result.
- **Works offline.** Everything, including the AI, runs on the spacecraft's own computer. No cloud needed.

## What's in this repository

| Folder | What it is | Start here |
| --- | --- | --- |
| [`app/`](app/) | The **desktop app** for Windows, the full onboard experience | [app/README.md](app/README.md) |
| [`website/`](website/) | The **website version**, the same rules and local AI running on a server so anyone can try it in a browser | [website/README.md](website/README.md) |
| [`presentation/`](presentation/) | The 7-slide demo deck | [Aboard-Demo.pdf](presentation/Aboard-Demo.pdf) |
| [`docs/`](docs/) | NASA data sources, dataset inventory and the original NASA files we used | [docs/README.md](docs/README.md) |

## Try it in 2 minutes

- **In a browser:** open the live website (link on our Space Apps project page) and pick Mo, Parisa or Nayan.
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

- **Images:** the anatomy, character and equipment illustrations were made with an image-generation model. Each one carries a visible **SI-generated** watermark wherever it appears.
- **Language models:** a local language model (Llama 3.2 3B, plus Gemma 3 4B as a photo fallback, through [Ollama](https://ollama.com)) reads entries, explains results and answers questions.
- **Code:** written with help from an AI coding assistant (Claude). Files that contain AI features say so in their header comments.
- **Data:** the demo crew and their 60-day histories are **simulated**. Vital signs and labs are drawn from the NASA means and SDs above. No real astronaut records are used.

Aboard is a hackathon prototype, not a medical device.
