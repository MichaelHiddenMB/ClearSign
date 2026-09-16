import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ocr import group_words

from .helpers import render_sign

client = TestClient(app)


def _post(image: bytes, filename: str = "frame.jpg"):
    return client.post("/api/ocr", files={"image": (filename, image, "image/jpeg")})


def _texts(payload: dict) -> list[str]:
    return [line["text"].upper() for line in payload["lines"]]


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_reads_straight_sign():
    response = _post(render_sign(["PLATFORM 2", "Trains to Downtown"]))
    assert response.status_code == 200
    payload = response.json()
    assert "PLATFORM 2" in _texts(payload)
    assert "TRAINS TO DOWNTOWN" in _texts(payload)
    assert all(line["confidence"] >= 60 for line in payload["lines"])
    assert payload["processing_ms"] >= 0


def test_reads_tilted_light_on_dark_sign():
    response = _post(render_sign(["EXIT", "Keep right"], fg="white", bg="#0b3d91", rotate_degrees=5))
    assert response.status_code == 200
    payload = response.json()
    assert "EXIT" in _texts(payload)
    assert "KEEP RIGHT" in _texts(payload)
    assert abs(payload["skew_degrees"]) == pytest.approx(5, abs=1.0)


def test_blank_image_returns_no_lines():
    response = _post(render_sign([" "]))
    assert response.status_code == 200
    assert response.json()["lines"] == []


def test_rejects_non_image():
    response = _post(b"not an image", filename="frame.txt")
    assert response.status_code == 400
    assert "image" in response.json()["detail"].lower()


def test_rejects_empty_upload():
    response = _post(b"")
    assert response.status_code == 400


def test_group_words_filters_low_confidence_and_keeps_line_order():
    data = {
        "text": ["", "PLATFORM", "2", "Trxins", "to", "Downtown"],
        "conf": [-1, 96, 91, 40, 88, 90],
        "block_num": [1, 1, 1, 1, 1, 1],
        "par_num": [1, 1, 1, 1, 1, 1],
        "line_num": [0, 1, 1, 2, 2, 2],
    }
    result = group_words(data, min_confidence=60)
    assert [l.text for l in result.lines] == ["PLATFORM 2", "to Downtown"]
    assert result.lines[0].confidence == 93.5
    assert result.dropped_words == 1
