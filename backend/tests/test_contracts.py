"""Sanity checks on the contract samples everyone builds against."""

import json
from pathlib import Path

import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
SAMPLES = sorted(CONTRACTS_DIR.glob("*.sample.json"))


def _reject_constant(name: str):
    raise ValueError(f"{name} is not valid JSON (the browser's JSON.parse rejects it)")


def test_all_six_samples_exist():
    assert len(SAMPLES) == 6


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_sample_is_strict_json(path: Path):
    # parse_constant fires on NaN / Infinity / -Infinity, which Python accepts but browsers don't
    json.loads(path.read_text(), parse_constant=_reject_constant)
