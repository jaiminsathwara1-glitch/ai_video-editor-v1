"""
Unit tests for CV analyser (no video file required — uses synthetic frames).
"""
import numpy as np
import pytest
from app.ai.cv_analyser import (
    _blur_score,
    _shake_score,
    _exposure_score,
    _perceptual_hash,
    hamming_distance,
    find_duplicates,
)


def make_frame(value: int, size: int = 64) -> np.ndarray:
    """Create a uniform gray frame."""
    return np.full((size, size), value, dtype=np.uint8)


def make_noise_frame(size: int = 64) -> np.ndarray:
    """High-frequency noise → very sharp (high Laplacian variance)."""
    return np.random.randint(0, 255, (size, size), dtype=np.uint8)


class TestBlurScore:
    def test_uniform_frame_is_blurry(self):
        frames = [make_frame(128) for _ in range(5)]
        score = _blur_score(frames)
        assert score < 1.0  # near zero variance

    def test_noisy_frame_is_sharp(self):
        frames = [make_noise_frame() for _ in range(5)]
        score = _blur_score(frames)
        assert score > 500  # high Laplacian variance


class TestExposureScore:
    def test_perfect_exposure(self):
        frames = [make_frame(128) for _ in range(5)]
        score, is_over, is_under = _exposure_score(frames)
        assert score > 8.0
        assert not is_over
        assert not is_under

    def test_overexposed(self):
        frames = [make_frame(250) for _ in range(5)]
        score, is_over, is_under = _exposure_score(frames)
        assert is_over

    def test_underexposed(self):
        frames = [make_frame(10) for _ in range(5)]
        score, is_over, is_under = _exposure_score(frames)
        assert is_under


class TestPerceptualHash:
    def test_same_frame_same_hash(self):
        frame = make_frame(100)
        h1 = _perceptual_hash(frame)
        h2 = _perceptual_hash(frame)
        assert h1 == h2

    def test_different_frames_different_hash(self):
        h1 = _perceptual_hash(make_frame(50))
        # use noise frame which will have gradients
        np.random.seed(42)
        h2 = _perceptual_hash(make_noise_frame())
        assert h1 != h2


class TestDuplicateDetection:
    def test_identical_hashes_are_duplicates(self):
        hashes = {"clip_a": "abc123", "clip_b": "abc123"}
        pairs = find_duplicates(hashes, threshold=0)
        assert ("clip_a", "clip_b") in pairs

    def test_very_different_hashes_not_duplicates(self):
        # All zeros vs all ones (256-bit hamming distance)
        hashes = {
            "clip_a": "0" * 16,
            "clip_b": "f" * 16,
        }
        pairs = find_duplicates(hashes, threshold=8)
        assert len(pairs) == 0
