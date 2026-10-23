"""Numerical calibration, immutable preprocessing and detector contract tests."""
from __future__ import annotations

import joblib
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image, ImageDraw

from linesight.features import ReferenceFeatures, image_array, synthetic_defect
from linesight.model import Detector, upper_threshold

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def nominal_images():
    images = []
    rng = np.random.default_rng(124)
    for index in range(8):
        array = np.clip(rng.normal(125, 1.8, (192, 192, 3)), 0, 255).astype(np.uint8)
        image = Image.fromarray(array)
        draw = ImageDraw.Draw(image)
        draw.ellipse((48, 48, 144, 144), outline=(65 + index, 65 + index, 65 + index), width=5)
        images.append(image)
    return images


@pytest.fixture(scope="module")
def detector(nominal_images):
    fitted = Detector.fit(nominal_images, {
        "representation": "patch", "aggregation": "top4", "n_estimators": 24, "max_samples": 128,
    }, seed=42)
    fitted.threshold = 0.7
    fitted.model_version = "unit-test-frozen"
    return fitted


def test_calibration_order_statistic_and_exchangeable_rank_coverage():
    # For 42 calibration scores, rank41 gives at most2/43 future nominal exceedances.
    threshold, rank = upper_threshold(np.arange(42), alpha=0.05)
    assert (threshold, rank) == (40.0, 41)
    future_exceedances = []
    for future in range(43):
        calibration = np.delete(np.arange(43), future)
        cut, _ = upper_threshold(calibration, 0.05)
        future_exceedances.append(future > cut)
    assert sum(future_exceedances) == 2
    assert np.mean(future_exceedances) <= 0.05


def test_small_calibration_requires_infinite_threshold_and_ties_are_conservative():
    threshold, rank = upper_threshold(np.arange(5), alpha=0.05)
    assert np.isinf(threshold) and rank == 6
    threshold, _ = upper_threshold(np.ones(42), 0.05)
    assert threshold == 1.0
    assert not np.any(np.ones(42) > threshold)


@pytest.mark.parametrize("scores,alpha", [([], .05), ([np.nan], .05), ([np.inf], .05),
                                         ([[1, 2]], .05), ([1, 2], 0), ([1, 2], 1)])
def test_invalid_calibration_inputs_fail_explicitly(scores, alpha):
    with pytest.raises(ValueError):
        upper_threshold(np.asarray(scores), alpha)


def test_reference_transform_cannot_learn_from_future_images(nominal_images):
    reference = ReferenceFeatures.fit(nominal_images)
    before = [x.copy() for x in (reference.median, reference.scale, reference.gradient_median, reference.gradient_scale)]
    patch, global_features, residual = reference.transform(Image.new("RGB", (900, 900), "white"))
    assert patch.shape == (144, 16)
    assert global_features.shape == (56,)
    assert residual.shape == (12, 12)
    assert np.isfinite(patch).all() and np.isfinite(global_features).all()
    for actual, expected in zip((reference.median, reference.scale, reference.gradient_median, reference.gradient_scale), before):
        np.testing.assert_array_equal(actual, expected)


def test_detector_score_matches_forest_anomaly_direction_and_top_patch_aggregation(detector, nominal_images):
    image = synthetic_defect(nominal_images[0], seed=918, kind=1)
    patches = detector.reference.transform(image)[0]
    independently_scored = -detector.forest.score_samples(patches)
    expected = np.sort(independently_scored)[-4:].mean()
    result = detector.inspect(image)
    assert result["score"] == pytest.approx(expected, abs=1e-12)
    np.testing.assert_allclose(np.asarray(result["heatmap"]).reshape(-1), independently_scored, atol=1e-12)
    assert 0 < result["score"] < 1
    assert result["score_is_probability"] is False


def test_injected_local_fault_raises_normal_reference_evidence(nominal_images):
    reference = ReferenceFeatures.fit(nominal_images)
    normal = reference.transform(nominal_images[0])[2]
    altered = nominal_images[0].copy()
    ImageDraw.Draw(altered).rectangle((80, 80, 111, 111), fill="white")
    defect = reference.transform(altered)[2]
    assert defect[5:7, 5:7].mean() > normal[5:7, 5:7].mean() + 3.0


def test_inference_serialization_roundtrip_preserves_decision_and_heatmap(detector, nominal_images, tmp_path):
    image = nominal_images[3]
    original = detector.inspect(image)
    target = tmp_path / "trusted.joblib"
    detector.save(target)
    restored = Detector.load(target).inspect(image)
    for key in ("score", "threshold", "is_anomaly", "heatmap", "model_version", "heatmap_kind", "score_is_probability"):
        assert restored[key] == original[key]
    assert original["is_anomaly"] is (original["score"] > original["threshold"])
    assert set(original["timing_ms"]) == {"features_ms", "forest_ms", "total_ms"}
    assert all(value >= 0 for value in original["timing_ms"].values())


def test_untrusted_artifact_shape_is_rejected(tmp_path):
    path = tmp_path / "wrong-type.joblib"
    joblib.dump({"pretend": "model"}, path)
    with pytest.raises(ValueError, match="Detector"):
        Detector.load(path)


def test_color_mode_preprocessing_and_proxy_generation_are_deterministic(nominal_images):
    image = nominal_images[0]
    original = np.asarray(image).copy()
    a = synthetic_defect(image, 421, 0)
    b = synthetic_defect(image, 421, 0)
    np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    np.testing.assert_array_equal(np.asarray(image), original)
    assert np.any(np.asarray(a) != original)
    for mode in ("L", "RGBA", "RGB"):
        output = image_array(image.convert(mode))
        assert output.shape == (192, 192, 3)
        assert output.dtype == np.float32
        assert 0 <= output.min() <= output.max() <= 1


def test_reference_refuses_insufficient_nominal_examples(nominal_images):
    with pytest.raises(ValueError, match="At least five"):
        ReferenceFeatures.fit(nominal_images[:4])


def test_uncalibrated_model_cannot_return_a_serving_decision(detector, nominal_images):
    unfrozen = Detector(detector.reference, detector.forest)
    with pytest.raises(ValueError, match="not been calibrated"):
        unfrozen.inspect(nominal_images[0])


def test_image_forest_retains_distinct_residual_evidence_semantics(nominal_images):
    fitted = Detector.fit(nominal_images, {
        "representation": "image", "n_estimators": 12, "max_samples": 8,
    })
    fitted.threshold = 0.6
    result = fitted.inspect(nominal_images[0])
    expected_score = -fitted.forest.score_samples(fitted.reference.transform(nominal_images[0])[1][None])[0]
    assert result["score"] == pytest.approx(expected_score)
    assert result["heatmap_kind"] == "reference_residual"
    np.testing.assert_allclose(result["heatmap"], fitted.reference.transform(nominal_images[0])[2])


def test_persisted_artifact_and_calibration_are_bound_to_the_frozen_run():
    artifact = ROOT / "artifacts/linesight.joblib"
    frozen_path = ROOT / "reports/frozen_model.json"
    if not artifact.is_file() or not frozen_path.is_file():
        pytest.skip("Training has not produced the frozen demonstration artifact yet")
    frozen = json.loads(frozen_path.read_text())
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == frozen["artifact_sha256"]
    assert hashlib.sha256((ROOT / "data/manifest.csv").read_bytes()).hexdigest() == frozen["dataset_manifest_sha256"]
    fitted = Detector.load(artifact)
    assert fitted.model_version == frozen["model_version"]
    assert fitted.metadata["selection_real_test_used"] is False
    assert fitted.metadata["threshold_real_test_used"] is False
    assert fitted.forest.n_estimators == frozen["config"]["n_estimators"]
    with (ROOT / "reports/calibration_scores.csv").open(newline="") as handle:
        calibration = list(csv.DictReader(handle))
    assert len(calibration) == 42
    scores = sorted(float(row["score"]) for row in calibration)
    assert fitted.threshold == scores[40] == frozen["calibration"]["threshold"]
    hashes = frozen["development_hashes"]
    assert len(set(hashes["fit"]) & set(hashes["tune"])) == 0
    assert len(set(hashes["fit"]) & set(hashes["calibration"])) == 0
    assert len(set(hashes["tune"]) & set(hashes["calibration"])) == 0


def test_reported_metrics_reconcile_with_every_frozen_test_prediction():
    metrics_path = ROOT / "reports/metrics.json"
    predictions_path = ROOT / "reports/test_predictions.csv"
    if not metrics_path.is_file() or not predictions_path.is_file():
        pytest.skip("Frozen benchmark evaluation has not produced its prediction evidence yet")
    metrics = json.loads(metrics_path.read_text())
    with predictions_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == metrics["test_count"] == 83
    assert {row["model_version"] for row in rows} == {metrics["model_version"]}
    confusion = [[0, 0], [0, 0]]
    normal_scores, defect_scores = [], []
    for row in rows:
        label = int(row["label"])
        score = float(row["score"])
        prediction = score > float(row["threshold"])
        assert row["is_anomaly"] == str(prediction)
        assert row["correct"] == str(prediction == bool(label))
        assert float(row["threshold"]) == metrics["threshold"]
        confusion[label][int(prediction)] += 1
        (defect_scores if label else normal_scores).append(score)
    assert confusion == metrics["confusion_matrix"]
    tn, fp = confusion[0]
    fn, tp = confusion[1]
    assert metrics["precision"] == pytest.approx(tp / (tp + fp))
    assert metrics["recall"] == pytest.approx(tp / (tp + fn))
    assert metrics["f1"] == pytest.approx(2 * tp / (2 * tp + fp + fn))
    assert metrics["false_positive_rate"] == pytest.approx(fp / (fp + tn))
    # Pairwise probability definition independently checks sklearn's ROC integration.
    pairwise_wins = sum((a > b) + 0.5 * (a == b) for a in defect_scores for b in normal_scores)
    assert metrics["auroc"] == pytest.approx(pairwise_wins / (len(defect_scores) * len(normal_scores)))
    assert metrics["selection_and_calibration_use_real_test"] is False
    assert metrics["score_is_probability"] is False
