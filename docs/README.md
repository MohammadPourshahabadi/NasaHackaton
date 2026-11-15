# NASA data and references

Aboard compares every reading with a **baseline**. Where NASA published a range, that range is used and marked **NASA** in the app. Where NASA did not, each demo crew member gets a random preflight value inside an approximate normal range, marked **SIM**.

## Sources used in the app

| NASA source | Values used | Where in the code | Verified against the NASA file |
| --- | --- | --- | --- |
| [Apollo AP004 Clinical Biochemistry](https://ntrs.nasa.gov/citations/19760005589) | Serum Na 141.5 ± 0.9 mEq/L, K 4.1 ± 0.3 mEq/L, creatinine 1.2 ± 0.1 mg/dL, glucose 95.7 ± 7.3 mg/dL (n=33). Range = mean ± 2 SD | `app/nasa_reference.py`, `app/baseline.py`, `app/demo_journal.py` | Yes. `nasa-data/AP004_*.zip` → `JMAPAP004_127.xls`, Sheet1, rows 16, 17, 23, 26 |
| [Apollo AP005 Cardiovascular Evaluations](https://ntrs.nasa.gov/citations/19760005591) | Resting heart rate 61.6 ± 8.60 bpm, systolic 115.3 ± 8.31, diastolic 67.0 ± 6.61 mmHg (preflight supine, n=24) | same | Heart rate found on page 17 of `nasa-data/NASA-AP005-Cardiovascular-Evaluations.pdf`. Blood pressure is on the same scanned table |
| [NASA Standard Measures sleep](https://ntrs.nasa.gov/citations/20230003916) | 7.33 h average in flight, range 5.0–9.65 h | `app/baseline.py`, `app/nasa_reference.py` | `nasa-data/NASA-Standard-Measures-Sleep-20230003916.pdf` |
| [ISS Tele-SUS](https://pmc.ncbi.nlm.nih.gov/articles/PMC8047175/) | Calf ultrasound method (no range published, so the baseline is **SIM**, 15–25 cm²) | `app/measurement_gallery.py`, `app/baseline.py` | Method only |
| [NASA Fluid Shifts](https://ntrs.nasa.gov/citations/20220007226) | Eye OCT TRT250 method and flight-day-50 mean 407.8 µm as context (baseline is **SIM**, 380–440 µm) | same | Context value only |
| [NASA Spaceflight Standard Measures](https://www.nasa.gov/humans-in-space/spaceflight-standard-measures-characterizing-how-humans-adapt-in-space/), [Behavioral measures](https://taskbook.nasaprs.com/tbp/index.cfm?action=taskbook_content&uid=0537B5A7B98A78002A73E5ECA86E55B1) | Topics of the six daily wellbeing questions | `app/medical_followup.py` | Topics only |

The two SIM ranges (calf ultrasound and eye OCT) are approximations chosen for the demo. They are not validated clinical norms.

## Simulated demo history
Mo, Parisa and Nayan each have 60 days of simulated data (`app/demo_journal.py`). Their vital signs and labs are drawn around the NASA AP005 and AP004 preflight means and SDs, and stay inside mean ± 2 SD. Sleep is drawn around the NASA Standard Measures mean. The wellbeing stories are invented: Mo is steady, Parisa improves over the last week, and Nayan gets worse over the last week. **No real astronaut records are used.**

## Files in this folder
| File | What it is |
| --- | --- |
| `Aboard-Dataset-Inventory.xlsx` | Every source, what Aboard uses it for, where in the code, and how it was verified |
| `NASA-References.md`, `Aboard-Datasets.md` | Longer notes on each NASA archive we reviewed |
| `nasa-data/` | The original NASA files we used: AP004 archive, AP005 report, sleep report, 96-E400 calf MRI CSV |
