# Aboard

Aboard is an offline health monitor that helps astronauts check their own health on long missions. It was built for the NASA Space Apps 2026 challenge [Create Health Monitoring Software for Astronauts on Space Missions](https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/).

Every reading is compared with a baseline. Where NASA has published data, the baseline is the NASA value and range, marked **NASA**. Where it hasn't, each crew member gets a simulated preflight value inside a normal range, marked **SIM**. A local AI model reads typed, spoken or photographed entries, explains results in plain language and answers health questions. Everything works without a link to Earth.

## Quick start

1. Open [release/Aboard.exe](release/Aboard.exe) on Windows 10 or 11 (x64). It includes its own Python runtime, so nothing else needs installing.
2. Choose a crew member: **Mo**, **Parisa** or **Nayan**. Each has 60 days of simulated history.
3. Optional local AI: run `Configure-LocalAI.ps1` once to start Ollama and download the models (see [Local AI](#local-ai)). Without it, entries are read by simple offline rules, and every status, guide and export still works.

Data stays on the device under `%LOCALAPPDATA%\Aboard`. Use synthetic inputs only.

## Two-minute demo

1. **Today screen.**
   - **Body map:** each area glows by the status of its latest readings. Click **Heart**, **Eyes · SANS**, **Brain · sleep**, **Blood labs** or a calf to open its trends against the baseline.
   - **Readings vs baseline:** each tile shows the reading, a bar with the baseline range and value, and a badge. **NASA** means NASA website data and **SIM** means a simulated preflight value.
2. **Mood sticker.** Below Today's tasks, a sticker sums up the last week of questionnaires with a light-hearted comment. Compare the three crew members:
   - **Mo:** steady and strong.
   - **Parisa:** a hard stretch that is bouncing back this week.
   - **Nayan:** was fine, but strain is rising this week.
3. **New entry, the AI way.** Click **＋ New entry** and type, say (**Speak**) or photograph (**Add photo**) something like *"Heart beat is 68 and I slept 6 hours."* The readings appear as you type, and the local AI refines them after a short pause.
   - The local AI fills in the readings and detects the body area. Each reading is compared with its NASA or simulated baseline.
   - Edit any value, remove one, or add one by hand. Then click **Save entry**.
   - A flagged reading opens a guided repeat. **Log repeat reading** then asks only for that one measurement.
4. **Vision symptom.** A new entry saying *"my vision got blurry when reading"* turns yellow: **Vision change · Check your eyes**. **Eyes · SANS** then glows yellow on the body map.
5. **Ask me about your health.** Try *"Is my blood pressure normal compared with NASA data?"* or *"How has my mood been this week?"* Answers cite the baseline source and the questionnaire trend.
6. **Trends tab.** 60-day charts. The shaded band is the baseline range and the dashed line is the NASA or preflight baseline. Points outside the band turn yellow.
7. **Alerts.** A red result creates a crew alert and an Earth handoff that can be exported as JSON.

## Baselines

| Measurement | Baseline | Source |
| --- | --- | --- |
| Sleep | NASA 7.33 h, range 5.0–9.65 h | NASA Standard Measures, in-flight actigraphy, 19 astronauts, 2,137 nights |
| Resting heart rate, blood pressure | NASA mean, range mean ± 2 SD | NASA Apollo AP005, preflight resting supine, n=24 |
| Serum sodium, potassium, creatinine, glucose | NASA mean, range mean ± 2 SD | NASA Apollo AP004, preflight serum, n=33 |
| Calf ultrasound area (left and right) | **SIM**: random preflight value per crew member, inside 15–25 cm² | Approximate adult range. NASA Tele-SUS measured this in flight but published no range |
| Optic nerve OCT TRT250 (left and right) | **SIM**: random preflight value per crew member, inside 380–440 µm | Approximate range. NASA Fluid Shifts reported a flight-day-50 mean of 407.8 µm, without a range |

**Where the NASA datasets are used**

| NASA source (see `Aboard-Dataset-Inventory.xlsx`) | Used for | Code |
| --- | --- | --- |
| Apollo AP004 Clinical Biochemistry, workbook `JMAPAP004_127.xls` (in `Dataset/New for model/AP004_*.zip`) | Serum sodium, potassium, creatinine and glucose baselines, and the simulated lab history | `nasa_reference.py` `REFERENCES`, `baseline.py`, `demo_journal.py` |
| Apollo AP005 Cardiovascular Evaluations, report Table 6 (`NASA-AP005-Cardiovascular-Evaluations.pdf`) | Resting heart rate and blood pressure baselines, and the simulated vital-sign history | `nasa_reference.py` `CARDIO`, `baseline.py`, `demo_journal.py` |
| NASA Standard Measures sleep study (NTRS 20230003916) | Sleep baseline and range, and the simulated sleep history | `baseline.py`, `nasa_reference.py`, `demo_journal.py` |
| ISS Tele-SUS and NASA Fluid Shifts | Calf ultrasound and eye OCT measurement guides and study context (no range published, so these baselines are simulated) | `measurement_gallery.py`, `nasa_reference.py` |
| NASA Standard Measures and Behavioral Health measures | Topics of the six daily questionnaire items | `medical_followup.py` |
| 96-E400 and LSAH OCT | Archived reference series only (older builds) | `nasa_reference.py` `ARCHIVED_MEASUREMENTS` |

The 60-day demo history is simulated. Each crew member's vital signs and labs are drawn around the NASA AP005 and AP004 preflight means and standard deviations, and stay inside mean ± 2 SD. Sleep is drawn around the NASA Standard Measures mean. No individual astronaut records are used.

The two simulated ranges are approximations chosen for the demo. They are not validated clinical norms. A reading outside its range turns the result yellow and asks for a check and a possible repeat. See [NASA-References.md](NASA-References.md) for the NASA study details. The logic is in `baseline.py` and `nasa_reference.py`.

## Features

| Area | What Aboard does |
| --- | --- |
| Status at a glance | Glowing body map with a legend, and baseline tiles grouped into Needs attention, Vital signs, Blood labs, and Muscle and eyes |
| AI entry | Type, speak or add a photo of a device screen. Aboard extracts readings and the body area. Every number must appear in the note or on the screen, so the model cannot invent values. Photo readings are marked "from photo · check" |
| Guidance | An animated measurement guide for each reading, repeat-reading flows, symptom checks for very high blood pressure, and an emergency procedure for red results |
| Spaceflight risks | Short sleep and fatigue, cardiovascular change, muscle loss (calf ultrasound), SANS (vision symptoms and OCT), and behavioural health (daily questionnaire and mood sticker) |
| Routine | 08:00–12:00 questionnaire window with a countdown, missed-window reminders and a task checklist |
| Crew | Separate journals per crew member, crew alerts visible to the others, and an Earth handoff export |
| Offline | Rules, journal, guides, local AI (Ollama) and speech (whisper.cpp) all run on the device |

## How a result is decided

The rules in `analysis.py`, `nasa_reference.py`, `baseline.py` and `medical_followup.py` decide the status. They compare each reading with its baseline range and with fixed watch limits. They also look for symptom cues in the notes, such as vision changes or an urgent request. **I need help now** always raises a red alert. Every result lists its reasons under **Why this result?**

The AI model never sets or changes the status. The limits and recheck intervals are hackathon values, not clinical ones. Flight use would need approved protocols and clinical validation. Ultrasound and photo attachments are for human review only.

## Local AI

Two models run locally through [Ollama](https://ollama.com):

| Model | Used for |
| --- | --- |
| Llama 3.2 3B (`llama3.2:3b`, 2 GB) | Reading typed, spoken and photographed entries, **What this means** explanations, **Ask me about your health** |
| Gemma 3 4B (`gemma3:4b`, 3.4 GB) | Slow fallback for reading photo text when Windows OCR is not available |

- **Fast answers.** Replies stream as they are written, and the model is loaded when a crew member logs in.
- **Facts come from Python.** For health questions, Aboard computes lowest and highest values with dates, averages, trends, baseline comparisons and the questionnaire trend. The model only sees those facts. When a measurement was never logged, Aboard answers directly.
- **Photos.** The OCR engine built into Windows reads the text on a device screen (cuff, glucose meter, sleep watch) in about half a second, offline. Llama and the rules then turn that text into readings. On a CPU-only laptop, a full photo entry takes about 4–12 seconds. Photos without printed numbers, such as an injury or an ultrasound, are attached for human review, and no values are taken from them.
- **Offline fallback.** If Ollama isn't running, simple rules still pull blood pressure, pulse, sleep, labs and the body area out of the text.

**Setup.** Run `Configure-LocalAI.ps1`. It starts portable Ollama from `LocalModels/Ollama` and downloads both models into `LocalModels/weights`. Run it with `-SkipPull` after a reboot to only start the service. To use a different text model, pull it and set `ABOARD_OLLAMA_MODEL` before launch. Keep `release` and `LocalModels` side by side in the project folder. **Settings** in the app shows the model status.

**Speech.** **Speak** uses whisper.cpp and the English base model in `LocalModels/Whisper`, or the paths in `ABOARD_WHISPER_EXE` and `ABOARD_WHISPER_MODEL`. If neither is available, it can use Groq when a Groq key is stored in **Settings**.

## Images

Illustrations made with an image-generation model carry a visible **AI-generated** tag wherever they appear: the anatomy body map, the activity characters and the measurement and equipment pictures. These are `anatomy-atlas.png`, `activity-*.png`, `measurement-frames.png` and `equipment-atlas.png`, and the tag is added in `ai_label.py`. Art drawn by code (star field, mood sticker, rating faces and scripted guide animations) is not AI-generated.

## Privacy

The journal is the SQLite file `%LOCALAPPDATA%\Aboard\journal.sqlite`, with images in the `attachments` folder next to it. Profiles separate records inside Aboard. Anyone with access to the same Windows account or database files can read the records. The local AI model and offline dictation send nothing off the device.

## Public datasets and prior work

The app ships with generated training cases, simulated journal entries and a synthetic ultrasound example. Summary values from NASA archives supply the optional comparison bands (see [NASA-References.md](NASA-References.md) and [Aboard-Datasets.md](Aboard-Datasets.md)). No individual astronaut records were used to train any model. The datasets below were reviewed as candidates for future work.

| Resource | Useful for | Boundary |
| --- | --- | --- |
| [NASA OSDR Inspiration4](https://www.nasa.gov/osdr-latest-news-i4-mission-datasets/) and [multimodal study](https://www.nature.com/articles/s41586-024-07648-x) | Astronaut measurement selection, survey design, and comparisons with published summaries | Four civilian crew members, with access restrictions on some raw streams |
| [NASA, ESA, and DLR AGBRESA](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0239228) | Earth analog testing with downloadable [questionnaires](https://doi.org/10.1371/journal.pone.0239228.s001) and [heart rate and blood pressure](https://doi.org/10.1371/journal.pone.0239228.s002) | Bed-rest and centrifugation observations |
| [CSA Bio-Monitor](https://www.asc-csa.gc.ca/eng/sciences/bio-monitor.asp) and [Space Health](https://www.asc-csa.gc.ca/eng/sciences/space-flight-improve-monitor-health-earth.asp) | Astronaut sensor feasibility and repeated wellness questionnaires | Raw paired dataset access unverified |
| [PhysioNet QoL_Stress](https://physionet.org/content/qol-stress/1.0.0/) | Train a future stress-task benchmark with physiology and self-reports. Split by participant | Labeled Earth lab task |
| [EchoNet-Dynamic](https://echonet.github.io/dynamic/) and [pretrained weights](https://github.com/echonet/dynamic/releases/tag/v1.0.0) | A future cardiac ultrasound adapter with an explicit view and validated task | Four-chamber echocardiography and ejection fraction or segmentation |
| [USFM](https://github.com/openmedlab/USFM) and [ESA EchoFinder](https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/epsilon/EchoFinder_Augmented_reality_and_artificial_intelligence_for_ultrasound_scans) | Pretrained ultrasound representation and ISS precedent for guided acquisition | USFM needs a task-specific head. EchoFinder guides acquisition |
| [Kaggle sleep and lifestyle](https://www.kaggle.com/datasets/uom190346a/sleep-health-and-lifestyle-dataset) and [ultrasound nerve segmentation](https://www.kaggle.com/competitions/ultrasound-nerve-segmentation) | UI fixtures or a segmentation benchmark with a defined anatomy | No representative astronaut outcomes or alert-level labels |
| [MediaPipe Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker) | Future landmark capture from a reviewed demonstration video | Pose tracking gives no clinical verification of a procedure |

I found no verified public dataset with paired astronaut vitals, questionnaire responses, notes, scans, and outcome labels suitable for training the three alert levels. The current local model trains on seeded simulated cases. Workflow sources include [NASA Earth-Independent Medical Operations](https://ntrs.nasa.gov/citations/20250000009), [NASA health and medical care](https://www.nasa.gov/reference/3-0-health-and-medical-care/), and [NASA’s sleep risk evidence](https://humanresearchroadmap.nasa.gov/Risks/risk.aspx?i=100).

## Source and build

- **Run from source.** Use Python 3.12 x64 with Tk and Pillow and run `python desktop.py`. Add `--smoke-test` for the automated start-up check.
- **Self-checks.** `python analysis.py` checks the assessment rules. `python train_local.py` regenerates the small synthetic fatigue model in `local_model.json`.
- **Build the EXE.** Run `python build.py <python-dir>`, where `<python-dir>` is a full Python 3.12 installation with Tk and Pillow. The build uses the Windows .NET Framework C# compiler and writes `release/Aboard.exe`. Set `ABOARD_EXE_NAME` to choose another file name.

## Earlier prototypes

Earlier experiments are kept in `archive/old-releases/` and are not part of the submission. They include a 3D voice crew assistant with Groq commands, built from `aboard.py`, `crew.py` and `avatar3d.py`, and single-feature builds of the guides, gallery and telemetry screens.
