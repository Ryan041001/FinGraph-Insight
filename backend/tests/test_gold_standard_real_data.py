import json
from pathlib import Path


def test_gold_standard_contains_50_sourced_real_samples():
    path = Path(__file__).resolve().parents[2] / "data" / "gold" / "gold_standard.json"
    samples = json.loads(path.read_text(encoding="utf-8"))

    assert len(samples) >= 50
    first_50 = samples[:50]
    assert all(sample["id"].startswith("gold_real_") for sample in first_50)
    assert all(sample.get("source") for sample in first_50)
    assert all(str(sample.get("url", "")).startswith("http") for sample in first_50)
    assert all(sample.get("entities") for sample in first_50)
    assert all(sample.get("relationships") for sample in first_50)
