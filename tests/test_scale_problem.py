"""Tests for detect_scale_problem: property 5 and unit tests."""

import pytest
from hypothesis import given, settings, strategies as st

from helpers import make_click, make_mismatch
from poltergeist.detection import detect_mismatches, detect_scale_problem


# Feature: human-action-log, Property 5: Scale Factor Recovery
@settings(max_examples=100)
@given(
    st.floats(min_value=0.25, max_value=6.0, allow_nan=False),
    st.lists(
        st.tuples(
            st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
            st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
        ),
        min_size=3,
        max_size=8,
    ),
)
def test_scale_factor_is_recovered(k, human_positions):
    # The human corrects each agent click at agent_position / k. Positions are
    # generated on the human side so every human coordinate is at least 1.0.
    log = []
    for index, (human_x, human_y) in enumerate(human_positions):
        start = index * 10_000
        log.append(make_click("agent", start, human_x * k, human_y * k))
        log.append(make_click("human", start + 1000, human_x, human_y))

    problem = detect_scale_problem(detect_mismatches(log))

    assert problem is not None
    assert problem.sample_size == len(human_positions)
    assert problem.scale_x == pytest.approx(k, rel=0.01)
    assert problem.scale_y == pytest.approx(k, rel=0.01)


def test_three_consistent_two_x_mismatches_flag_a_problem():
    mismatches = [
        make_mismatch(200, 400, 100, 200),
        make_mismatch(300, 600, 150, 300),
        make_mismatch(100, 200, 50, 100),
    ]
    problem = detect_scale_problem(mismatches)
    assert problem is not None
    assert problem.sample_size == 3
    assert problem.scale_x == pytest.approx(2.0)
    assert problem.scale_y == pytest.approx(2.0)


def test_inconsistent_ratios_do_not_flag_a_problem():
    mismatches = [
        make_mismatch(100, 100, 100, 100),
        make_mismatch(200, 200, 100, 100),
        make_mismatch(300, 300, 100, 100),
    ]
    assert detect_scale_problem(mismatches) is None


def test_two_mismatches_are_not_enough():
    mismatches = [
        make_mismatch(200, 400, 100, 200),
        make_mismatch(300, 600, 150, 300),
    ]
    assert detect_scale_problem(mismatches) is None


def test_near_zero_human_coordinates_are_excluded():
    mismatches = [
        make_mismatch(200, 400, 100, 200),
        make_mismatch(300, 600, 150, 300),
        make_mismatch(100, 200, 50, 100),
        make_mismatch(10, 10, 0.5, 5),
    ]
    problem = detect_scale_problem(mismatches)
    assert problem is not None
    assert problem.sample_size == 3


def test_a_sample_is_skipped_when_only_one_axis_is_near_zero():
    mismatches = [
        make_mismatch(200, 400, 100, 200),
        make_mismatch(300, 600, 150, 300),
        make_mismatch(10, 10, 5, 0.2),
    ]
    assert detect_scale_problem(mismatches) is None


def test_all_near_zero_produces_no_problem():
    mismatches = [make_mismatch(10, 10, 0.1, 0.2) for _ in range(5)]
    assert detect_scale_problem(mismatches) is None


def test_no_mismatches_produces_no_problem():
    assert detect_scale_problem([]) is None


def test_negative_mean_does_not_hide_a_large_spread():
    mismatches = [
        make_mismatch(-100, -100, 100, 100),
        make_mismatch(-200, -200, 100, 100),
        make_mismatch(-300, -300, 100, 100),
    ]
    assert detect_scale_problem(mismatches) is None
