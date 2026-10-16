from __future__ import annotations

from pathlib import Path

import numpy as np

from app.extraction.preprocess import preprocess_image, upscale_to_long_edge, deskew

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "extraction"


def test_preprocess_png_runs():
    bgr = preprocess_image(FIXTURES / "northvale_page1.png", do_perspective=False)
    assert bgr.ndim == 3
    assert bgr.shape[0] > 100 and bgr.shape[1] > 100


def test_upscale_small_image():
    small = np.zeros((100, 80, 3), dtype=np.uint8)
    out = upscale_to_long_edge(small, long_edge=400)
    assert max(out.shape[0], out.shape[1]) == 400


def test_deskew_noop_on_blank():
    blank = np.full((200, 200, 3), 255, dtype=np.uint8)
    out = deskew(blank)
    assert out.shape == blank.shape
