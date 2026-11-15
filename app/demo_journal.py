"""Seed reproducible, explicitly simulated readings for the demo profiles.

SI declaration: the simulated data design (random values inside normal human ranges, around NASA
AP004/AP005 means) was generated with Anthropic Claude. No real astronaut records are used.
"""
from datetime import date, timedelta
from math import sin, pi
from random import Random
import json

from baseline import baseline
from medical_followup import WELLBEING, wellbeing_summary
from nasa_reference import assess, CARDIO, REFERENCES


DEMO_PROFILES = ('mo', 'parisa', 'nayan', 'admin')
DEMO_VERSION = 'nasa-60-day-v4'
OLDER_VERSIONS = ('nasa-60-day-v1', 'nasa-60-day-v2', 'nasa-60-day-v3')
# Simulated history is drawn from NASA published distributions:
#   resting heart rate, systolic, diastolic  - Apollo AP005 preflight mean and SD (CARDIO)
#   serum sodium, potassium, creatinine, glucose - Apollo AP004 preflight mean and SD (REFERENCES)
#   sleep - NASA Standard Measures in-flight actigraphy, 7.33 h
# Each crew member gets a personal centre within about 0.6 SD of the NASA mean; daily values stay inside mean ± 2 SD.

# Wellbeing story for each crew member (ratings are strain, 1 = none, 10 = extreme).
#   mo     - steady, good mental health
#   parisa - a hard stretch that improves over the last week
#   nayan  - good, then getting worse over the last week
MOOD_STORY = {'mo': 'steady', 'parisa': 'improving', 'nayan': 'declining', 'admin': 'steady'}


def wellbeing_ratings(profile, i, days, rng):
    story = MOOD_STORY[profile]
    last_week = i >= days - 7
    step = i - (days - 7)  # 0..6 inside the last week
    if story == 'steady':
        level = 2
    elif story == 'improving':
        level = 7 if not last_week else round(7 - step * 5 / 6)
    else:
        level = 2 if not last_week else round(2 + step * 5.5 / 6)
    ratings = {key: max(1, min(10, level + rng.randint(-1, 1))) for key in WELLBEING}
    if story == 'improving' and not last_week and i % 5 == 0:
        ratings['sleep_difficulty'] = min(10, ratings['sleep_difficulty'] + 2)
    return ratings


def readings(profile, days):
    crew_index = DEMO_PROFILES.index(profile)
    rng = Random(2081 + crew_index)
    calf_base = baseline(profile, 'calf_csa_left')['value']
    calf_right = baseline(profile, 'calf_csa_right')['value']
    eye_base = baseline(profile, 'trt250_left')['value']
    eye_right = baseline(profile, 'trt250_right')['value']
    picker = Random(f'aboard-nasa-centre:{profile}')
    centre = {key: picker.uniform(-.6, .6) for key in ('pulse', 'systolic', 'diastolic', 'serum_glucose',
                                                      'serum_creatinine', 'serum_sodium', 'serum_potassium')}
    centre['sleep'] = picker.uniform(-.25, .25)
    result = []
    for i in range(days):
        phase = sin(2*pi*i/(11 + crew_index*2))
        trend = i/max(1, days-1)

        def variation(spread):
            return rng.uniform(-spread, spread)

        def nasa(key, table, spread):
            mean, sd = table[key][2], table[key][3]
            return mean + centre[key] * sd + spread * sd

        checkin = {
            'sleep': round(7.33 + centre['sleep'] + .26*phase + variation(.13) + .2*trend, 1),
            'pulse': round(nasa('pulse', CARDIO, .35*phase + variation(.25))),
            'systolic': round(nasa('systolic', CARDIO, .35*phase + variation(.25))),
            'diastolic': round(nasa('diastolic', CARDIO, .3*phase + variation(.25))),
            'notes': 'Simulated check-in drawn from NASA AP005 and Standard Measures distributions.',
        }
        if i%7 == 0:
            checkin.update({key: round(nasa(key, REFERENCES, variation(.6)), 2 if key == 'serum_creatinine' else 1)
                            for key in ('serum_glucose', 'serum_creatinine', 'serum_sodium', 'serum_potassium')})
        if i%10 == 0 or i == days-1:
            # Slow in-flight changes: calf muscle area shrinks, retinal thickness rises (both stay in range).
            checkin.update(calf_csa_left=round(calf_base - (0.5 + 0.2*crew_index)*trend + variation(.2), 2),
                           calf_csa_right=round(calf_right - (0.5 + 0.2*crew_index)*trend + variation(.2), 2),
                           trt250_left=round(eye_base + (6 + crew_index)*trend + variation(1.5), 1),
                           trt250_right=round(eye_right + (6 + crew_index)*trend + variation(1.5), 1),
                           region='Left leg',
                           notes='Simulated check-in with onboard calf ultrasound and OCT readings.')
        result.append((checkin, wellbeing_ratings(profile, i, days, rng)))
    return result


def seed_demo(journal, end=None):
    end = end or date.today()-timedelta(days=1)
    start = end-timedelta(days=59)
    with journal.db:
        journal.db.execute('BEGIN IMMEDIATE')
        for profile in DEMO_PROFILES:
            rows = journal.db.execute(
                'SELECT id, stamp, record FROM entries WHERE profile=? ORDER BY stamp, id',
                (profile,),
            )
            existing = [(row_id, stamp, json.loads(raw)) for row_id, stamp, raw in rows]
            if any(record.get('demo_series') == DEMO_VERSION for _, _, record in existing):
                continue
            # Replace older simulated series. Entries the crew member made themselves are kept.
            for row_id, _, record in existing:
                if record.get('demo_series') in OLDER_VERSIONS:
                    journal.db.execute('DELETE FROM entries WHERE id=?', (row_id,))
            occupied = {stamp[:10] for _, stamp, record in existing if not record.get('demo_series')}
            history = []
            for i, (checkin, ratings) in enumerate(readings(profile, 60)):
                day = (start+timedelta(days=i)).isoformat()
                if day in occupied:
                    continue
                stamp = day+'T09:00:00'
                assessment = assess(checkin, history)
                record = {'checkin':checkin,'status':assessment['status'],'assessment':assessment,
                          'daily':True,'stamp':stamp,'demo_series':DEMO_VERSION,
                          'wellbeing':wellbeing_summary(ratings)}
                history.append(record)
                journal.db.execute('INSERT INTO entries (stamp,profile,record) VALUES (?,?,?)',
                                   journal._entry(profile, stamp, record))
