"""Source-linked follow-up and daily self-report for the mission simulation."""
import re

AHA = 'https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/monitoring-your-blood-pressure-at-home'
NASA_CARE = 'https://www.nasa.gov/reference/3-0-health-and-medical-care/'
NASA_BEHAVIOR = 'https://www.nasa.gov/humans-in-space/spaceflight-standard-measures-characterizing-how-humans-adapt-in-space/'
NASA_SUPPORT = 'https://www.nasa.gov/humans-in-space/isolation-what-can-we-learn-from-the-experiences-of-nasa-astronauts/'

BP_SYMPTOMS = ('Chest pain', 'Shortness of breath', 'Back pain', 'Numbness',
               'Weakness', 'Vision changes', 'Difficulty speaking')
WELLBEING = {
    'mental_fatigue': 'How mentally exhausted do you feel right now?',
    'stress_now': 'How stressed do you feel right now?',
    'workload_now': 'How demanding has your work felt today?',
    'sleep_difficulty': 'How much difficulty did you have sleeping last night?',
    'low_mood': 'How low or down have you felt today?',
    'task_difficulty': 'How much have your symptoms affected your duties today?',
}


def severe_bp(values):
    from analysis import get_numeric
    return any((get_numeric(values, key)[0] or 0) > limit
               for key, limit in (('systolic', 180), ('diastolic', 120)))


NASA_SANS = 'https://humanresearchroadmap.nasa.gov/risks/risk.aspx?i=105'
VISION_CUES = re.compile(
    r"\b(?:blurr?(?:y|ed)\s+(?:vision|sight)|(?:vision|sight|eyesight)\s+(?:is\s+|got\s+|getting\s+|seems\s+)?"
    r"(?:blurr?y|blurred|changed?|changing|worse|fuzzy|dim)|double\s+vision|vision\s+(?:loss|changes?|problems?)|"
    r"(?:trouble|difficulty|hard(?:er)?\s+time)\s+(?:reading|focusing|seeing)|"
    r"hard(?:er)?\s+to\s+(?:read|focus|see)|can'?t\s+(?:read|focus|see)\s+(?:clearly|well|properly|up close)|"
    r"eye\s+pain|seeing\s+spots|blind\s+spot)\b", re.I)


def vision_symptom(notes):
    from analysis import context_cue
    return context_cue(VISION_CUES, str(notes or '').replace('’', "'"))


def apply_followup(checkin, result):
    if vision_symptom(checkin.get('notes')) and result['status'] != 'red':
        result['vision_symptom'] = True
        if result['status'] == 'green':
            result.update(status='yellow', title='Vision change · Check your eyes', guide='sleep',
                          recheck='Today, after the crew medical officer reviews it.', next_hours=None,
                          actions=[])
        result['actions'][0:0] = [
            'Do the onboard vision check (near and far reading chart, Amsler grid) and note which eye is affected.',
            'Report the change to the crew medical officer today. In flight, vision changes can be an early sign of '
            'SANS (spaceflight-associated neuro-ocular syndrome) and may need an OCT eye scan.',
        ]
        result['rationale'].insert(0, 'The notes describe a change in vision. Aboard treats new vision symptoms '
                                      'in flight as a reason for an eye check.')
        result.setdefault('sources', [])
        if NASA_SANS not in result['sources']:
            result['sources'].append(NASA_SANS)
    if severe_bp(checkin):
        answers = checkin.get('bp_followup', {})
        symptoms = [name for name in BP_SYMPTOMS if name in answers.get('symptoms', [])]
        if symptoms:
            result.update(status='red', title='Alert the crew medical officer now', guide='urgent', next_hours=0,
                          recheck='Follow the mission emergency procedure now.',
                          actions=['Alert the crew medical officer and follow the mission emergency procedure now.',
                                   'Share the reading and reported symptoms with the medical officer.'])
            result['rationale'].insert(0, 'Very high blood pressure with reported symptoms: ' + ', '.join(symptoms) + '.')
        elif result['status'] != 'red':
            repeat = answers.get('repeat') or {}
            if severe_bp(repeat):
                detail = 'Repeat reading is still very high. Contact the crew medical officer immediately.'
            elif repeat:
                detail = 'Repeat reading was recorded. Share both readings promptly with the crew medical officer.'
            else:
                detail = ('Contact the crew medical officer now. If you have no concerning symptoms, '
                          'wait at least one minute before repeating and record both readings.')
            result['actions'].insert(0,detail)
        result['sources'].extend(url for url in (AHA,NASA_CARE) if url not in result['sources'])
    return result


def wellbeing_summary(answers):
    if answers.keys() != WELLBEING.keys() or any(not 1 <= score <= 10 for score in answers.values()):
        raise ValueError('Answer all six wellbeing questions with ratings from 1 to 10.')
    peak=max(answers.values())
    label='High self-reported strain' if peak>=8 else ('Some self-reported strain' if peak>=4 else 'Low self-reported strain')
    if peak >= 8 or answers.get('task_difficulty', 0) >= 4:
        scene = 'support'
        action = 'Contact the crew medical officer to request a private psychological appointment and confirm a time. If you cannot perform a duty safely, tell the crew lead now.'
    elif peak >= 4:
        scene = 'sleep' if answers['sleep_difficulty'] == peak else 'reset'
        action = ('Protect your scheduled sleep window.' if scene == 'sleep' else
                  'Make time for a short break or a mindfulness activity.')
        action += ' If the difficulty continues or worsens, request a private psychological conference.'
    else:
        scene = 'routine'
        action = 'Keep your usual sleep, activity and social routines. Complete the next daily check-in. You can request private support at any time.'
    return {'ratings': answers, 'label': label, 'source': NASA_BEHAVIOR,
            'interpretation': 'Aboard prototype uses the highest 1–10 rating for its demo bands. The check-in tracks self-reported strain.',
            'scale_min': 1, 'scene': scene, 'action': action, 'support_source': NASA_SUPPORT}
