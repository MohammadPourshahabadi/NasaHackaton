# NASA reference audit

Reviewed the 20 ZIP archives in Dataset. Many archives contain repeated copies of the same workbook or figure. This build includes derived reference values only.

| Archive | What the supplied files contain | Use in Aboard |
| --- | --- | --- |
| AP004 | Apollo 7–17 serum and 24-hour urine summaries. JMAPAP004_127.xls, Sheet1, Excel rows 16, 17, 23 and 26 report preflight mean and standard deviation for 33 crew members per selected analyte. | Serum sodium, potassium, creatinine and glucose. mg/100 mL equals mg/dL. Urine and point-of-care blood glucose are different measurements. |
| 96-E400 | ISS calf muscle performance before and after flight. JMISS96_E400_81.xls, Sheet1, Excel rows 7–15 contain nine preflight isometric measurements at neutral ankle angle. Row 17 reports mean 144 N·m and standard error 11 N·m. | Preflight observed span 114–218 N·m. Only for comparable calf dynamometry. Grip strength and circumference use different measurements. |
| AP001 | Apollo session records list the vitals measured and session metadata. The other spreadsheet describes drugs. | Protocol context. The supplied session workbook does not contain the vital-sign values needed for a baseline. |
| ASTP007 / ASTP009 | Leg-volume measurement protocol and muscle fatigue spectral analyses. | Context for future protocol-specific measurements. |
| ASTP005 / 9401621 / BRSMImmune | Contact surveillance tables, immunization protocol, and lab-specific immune-cell results. | Potential future evidence for matching immune assays. |
| LMLSTP3.5 / LMLSTP4.3 | Ground analog psychological measurement plan and habitat microbial surveillance tables. | Context for habitat research. |
| NAG91151 / NAG53952 / LSAHNEWSV13_1_2 | Sweat calcium workbooks, sleep and circadian research report, and overweight/obesity prevalence tables. | Research context. |
| DSO 402 / 470 / 474, M001, 15-IML-1 | Archived protocol-specific tables, images and reports. DSO 474 contains retinal measurements. | Future specialist review. |

## App behavior

Use **Make a new entry** and choose a NASA-supported measurement. Enter its value in the displayed unit. Confirm the comparison method only when the reading is comparable to the study. Serum references use historical preflight lab serum. Calf torque uses a neutral-ankle isometric dynamometer test. Aboard saves the NASA study identifier, sample count, method, and comparison band with the assessment.

For this demo, AP004 uses mean ± 2 SD and 96-E400 uses the observed minimum and maximum. An outside-band comparison asks the crew to verify the measurement and discuss whether to repeat it. Any urgent alert follows the existing escalation rules. These small historical cohorts provide descriptive comparisons. Clinical validation, relevant populations and approved protocols would be needed before using the values as decision limits. Existing routine measurements continue to use the astronaut’s prior readings when available.

Sources: [NASA Apollo clinical biochemistry](https://ntrs.nasa.gov/citations/19760005589), [ISS muscle performance study](https://doi.org/10.1152/japplphysiol.91578.2008).

## Additional public NASA catalog references

- AP005 Apollo Flight Crew Cardiovascular Evaluations. Downloaded NASA report 19760005591, Table 6, page 245. Preflight supine control of the lower-body negative-pressure protocol, before pressure was applied, after five minutes of rest. Historical means and between-crew SDi for 24 observations are 61.6 ± 8.60 bpm for heart rate, 115.3 ± 8.31 mmHg for systolic and 67.0 ± 6.61 mmHg for diastolic. The group comprised a historical Apollo cohort. Do not compare a seated measurement using this protocol switch. Aboard adds a separate opt-in and applies the demo mean ± 2 SD rule.
- NASA Standard Measures, report 20230003916. Public study summary from 19 astronaut volunteers and 2,137 in-flight nights, 7.33 ± 1.16 h using actigraphy. Aboard displays the study mean beside submitted sleep for context. Its personal-baseline sleep rules still apply. The downloaded NASA Sleep Accommodations brief provides further background.
- NLSP DSO 484 lists individual sleep measurements under restricted access. Public items mainly cover circadian response to a light intervention. These were excluded from the sleep comparison.

The new PDF sources are stored in Dataset/New for model. These aggregate references supply the deterministic comparison layer and are included as evidence in the local LLM's entry review. They were not used to retrain Gemma or the synthetic fatigue classifier.

## Calf muscle MRI and preflight eye exams

- **96-E400 calf morphology.** In the downloaded NLSP archive, workbook `JMISS96_E400_91.xls`, Sheet1, rows 7–15, 21–29 and 35–43 contain paired muscle volumes for nine coded participants, before flight and 4 and 19 days after return. `Dataset/New for model/NASA-96-E400-calf-MRI-volume.csv` transcribes the three original volume columns in cm³ for the gastrocnemius, soleus and combined muscle groups. Row 45 reports combined means of 764, 657 and 699 cm³. The app records the combined volume from a specialist's MRI report and displays those study means as context. The dataset's neutral-ankle dynamometer values remain a separate functional measurement. [Study and methods](https://doi.org/10.1152/japplphysiol.91578.2008)
- **ISS preflight OCT.** Patel et al. analyzed 30 eyes from 15 NASA ISS astronauts, using scans acquired 28–277 days before launch and after return. The preflight cohort median global RNFL thickness was 93.2 µm for the 1.73 mm radius circumpapillary scan. Aboard records this measurement separately by eye and displays the published median as context. No participant-level exam files were verified for download. [Published OCT analysis](https://jamanetwork.com/journals/jamaophthalmology/fullarticle/2667551)
- **Additional eye leads.** NASA's prospective Ocular Health study reports longitudinal OCT and optical biometry in 11 ISS astronauts. NASA's medical examination standard lists the full set of modalities. The locally downloaded DSO 474 workbooks measure photographic vessel widths in pixels and camera stabilization repeatability. OSD-679 and OSD-680 are rat hindlimb-suspension studies. For individual modern astronaut exam data, investigate the LSDA and LSAH access process. [NASA Ocular Health study](https://humanresearchroadmap.nasa.gov/tasks/task.aspx?i=1234) · [Published cohort](https://pubmed.ncbi.nlm.nih.gov/32239198/) · [NASA examination standard](https://www.nasa.gov/wp-content/uploads/2023/04/ochmo-std-100.1a.pdf) · [NASA repository access](https://ntrs.nasa.gov/citations/20220014789)

Both imaging references are descriptive. Aboard records and charts the specialist measurements and does not derive clinical flags from the cohort values.

## Onboard muscle and eye measurements

The ISS build uses guided panoramic ultrasound of the medial gastrocnemius (cross-sectional area in cm²) and onboard OCT of the optic nerve head (TRT250 in µm). Each measurement has separate left/right entry fields and a training guide. The [ISS Tele-SUS study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8047175/) reports 74 guided scans in 11 astronauts. The [NASA Fluid Shifts report](https://ntrs.nasa.gov/citations/20220007226) reports left-eye TRT250 means of 407.8 µm on flight day 50 and 418.9 µm on flight day 150 (Table 1). These summaries are descriptive and provide no app alert threshold. Previously saved ground-based calf MRI, calf torque and global RNFL entries appear only as archived series in Statistics.
