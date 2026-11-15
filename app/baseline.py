"""Reference baselines: NASA published values where they exist, simulated preflight values otherwise.

SI declaration: simulated values generated with Anthropic Claude (random, inside normal ranges).

Every measurement is compared with one baseline:
* NASA   - mean and range (mean ± 2 SD) published by NASA. Source and study are shown in the app.
* SIMULATED - no NASA range in the reviewed data. Each crew member gets a random preflight value inside an
  approximate normal range. These values are invented for the demo and are labelled as such everywhere.
"""
from random import Random

from nasa_reference import CARDIO, REFERENCES, SLEEP_STUDY, CALF_US_SOURCE, EYE_SOURCE

NASA_BADGE = 'NASA data'
SIM_BADGE = 'Simulated'


def _nasa(row, study, detail):
    label, unit, mean, sd, count, _experiment, url = row
    return {'kind': 'nasa', 'label': label, 'unit': unit, 'center': mean,
            'low': round(mean - 2 * sd, 2), 'high': round(mean + 2 * sd, 2),
            'study': study, 'detail': f'{detail}, n={count}', 'url': url,
            'method': 'mean ± 2 SD'}


REFERENCE = {
    'sleep': {'kind': 'nasa', 'label': 'Sleep', 'unit': 'hours', 'center': 7.33, 'low': 5.0, 'high': 9.65,
              'study': 'NASA Standard Measures', 'detail': 'in-flight wrist actigraphy, 19 astronauts, 2,137 nights',
              'url': SLEEP_STUDY, 'method': 'mean ± 2 SD'},
    **{key: _nasa(row, 'NASA Apollo AP005', 'preflight resting supine control') for key, row in CARDIO.items()},
    **{key: _nasa(row, 'NASA Apollo AP004', 'preflight serum, Apollo crews')
       for key, row in REFERENCES.items() if key.startswith('serum')},
    # No NASA range in the reviewed data. Approximate adult ranges; not validated clinical norms.
    'calf_csa_left': {'kind': 'sim', 'label': 'Calf US area · Left', 'unit': 'cm²', 'low': 15.0, 'high': 25.0,
                      'study': 'Approximate adult range', 'url': CALF_US_SOURCE,
                      'detail': 'medial gastrocnemius area; NASA Tele-SUS measured this in flight without a public range'},
    'calf_csa_right': {'kind': 'sim', 'label': 'Calf US area · Right', 'unit': 'cm²', 'low': 15.0, 'high': 25.0,
                       'study': 'Approximate adult range', 'url': CALF_US_SOURCE,
                       'detail': 'medial gastrocnemius area; NASA Tele-SUS measured this in flight without a public range'},
    'trt250_left': {'kind': 'sim', 'label': 'OCT TRT250 · Left', 'unit': 'µm', 'low': 380.0, 'high': 440.0,
                    'study': 'Approximate range', 'url': EYE_SOURCE,
                    'detail': 'NASA Fluid Shifts reported a flight-day-50 mean of 407.8 µm, without a range'},
    'trt250_right': {'kind': 'sim', 'label': 'OCT TRT250 · Right', 'unit': 'µm', 'low': 380.0, 'high': 440.0,
                     'study': 'Approximate range', 'url': EYE_SOURCE,
                     'detail': 'NASA Fluid Shifts reported a flight-day-50 mean of 407.8 µm, without a range'},
}


def _simulated_preflight(profile, key):
    """Stable random preflight value in the middle 60% of the normal range for this crew member."""
    ref = REFERENCE[key]
    side = key.rsplit('_', 1)[0]  # left and right sides share one base value
    rng = Random(f'aboard-preflight:{profile}:{side}')
    span = ref['high'] - ref['low']
    value = ref['low'] + span * rng.uniform(.2, .8)
    if key.endswith('_right'):
        value += span * .03
    return round(value, 2 if span < 50 else 1)


def fmt(value):
    """Readable precision: 98.68 -> 98.7, 4.13 -> 4.1, 1.25 -> 1.25."""
    value = float(value)
    if abs(value) >= 10:
        return f'{round(value, 1):g}'
    return f'{round(value, 2):g}' if abs(value) < 2 else f'{round(value, 1):g}'


def baseline(profile, key):
    """The value and range a reading is compared with, plus how to label it."""
    ref = REFERENCE.get(key)
    if not ref:
        return None
    if ref['kind'] == 'nasa':
        value = ref['center']
        name = f"NASA baseline {fmt(value)} {ref['unit']}"
        range_text = f"NASA range {fmt(ref['low'])}–{fmt(ref['high'])} {ref['unit']}"
        source = f"{ref['study']} ({ref['detail']}). Source: NASA website, {ref['url']}"
        badge = NASA_BADGE
    else:
        value = _simulated_preflight(profile or 'crew', key)
        name = f"Your preflight {fmt(value)} {ref['unit']} (simulated)"
        range_text = f"Normal range {fmt(ref['low'])}–{fmt(ref['high'])} {ref['unit']} (approximate)"
        source = (f"Simulated preflight value: random number inside an approximate normal range. Not real data. "
                  f"{ref['detail']}.")
        badge = SIM_BADGE
    return {'key': key, 'kind': ref['kind'], 'value': value, 'low': ref['low'], 'high': ref['high'],
            'unit': ref['unit'], 'label': ref['label'], 'name': name, 'range_text': range_text,
            'source': source, 'badge': badge, 'url': ref['url'], 'study': ref['study'], 'detail': ref['detail']}


def compare(profile, key, value):
    """Position of a reading against its baseline."""
    base = baseline(profile, key)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if base is None:
        return None
    delta = number - base['value']
    pct = delta / base['value'] * 100 if base['value'] else 0
    inside = base['low'] <= number <= base['high']
    word = 'within' if inside else ('below' if number < base['low'] else 'above')
    return {**base, 'reading': number, 'delta': delta, 'pct': pct, 'inside': inside, 'where': word,
            'summary': f"{word} the {base['range_text'].replace('Normal range', 'normal range')} · "
                       f"{'+' if delta >= 0 else '−'}{fmt(abs(delta))} {base['unit']} vs "
                       f"{'NASA' if base['kind'] == 'nasa' else 'your preflight'} baseline"}


def outside_range(key, value):
    ref = REFERENCE.get(key)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return bool(ref) and not ref['low'] <= number <= ref['high']
