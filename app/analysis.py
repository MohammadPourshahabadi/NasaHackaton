"""Local check-in analysis for the Aboard training prototype.

The status is a transparent workflow rule. The separately displayed model was
trained with synthetic labels and never decides a status or an action.
"""

import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from statistics import median


SOURCE_CREW_MEDICINE = "https://www.nasa.gov/reference/3-0-health-and-medical-care/"
SOURCE_SLEEP = "https://humanresearchroadmap.nasa.gov/Risks/risk.aspx?i=100"
SOURCE_BP = (
    "https://www.heart.org/en/health-topics/high-blood-pressure/"
    "understanding-blood-pressure-readings/monitoring-your-blood-pressure-at-home"
)
SOURCE_ULTRASOUND = (
    "https://www.nasa.gov/missions/station/ultrasound-scans-in-space-transform-medicine-on-earth/"
)

MODEL_FILE = Path(__file__).with_name("local_model.json")
MODEL_FEATURES = ("sleep", "fatigue", "mood", "pulse", "schedule_change")
MODEL_SLEEP_BOUNDS = (4.0, 9.0)
MODEL_PULSE_BOUNDS = (48, 104)
REQUIRED = ("sleep", "fatigue", "mood", "pulse", "systolic", "diastolic", "temperature")
LABELS = {
    "sleep": "sleep duration", "fatigue": "fatigue rating", "mood": "mood rating",
    "pulse": "resting pulse", "systolic": "systolic pressure",
    "diastolic": "diastolic pressure", "temperature": "temperature",
}
# Entry bounds catch typing/unit errors. They are not a medical reference range.
ENTRY_BOUNDS = {
    "sleep": (0, 24), "fatigue": (1, 5), "mood": (1, 5), "pulse": (1, 350),
    "systolic": (1, 400), "diastolic": (0, 350), "temperature": (25, 50),
}
GUIDES = {
    "sleep": "sleep", "fatigue": "sleep", "mood": "sleep", "pulse": "pulse",
    "systolic": "bp", "diastolic": "bp", "temperature": "temperature",
}
WATCH_CHANGES = {"pulse": 15, "systolic": 20, "diastolic": 12, "temperature": 0.8}
SHIFT_CUES = re.compile(r"\b(shift change|schedule change|night shift|changed shifts)\b", re.I)
PULSE_CUES = re.compile(r"\b(?:measured|checked|taken|reading)\b[^.!?\n]{0,40}\bafter (?:exercise|workout|training)\b", re.I)
NEGATION_CUE = re.compile(r"\b(?:no|not|never|without)\b", re.I)


def get_numeric(checkin, field):
    """Return a (value, issue) pair. Clean missing and invalid values are distinct."""
    raw = checkin.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, "missing"
    try:
        value = float(raw) if not isinstance(raw, bool) else math.nan
    except (TypeError, ValueError, OverflowError):
        return None, "invalid"
    low, high = ENTRY_BOUNDS[field]
    if not low <= value <= high or (field in {"fatigue", "mood"} and not value.is_integer()):
        return None, "invalid"
    return value, None


def history_medians(history):
    """Use at least three valid earlier readings among the previous 14 check-ins."""
    earlier = []
    for item in (history or ())[-14:]:
        if isinstance(item, Mapping):
            row = item.get("checkin", item)
            if isinstance(row, Mapping) and row.get("urgent") is not True and row.get("ultrasound_review") != "urgent":
                earlier.append(row)

    baseline = {}
    for field in ("sleep", *WATCH_CHANGES):
        values = []
        for row in earlier:
            value, _ = get_numeric(row, field)
            if field in {"systolic", "diastolic"}:
                top, _ = get_numeric(row, "systolic")
                bottom, _ = get_numeric(row, "diastolic")
                if top is None or bottom is None or top <= bottom:
                    continue
            if field == "pulse" and context_cue(PULSE_CUES, str(row.get("notes") or "")):
                continue
            if value is not None:
                values.append(value)
        if len(values) >= 3:
            baseline[field] = median(values)
    return baseline


def context_cue(pattern, notes):
    """Use explicit text cues as context only, with simple clause-level negation."""
    for clause in re.split(r"[.!?;\n,]", notes):
        match = pattern.search(clause)
        if match and not NEGATION_CUE.search(clause[:match.end()]):
            return True
    return False


def sigmoid(value):
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def local_insight(values, schedule_change, model_path):
    absent = {"label": "Synthetic fatigue-pattern model", "probability": None}
    predictors = dict(values, schedule_change=float(schedule_change))
    if any(predictors.get(field) is None for field in MODEL_FEATURES):
        return dict(absent, detail="Needs valid sleep, fatigue, mood and resting pulse entries.")
    if not (MODEL_SLEEP_BOUNDS[0] <= predictors["sleep"] <= MODEL_SLEEP_BOUNDS[1]
            and MODEL_PULSE_BOUNDS[0] <= predictors["pulse"] <= MODEL_PULSE_BOUNDS[1]):
        return dict(absent, detail="Readings are outside the simulated model’s training range.")

    try:
        with Path(model_path or MODEL_FILE).open(encoding="utf-8") as stream:
            model = json.load(stream)
        if model["version"] != 1 or tuple(model["features"]) != MODEL_FEATURES:
            raise ValueError("Model schema mismatch")
        weights = model["weights"]
        means = model["means"]
        scales = model["scales"]
        bias = float(model["bias"])
        if not len(weights) == len(means) == len(scales) == len(MODEL_FEATURES):
            raise ValueError("Model shape mismatch")
        logit = bias + sum(
            weights[index] * (predictors[field] - means[index]) / scales[index]
            for index, field in enumerate(MODEL_FEATURES)
        )
        if not math.isfinite(logit):
            raise ValueError("Invalid model output")
    except (OSError, ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError):
        return dict(absent, detail="Model unavailable. The offline check-in rules still ran.")

    return {
        **absent,
        "probability": round(sigmoid(logit), 3),
        "detail": "Synthetic fatigue-pattern score. Status and actions come from the check-in rules.",
        "provenance": "Logistic regression fitted to simulated examples. No flight or patient records.",
    }


def analyze(checkin, history=None, model_path=None, *, require_all=True, include_model=True, latest_baseline=False):
    """Fuse available check-in inputs using transparent workflow rules.

    History is oldest first, with each entry a check-in or a record containing
    a 'checkin' mapping. All records must belong to the same crew member.
    Pulse is bpm, temperature is Celsius and cuff readings are mmHg.
    Fatigue 5 is highest and mood 5 is best. `urgent=True` is a crew report.
    An ultrasound review value represents a human review, not image inference.
    """
    values, missing, invalid = {}, [], []
    for field in REQUIRED:
        value, issue = get_numeric(checkin, field)
        values[field] = value
        if issue == "missing" and require_all:
            missing.append(field)
        elif issue == "invalid":
            invalid.append(field)

    systolic, diastolic = values["systolic"], values["diastolic"]
    if systolic is not None and diastolic is not None and systolic <= diastolic:
        invalid.extend(("systolic", "diastolic"))
        values["systolic"] = values["diastolic"] = None

    notes = str(checkin.get("notes") or "").strip()
    schedule_change = context_cue(SHIFT_CUES, notes)
    pulse_after_effort = context_cue(PULSE_CUES, notes)
    attached = bool(str(checkin.get("ultrasound_path") or "").strip())
    review = str(checkin.get("ultrasound_review") or "unreviewed").strip().lower()
    scan_review = {
        "unreviewed": "Image attached for human review. Image pixels were not scored.",
        "routine": "Human review recorded as routine.",
        "followup": "Human reviewer requested follow-up.",
        "urgent": "Human reviewer requested immediate action.",
    }
    if not attached:
        scan_state = "No scan attached. Routine check-ins can omit a scan."
    else:
        scan_state = scan_review.get(review, scan_review["unreviewed"])
    modalities = {
        "Questionnaire": f"{sum(values[field] is not None for field in REQUIRED[:3])}/3 valid daily answers.",
        "Vitals": f"{sum(values[field] is not None for field in REQUIRED[3:])}/4 valid measurement entries.",
        "Crew notes": "Context recorded for review." if notes else "No notes entered.",
        "Ultrasound": scan_state,
    }
    if not require_all:
        modalities.pop('Questionnaire')
        modalities.pop('Vitals')

    urgent = []
    if checkin.get("urgent") is True:
        urgent.append("The check-in reports a warning symptom or an immediate crew concern.")
    if review == "urgent":
        urgent.append("An urgent ultrasound assessment was entered manually.")

    watch = []
    flagged_metrics = []
    if missing:
        watch.append(("Missing: " + ", ".join(LABELS[field] for field in missing) + ".", GUIDES[missing[0]]))
    if invalid:
        watch.append(("Check entries or units: " + ", ".join(LABELS[field] for field in invalid) + ".", GUIDES[invalid[0]]))
    if checkin.get("injury_path"):
        watch.append(("An injury photo is attached for human review.", None))
    if review == "followup":
        watch.append(("A human ultrasound reviewer requested a follow-up.", "ultrasound"))
    elif attached and review != "routine" and review != "urgent":
        watch.append(("The attached scan is waiting for human review.", "ultrasound"))

    # AHA guidance for home readings, used to demonstrate a prompt to contact
    # the medical officer. The simulation does not apply a flight BP standard.
    very_high_bp = (
        (systolic is not None and systolic > 180)
        or (diastolic is not None and diastolic > 120)
    )
    if very_high_bp:
        watch.insert(0, ("The entered cuff value exceeds the very high terrestrial BP reference.", "bp"))
        flagged_metrics.extend(key for key,value,limit in
                               (('systolic',systolic,180),('diastolic',diastolic,120))
                               if value is not None and value>limit)

    baseline = history_medians(history)
    reference_label = "recent median"
    if latest_baseline:
        baseline = {}
        for row in reversed(history or []):
            values_at_time = row.get('checkin',row)
            for key in ("sleep", *WATCH_CHANGES):
                value,_ = get_numeric(values_at_time,key)
                if value is not None and key not in baseline:
                    baseline[key] = value
        reference_label = "previous reading"
    sleep = values["sleep"]
    fatigue = values["fatigue"]
    usual_sleep = baseline.get("sleep")
    short_sleep = sleep is not None and (sleep <= 5.5 or (usual_sleep is not None and usual_sleep - sleep >= 1.25))
    if short_sleep:
        flagged_metrics.append('sleep')
    if fatigue is not None and fatigue >= 4:
        if short_sleep:
            message = "Short sleep and high fatigue were reported together."
            if usual_sleep is not None:
                message = f"Reported sleep is {sleep:g} h vs. a {usual_sleep:g} h {reference_label}, with high fatigue."
        else:
            message = "The questionnaire reports high fatigue."
        watch.append((message, "sleep"))
    elif short_sleep:
        message = f"Recorded sleep was {sleep:g} hours."
        if usual_sleep is not None:
            message += f" {reference_label.capitalize()}: {usual_sleep:g} hours."
        watch.append((message, "sleep"))
    if values["mood"] is not None and values["mood"] <= 2:
        watch.append(("The questionnaire reports low mood.", "sleep"))

    for field, amount in WATCH_CHANGES.items():
        value, usual = values[field], baseline.get(field)
        if value is not None and usual is not None and abs(value - usual) >= amount:
            flagged_metrics.append(field)
            watch.append((f"{LABELS[field].capitalize()} differs from its {reference_label} ({value:g} vs. {usual:g}).", GUIDES[field]))

    # Broad demo watch values also make follow-up visible on a first check-in.
    vitals_watch = {
        "pulse": lambda value: value < 45 or value > 110,
        "systolic": lambda value: value < 90 or 150 <= value <= 180,
        "diastolic": lambda value: value < 50 or 95 <= value <= 120,
        "temperature": lambda value: value < 35.5 or value >= 38,
    }
    for field, outside_demo_watch in vitals_watch.items():
        if values[field] is not None and outside_demo_watch(values[field]):
            flagged_metrics.append(field)
            watch.append((f"{LABELS[field].capitalize()} crossed a demonstration watch value.", GUIDES[field]))
    if pulse_after_effort:
        if values['pulse'] is not None:
            flagged_metrics.append('pulse')
        watch.append(("A note indicates a measurement after exertion. Confirm a resting pulse.", "pulse"))

    reasons = [reason for reason, _ in watch]
    if schedule_change:
        reasons.append("The note mentions a schedule change. Include that context in the review.")

    if urgent:
        result = {
            "status": "red", "title": "Alert the crew medical officer now", "guide": "urgent",
            "rationale": urgent + reasons,
            "actions": [
                "Alert the crew medical officer and use the mission emergency procedure now.",
                "If the medical officer directs a repeat measurement, capture it with the animated guide and record the time.",
                "Record what was done and prepare a summary for the flight surgeon as the link permits.",
            ],
            "recheck": "Follow the medical officer’s instructions after alerting them.",
            "next_hours": 0,
        }
    elif watch:
        fast = very_high_bp
        repeat_guides = list(dict.fromkeys(guide for _, guide in watch
                                          if guide in {"bp", "pulse", "temperature"}))
        actions = []
        if fast:
            actions.append("Contact the crew medical officer now for a repeat and review plan.")
        elif repeat_guides:
            actions.append("Check the flagged vital signs and follow the onboard procedure for a repeat reading.")
        if short_sleep:
            actions.extend([
                "Verify the log. Was this your full sleep period, a nap, or a partial recording?",
                "Check alertness. Tell the crew lead before critical work if you feel too fatigued to do it safely.",
                "Follow up. Log the next planned sleep episode. Discuss ongoing short sleep or impairment with crew medical.",
            ])
        elif not fast:
            actions.append("Review persistent changes or symptoms with the crew medical officer before critical work.")
        if attached and review != "routine":
            actions.append("Request human review of the image and record the reviewer’s assessment.")
        if checkin.get("injury_path"):
            actions.append("Share the injury photo with the crew medical officer through the mission procedure.")
        result = {
            "status": "yellow", "title": ("Contact crew medical officer" if fast else
                "Short sleep · Check fatigue" if short_sleep and not repeat_guides else
                "Hold on. Let’s check that again." if repeat_guides else "A closer look would help"),
            "guide": watch[0][1], "repeat_guides": repeat_guides, "short_sleep": short_sleep,
            "rationale": reasons, "actions": actions,
            "recheck": "Now, as directed by the crew medical officer." if fast
            else "Log the next planned sleep episode." if short_sleep and not repeat_guides
            else "Next demo check-in in 4 hours, or when the medical officer directs.",
            "next_hours": 0 if fast else None if short_sleep and not repeat_guides else 4,
        }
    else:
        result = {
            "status": "green", "title": "Continue the daily check-in", "guide": "sleep",
            "rationale": ["The entered readings did not trigger the demo follow-up rules.", *reasons],
            "actions": ["Keep the next scheduled daily check-in.", "Log a new check-in if symptoms or readings change."],
            "recheck": "Next scheduled check-in in 24 hours in the demo.", "next_hours": 24,
        }

    model_values = {**values, "pulse": None} if pulse_after_effort else values
    return {
        **result, "modalities": modalities, "flagged_metrics": list(dict.fromkeys(flagged_metrics)),
        "model": local_insight(model_values, schedule_change, model_path) if include_model else None,
        "missing": missing, "invalid": invalid, "baseline": baseline,
        "sources": [SOURCE_CREW_MEDICINE, SOURCE_SLEEP, SOURCE_BP, SOURCE_ULTRASOUND],
    }


def self_test():
    routine = {"sleep": 7.4, "fatigue": 2, "mood": 4, "pulse": 64, "systolic": 116,
               "diastolic": 76, "temperature": 36.7, "urgent": False}
    assert analyze(routine)["status"] == "green"
    assert analyze(dict(routine, sleep=5, fatigue=4))["status"] == "yellow"
    assert analyze(dict(routine, urgent=True))["status"] == "red"
    assert analyze({"urgent": True})["status"] == "red"
    assert analyze({})["status"] == "yellow"
    assert analyze(dict(routine, systolic=185))["next_hours"] == 0
    assert analyze(dict(routine, temperature="NaN"))["invalid"] == ["temperature"]
    assert analyze(dict(routine, systolic=65))["invalid"] == ["systolic", "diastolic"]
    assert analyze(dict(routine, ultrasound_path="scan.png"))["guide"] == "ultrasound"
    assert analyze(dict(routine, ultrasound_review="urgent"))["status"] == "red"
    assert analyze(dict(routine, notes="Pulse checked after exercise."))["guide"] == "pulse"
    assert analyze(dict(routine, notes="No pulse reading was taken after exercise."))["status"] == "green"
    assert analyze(dict(routine, pulse=107))["model"]["probability"] is None
    prior = [dict(routine, pulse=60)] * 4
    assert analyze(dict(routine, pulse=83), prior)["status"] == "yellow"
    assert analyze(routine, model_path="nonexistent-model.json")["status"] == "green"
    if MODEL_FILE.exists():
        assert analyze(routine)["model"]["probability"] is not None
    print("Aboard local analysis checks passed.")


if __name__ == "__main__":
    self_test()
