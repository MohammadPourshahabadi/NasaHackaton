"""Descriptive NASA cohort comparisons for the hackathon demonstration."""
from math import isfinite
from analysis import analyze, get_numeric

# AP004 JMAPAP004_127.xls, Sheet1, Excel rows 16, 17, 23 and 26.
# 96-E400 JMISS96_E400_81.xls, Sheet1, Excel rows 7-15 and 17.
REFERENCES = {
    'serum_sodium': ('Serum sodium', 'mEq/L', 141.5, 0.9, 33, 'AP004', 'https://ntrs.nasa.gov/citations/19760005589'),
    'serum_potassium': ('Serum potassium', 'mEq/L', 4.1, 0.3, 33, 'AP004', 'https://ntrs.nasa.gov/citations/19760005589'),
    'serum_creatinine': ('Serum creatinine', 'mg/dL', 1.2, 0.1, 33, 'AP004', 'https://ntrs.nasa.gov/citations/19760005589'),
    'serum_glucose': ('Serum glucose', 'mg/dL', 95.7, 7.3, 33, 'AP004', 'https://ntrs.nasa.gov/citations/19760005589'),
    'calf_torque': ('Calf isometric torque', 'N·m', 144, None, 9, '96-E400', 'https://doi.org/10.1152/japplphysiol.91578.2008'),
}

CALF_PREFLIGHT = (119, 114, 128, 157, 135, 117, 218, 138, 171)
CALF_US_SOURCE = 'https://pmc.ncbi.nlm.nih.gov/articles/PMC8047175/'
EYE_SOURCE = 'https://ntrs.nasa.gov/citations/20220007226'
ARCHIVED_MEASUREMENTS = {
    'calf_torque': REFERENCES['calf_torque'][:2],
    'calf_volume': ('Calf muscle volume (MRI)', 'cm³'),
    'rnfl_left': ('Global RNFL thickness (OCT) · Left eye', 'µm'),
    'rnfl_right': ('Global RNFL thickness (OCT) · Right eye', 'µm'),
}
IMAGING = {
    'calf_csa_left': ('Calf US area · Left', 'cm²'),
    'calf_csa_right': ('Calf US area · Right', 'cm²'),
    'trt250_left': ('OCT TRT250 · Left', 'µm'),
    'trt250_right': ('OCT TRT250 · Right', 'µm'),
}
AP005 = 'https://nlsp.nasa.gov/search/data/details/e1fa5c55-ddfe-5548-91ba-864080319f44?dataType=EXPERIMENTS'
SLEEP_STUDY = 'https://ntrs.nasa.gov/citations/20230003916'
# Apollo cardiovascular evaluations, Table 6, preflight Control, SDi.
CARDIO = {
    'pulse': ('Resting heart rate', 'bpm', 61.6, 8.60, 24, 'AP005', AP005),
    'systolic': ('Systolic pressure', 'mmHg', 115.3, 8.31, 24, 'AP005', AP005),
    'diastolic': ('Diastolic pressure', 'mmHg', 67.0, 6.61, 24, 'AP005', AP005),
}
NASA_MEASUREMENTS = {'Sleep': ('sleep', 'hours'),
                     **{row[0]: (key, row[1]) for key, row in {**CARDIO, **REFERENCES, **IMAGING}.items()
                        if key not in ARCHIVED_MEASUREMENTS}}
MEASURE_KEYS = {key for key, _ in NASA_MEASUREMENTS.values()}
CONTEXT_KEYS = {'notes', 'region', 'region_attention', 'urgent', 'ultrasound_path', 'injury_path',
                'ultrasound_review', 'nasa_supine_confirmed', 'nasa_protocol_confirmed'}


def supported_entry(checkin):
    return {key: value for key, value in checkin.items() if key in MEASURE_KEYS or key in CONTEXT_KEYS}


def assess(checkin, history):
    supported = supported_entry(checkin)
    real = [record for record in history if not record.get('demo_series')]
    prior = [supported_entry(record['checkin']) for record in real]
    result = compare(supported, analyze(supported, prior, require_all=False, include_model=False,
                                        latest_baseline=True))
    previous = {}
    for key in MEASURE_KEYS.intersection(supported):
        for row in reversed(prior):
            try:
                number = float(row[key])
            except (KeyError, TypeError, ValueError):
                continue
            if isfinite(number):
                previous[key] = number
                break
    result['previous_readings'] = previous
    return result


def compare(checkin, result):
    """Add descriptive evidence and a demo review flag. Preserve urgent escalation."""
    evidence = []
    flagged = []
    for key, (label, unit, mean, sd, count, experiment, url) in {**REFERENCES, **CARDIO}.items():
        if key in CARDIO and get_numeric(checkin, key)[0] is None:
            continue
        if key in ('systolic', 'diastolic'):
            try:
                if float(checkin['systolic']) <= float(checkin['diastolic']):
                    continue
            except (KeyError, TypeError, ValueError):
                pass
        raw = checkin.get(key)
        if raw in (None, ''):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if not isfinite(value) or value <= 0:
            continue
        band = (round(mean - 2*sd, 4), round(mean + 2*sd, 4)) if sd else (min(CALF_PREFLIGHT), max(CALF_PREFLIGHT))
        method = 'mean ± 2 SD' if sd else 'observed min–max'
        matched = True  # Aboard always compares with the NASA baseline when one exists.
        outside = not band[0] <= value <= band[1]
        evidence.append({'experiment': experiment, 'url': url, 'metric': key,
                         'value': value, 'unit': unit, 'mean': mean, 'n': count,
                         'comparison_band': band, 'method': method, 'matched': matched, 'outside': outside,
                         'protocol': 'Preflight resting supine control (five minutes)' if key in CARDIO else 'Preflight'})
        disposition = 'outside the NASA range' if outside else 'within the NASA range'
        result['rationale'].append(f'{label}: {value:g} {unit}, {disposition}. NASA baseline from {experiment} '
                                   f'preflight data (NASA website): mean {mean:g}, {method} {band[0]:g}–{band[1]:g} '
                                   f'{unit}, n={count}.')
        if outside:
            flagged.append(label)
            if key not in result['flagged_metrics']:
                result['flagged_metrics'].append(key)
    try:
        sleep = float(checkin.get('sleep'))
    except (TypeError, ValueError):
        sleep = None
    if sleep is not None and 0 <= sleep <= 24:
        band = (5.0, 9.65)
        outside = not band[0] <= sleep <= band[1]
        evidence.append({'experiment': 'Standard Measures', 'url': SLEEP_STUDY, 'metric': 'sleep',
                         'value': sleep, 'unit': 'h', 'mean': 7.33, 'sd': 1.16, 'n': 19, 'nights': 2137,
                         'comparison_band': band, 'method': 'mean ± 2 SD',
                         'protocol': 'In-flight actigraphy', 'matched': True, 'outside': outside})
        result['rationale'].append(f'Sleep: {sleep:g} h, {"outside" if outside else "within"} the NASA range. '
                                   'NASA baseline from Standard Measures (NASA website): 7.33 h average during '
                                   'flight by actigraphy, range 5.0–9.65 h (19 crew, 2,137 nights).')
        if outside:
            flagged.append('Sleep')
            if 'sleep' not in result['flagged_metrics']:
                result['flagged_metrics'].append('sleep')
    for key, (label, unit) in IMAGING.items():
        try:
            value = float(checkin.get(key))
        except (TypeError, ValueError):
            continue
        if not isfinite(value) or value <= 0:
            continue
        if key.startswith('calf_csa_'):
            experiment, url, count = 'ISS Tele-SUS', CALF_US_SOURCE, 11
            context = ('ISS Tele-SUS used guided panoramic ultrasound to measure calf muscle '
                       'cross-sectional area during flight. Track the same side and scan site.')
            statistic = {}
            protocol = 'Medial gastrocnemius cross-sectional area by panoramic ultrasound'
        else:
            experiment, url, count = 'NASA Fluid Shifts', EYE_SOURCE, 14
            context = ('In NASA’s left-eye study, mean TRT250 was 407.8 µm on flight day 50 '
                       'and 418.9 µm on flight day 150. Review scans with the medical team.')
            statistic = {'flight_day_means': {'50': 407.8, '150': 418.9}}
            protocol = 'Total retinal thickness in the 0–250 µm annulus from Bruch membrane opening'
        from baseline import REFERENCE as BASELINES
        low, high = BASELINES[key]['low'], BASELINES[key]['high']
        outside = not low <= value <= high
        evidence.append({'experiment': experiment, 'url': url, 'metric': key, 'value': value,
                         'unit': unit, 'n': count, 'protocol': protocol, 'matched': False,
                         'comparison_band': (low, high), 'simulated_baseline': True,
                         'outside': outside, **statistic})
        result['rationale'].append(f'{label}: {value:g} {unit}, {"outside" if outside else "within"} the approximate '
                                   f'normal range {low:g}–{high:g} {unit}. No NASA range exists for this measure, '
                                   f'so Aboard compares it with a simulated preflight baseline. {context}')
        if outside:
            flagged.append(label)
            if key not in result['flagged_metrics']:
                result['flagged_metrics'].append(key)
        if url not in result['sources']:
            result['sources'].append(url)
    if evidence:
        result['nasa_reference'] = evidence
    if flagged and result['status'] != 'red':
        if result['status'] == 'green':
            guide = next((('pulse' if item['metric'] == 'pulse' else 'bp') for item in evidence
                          if item['outside'] and item['metric'] in CARDIO), None)
            result.update(status='yellow', title='Outside your baseline range', guide=guide,
                          next_hours=4, recheck='Review during the next demo check-in in 4 hours.')
        many = len(flagged) > 1
        result['actions'].insert(0, ', '.join(flagged) + (' are' if many else ' is') + ' outside the baseline range. '
                                 'Check the unit and how ' + ('they were' if many else 'it was') + ' measured, then '
                                 'ask the crew medical officer whether to repeat ' + ('them.' if many else 'it.'))
    return result
