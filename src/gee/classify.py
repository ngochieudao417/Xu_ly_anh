"""
Task 3.5-3.7: train Random Forest (2 phuong an), tinh Kappa/OA/confusion
matrix, so sanh va chon phuong an thang.
"""

from __future__ import annotations

import ee

from src.gee import config as gcfg

N_TREES = 200


def train_rf(train_fc: "ee.FeatureCollection", feature_names: list[str]) -> "ee.Classifier":
    classifier = ee.Classifier.smileRandomForest(numberOfTrees=N_TREES, seed=gcfg.SAMPLE_SEED)
    return classifier.train(features=train_fc, classProperty=gcfg.CLASS_COL, inputProperties=feature_names)


def evaluate(classifier: "ee.Classifier", test_fc: "ee.FeatureCollection", feature_names: list[str]) -> dict:
    """Ap classifier len tap test, tra ve OA, Kappa, confusion matrix (list-of-list), va per-class producer/consumer accuracy."""
    classified = test_fc.classify(classifier)
    error_matrix = classified.errorMatrix(gcfg.CLASS_COL, "classification")
    result = {
        "overall_accuracy": error_matrix.accuracy().getInfo(),
        "kappa": error_matrix.kappa().getInfo(),
        "confusion_matrix": error_matrix.array().getInfo(),
        "producers_accuracy": [v[0] for v in error_matrix.producersAccuracy().getInfo()],
        "consumers_accuracy": error_matrix.consumersAccuracy().getInfo()[0],
        "order": sorted(gcfg.CLASS_MAP.keys()),
    }
    return result


def variable_importance(classifier: "ee.Classifier") -> dict:
    return classifier.explain().getInfo().get("importance", {})
