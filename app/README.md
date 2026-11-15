# Aboard desktop app

The full onboard version of Aboard: a Windows app with a body map, NASA baselines, AI-assisted entries, a mood sticker and 60-day trends. It runs completely offline.

## Run it

1. Download **[release/Aboard.exe](release/Aboard.exe)** (Windows 10 or 11, 64-bit).
2. Double-click it. The first start takes a few seconds while it unpacks its built-in Python.
3. Choose **Mo**, **Parisa** or **Nayan**. Each has 60 days of simulated history.

That's it. Rules, NASA baselines, guides and charts all work right away. The AI features need Ollama (below).

## Turn on the local AI (optional)

Aboard talks to [Ollama](https://ollama.com), a free program that runs AI models on your own computer.

1. **Install Ollama.** Download it from [ollama.com/download/windows](https://ollama.com/download/windows) and run the installer.
2. **Download the models.** Open PowerShell and run:
   ```powershell
   ollama pull llama3.2:3b
   ollama pull gemma3:4b
   ```
   Llama 3.2 (2 GB) reads your entries and answers questions. Gemma 3 (3.4 GB) is only a fallback for reading photos on computers without Windows OCR, so you can skip it.
3. **Start Aboard.** Open **Settings** in the app. It should say **Ready on this device**.

**Prefer a portable setup?** Put the portable Ollama runtime in `app/LocalModels/Ollama` and run `Configure-LocalAI.ps1`. It starts Ollama and downloads both models into `app/LocalModels/weights`, and Aboard finds them automatically.

**Offline speech (optional):** put `whisper-cli.exe` and `ggml-base.en.bin` from [whisper.cpp](https://github.com/ggerganov/whisper.cpp) in `app/LocalModels/Whisper`. Then the **Speak** button works without internet.

## A 2-minute tour

1. **Today:** the body map glows by status. Click **Heart**, **Eyes · SANS**, **Brain · sleep**, **Blood labs** or a calf to see its trend.
2. **Readings vs baseline:** every tile shows your value on a bar with its baseline range. **NASA** means NASA data. **SIM** means a simulated preflight value.
3. **＋ New entry:** type *"Heart beat is 68 and I slept 6 hours"*. The values appear as you type. Or click **Add photo** and pick a picture of a blood-pressure cuff screen. Windows reads the screen and Aboard fills in the numbers.
4. **Repeat a reading:** a flagged value (try heart rate `112`) opens a guided repeat that asks only for that one measurement.
5. **Vision symptom:** write *"my vision got blurry when reading"*. The result turns yellow, **Eyes · SANS** glows and the next step is a vision check.
6. **Mood sticker:** sums up the last week of questionnaires. Mo is steady, Parisa is bouncing back and Nayan is running low.
7. **Ask me about your health:** *"Is my blood pressure normal compared with NASA data?"*

## How it decides

- **Status:** rules in `analysis.py`, `nasa_reference.py`, `baseline.py` and `medical_followup.py` decide green, yellow or red. **Why this result?** shows the reasons.
- **NASA baselines:** Apollo AP005 (heart rate and blood pressure), Apollo AP004 (serum labs) and NASA Standard Measures (sleep). See [../docs/README.md](../docs/README.md).
- **AI:** `ai_core.py` holds all AI features. The model only ever sees facts that Python computed. For any number it reads, that number must appear in your text or on the device screen, so it can't invent values. It never changes a status.
- **SI watermark:** `ai_label.py` stamps a visible **SI-generated** watermark on every SI-generated illustration.

## Files

| File | Role |
| --- | --- |
| `desktop.py` / `mission.py` | Starts the app and draws its screens |
| `ai_core.py` | Ollama connection, entry reading, photo reading (Windows OCR), explanations, questions, mood sticker |
| `baseline.py`, `nasa_reference.py` | NASA and simulated baselines and comparisons |
| `analysis.py`, `medical_followup.py` | Status rules, vision (SANS) and blood-pressure follow-up |
| `demo_journal.py` | The 60-day simulated crew histories |
| `polish.py`, `wellbeing_ui.py`, `measurement_gallery.py`, `activity_gallery.py` | Visuals, questionnaire, measurement guides |
| `storage.py` | Local SQLite journal in `%LOCALAPPDATA%\Aboard` |
| `build.py`, `Launcher.cs` | Packages everything into `release/Aboard.exe` |

## Run from source or rebuild

- **Run from source:** `python desktop.py`. You need Python 3.12 with Tk and Pillow.
- **Self-check:** `python desktop.py --smoke-test` and `python analysis.py`.
- **Rebuild the EXE:** `python build.py <path-to-python-3.12>`. This writes `release/Aboard.exe`.

Your journal stays on your computer in `%LOCALAPPDATA%\Aboard`. Aboard is a hackathon prototype, not a medical device.
