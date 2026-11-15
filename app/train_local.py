"""Fit and evaluate the Aboard synthetic fatigue-pattern model offline."""

import argparse
import json
import random
from pathlib import Path
from statistics import fmean, pstdev

from analysis import MODEL_FEATURES, MODEL_FILE, MODEL_PULSE_BOUNDS, MODEL_SLEEP_BOUNDS, sigmoid


def dataset(count, seed):
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        sleep = round(rng.uniform(*MODEL_SLEEP_BOUNDS), 1)
        fatigue = rng.randint(1, 5)
        mood = rng.randint(1, 5)
        pulse = rng.randint(*MODEL_PULSE_BOUNDS)
        shift = int(rng.random() < 0.28)
        # A simulated labeling process with overlap between examples. These
        # coefficients were selected to make a teaching dataset and have no
        # interpretation as biomedical effect sizes.
        pattern = (
            0.9 * (6.7 - sleep) + 1.1 * (fatigue - 3) + 0.32 * (3 - mood)
            + 0.026 * (pulse - 70) + 0.65 * shift - 0.25
        )
        label = int(rng.random() < sigmoid(pattern))
        rows.append(((sleep, fatigue, mood, pulse, shift), label))
    return rows


def predict(features, weights, bias):
    return sigmoid(bias + sum(value * weight for value, weight in zip(features, weights)))


def train(seed):
    training = dataset(2400, seed)
    holdout = dataset(600, seed + 1)
    columns = list(zip(*(values for values, _ in training)))
    means = [fmean(column) for column in columns]
    scales = [pstdev(column) for column in columns]

    def standardize(values):
        return tuple((value - mean) / scale for value, mean, scale in zip(values, means, scales))

    normalized = [(standardize(values), label) for values, label in training]
    weights = [0.0] * len(MODEL_FEATURES)
    bias = 0.0
    learning_rate = 0.25
    penalty = 0.005
    for _ in range(140):
        gradient = [0.0] * len(MODEL_FEATURES)
        bias_gradient = 0.0
        for values, label in normalized:
            error = predict(values, weights, bias) - label
            bias_gradient += error
            for index, value in enumerate(values):
                gradient[index] += error * value
        bias -= learning_rate * bias_gradient / len(normalized)
        for index, value in enumerate(gradient):
            weights[index] -= learning_rate * (value / len(normalized) + penalty * weights[index])

    probabilities = [(predict(standardize(values), weights, bias), label) for values, label in holdout]
    accuracy = fmean(int(probability >= 0.5) == label for probability, label in probabilities)
    brier = fmean((probability - label) ** 2 for probability, label in probabilities)
    return {
        "version": 1,
        "features": MODEL_FEATURES,
        "means": means,
        "scales": scales,
        "weights": weights,
        "bias": bias,
        "provenance": "Synthetic generator only. Flight and patient records were not used.",
        "seed": seed,
        "training_examples": len(training),
        "holdout_examples": len(holdout),
        "synthetic_holdout": {"accuracy": round(accuracy, 4), "brier": round(brier, 4)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=MODEL_FILE)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    model = train(args.seed)
    args.output.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    metrics = model["synthetic_holdout"]
    print(f"Wrote {args.output}. Synthetic holdout accuracy {metrics['accuracy']:.1%}, Brier score {metrics['brier']:.3f}.")


if __name__ == "__main__":
    main()
