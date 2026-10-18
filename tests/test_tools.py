"""Tests for lookup and calculate. They do not need an API key."""

import time

import pytest

from tools import calculate, lookup


# ---------------------------------------------------------------- lookup ---

def test_lookup_finds_2025_population():
    result = lookup("Ossbridge", "population_2025")
    assert result["value"] == 52904
    assert result["sources"] == ["NR-01"]


def test_lookup_finds_2020_population_in_another_text_style():
    # Ossford's profile is written differently ("Census population: X in 2020 and Y in 2025")
    assert lookup("Ossford", "population_2020")["value"] == 31560
    assert lookup("Ossford", "population_2025")["value"] == 30982


def test_lookup_misspelled_name_gives_suggestions():
    result = lookup("Ossbrige", "area_km2")
    assert "error" in result
    assert "Ossbridge" in result["error"]


def test_lookup_similar_names_are_not_mixed():
    ossbridge = lookup("Ossbridge", "area_km2")
    ossford = lookup("Ossford", "area_km2")
    assert ossbridge["value"] == 1284.6 and ossbridge["sources"] == ["NR-01"]
    assert ossford["value"] == 846.2 and ossford["sources"] == ["NR-02"]


def test_lookup_ignores_archived_profile():
    # NR-13 (archived 2019) says 4,980 megalitres; the 2025 profile NR-03 says 5,207
    result = lookup("Tarnvale", "water_use_2025_megalitres")
    assert result["value"] == 5207
    assert result["sources"] == ["NR-03"]
    # NR-14 (archived) says 10 schools; the 2025 profile NR-04 says 11
    assert lookup("Kelmarsh", "schools")["value"] == 11


def test_lookup_uses_correction_notice():
    # NR-05 says 912.4, the correction NR-16 says 921.4
    result = lookup("Brightwater", "area_km2")
    assert result["value"] == 921.4
    assert result["sources"] == ["NR-05", "NR-16"]


def test_lookup_correction_does_not_change_other_fields():
    result = lookup("Brightwater", "population_2025")
    assert result["value"] == 44675
    assert result["sources"] == ["NR-05"]


def test_lookup_changes_cubic_metres_to_megalitres():
    # Lindenmoor gives 2,151,400 cubic metres = 2,151.4 megalitres
    result = lookup("Lindenmoor", "water_use_2025_megalitres")
    assert result["value"] == pytest.approx(2151.4)
    assert result["unit"] == "megalitres"


def test_lookup_water_tariff():
    result = lookup(field="water_tariff_2025")
    assert result["value"] == 142.35  # the 2025 tariff, not the 2024 one (131.80)
    assert result["sources"] == ["NR-15"]


def test_lookup_bad_inputs_return_errors_not_crash():
    assert "error" in lookup("Ossbridge", "density")      # unknown field
    assert "error" in lookup(None, "area_km2")            # no district
    assert "error" in lookup("", "area_km2")              # empty district
    assert "error" in lookup(12345, "area_km2")           # not a string
    assert "error" in lookup("x" * 10000, "area_km2")     # very long input


def test_lookup_returns_a_sentence_not_the_whole_document():
    result = lookup("Harrowfield", "pupils_2025_26")
    assert result["value"] == 13904
    assert len(result["sentence"]) < 120


# ------------------------------------------------------------- calculate ---

def test_calculate_simple_division():
    assert calculate("44675 / 921.4")["result"] == pytest.approx(48.486, abs=0.001)


def test_calculate_multiplication_from_the_task():
    assert calculate("48317 * 1.0947")["result"] == pytest.approx(52892.6199)


def test_calculate_brackets_and_minus():
    assert calculate("(71388 - 67214) / 67214 * 100")["result"] == pytest.approx(6.21, abs=0.01)
    assert calculate("-(3) + 5")["result"] == 2


@pytest.mark.parametrize("dangerous", [
    "__import__('os').system('echo hi')",
    "(1).__class__",
    "9**9**9",
])
def test_calculate_refuses_dangerous_input_quickly(dangerous):
    start = time.time()
    result = calculate(dangerous)
    assert "error" in result
    assert time.time() - start < 1  # did not freeze


def test_calculate_division_by_zero():
    assert calculate("1 / 0") == {"error": "division by zero"}
    assert "error" in calculate("0 ** -1")


def test_calculate_too_big_result():
    assert "error" in calculate("10 ** 20")


def test_calculate_refuses_names_strings_and_commas():
    assert "error" in calculate("x + 1")
    assert "error" in calculate("'a' * 3")
    assert "error" in calculate("True + 1")
    assert "commas" in calculate("52,904")["error"]


def test_calculate_bad_text_returns_errors_not_crash():
    assert "error" in calculate("")
    assert "error" in calculate("2 +")
    assert "error" in calculate(None)
    assert "error" in calculate("1" * 500)