"""Tests for detect_mismatches: properties 2, 3, 4, 6 and unit tests."""

import math

from hypothesis import given, settings, strategies as st

from helpers import make_click
from poltergeist.detection import detect_mismatches

coordinate = st.floats(min_value=-2000, max_value=2000, allow_nan=False)

# A chronological log: each entry is (actor, gap in ms since previous click, x, y).
log_entries = st.lists(
    st.tuples(
        st.sampled_from(["agent", "human"]),
        st.integers(min_value=0, max_value=3000),
        coordinate,
        coordinate,
    ),
    max_size=40,
)


def build_log(entries):
    clicks = []
    now = 0
    for actor, gap, x, y in entries:
        now += gap
        clicks.append(make_click(actor, now, x, y))
    return clicks


# Feature: human-action-log, Property 2: One-to-One Human Click Matching
@settings(max_examples=100)
@given(log_entries)
def test_each_human_click_matches_at_most_one_agent_click(entries):
    mismatches = detect_mismatches(build_log(entries))
    human_ids = [id(m.human_click) for m in mismatches]
    assert len(human_ids) == len(set(human_ids))


# Feature: human-action-log, Property 3: One-to-One Agent Click Matching
@settings(max_examples=100)
@given(log_entries)
def test_each_agent_click_matches_at_most_one_human_click(entries):
    mismatches = detect_mismatches(build_log(entries))
    agent_ids = [id(m.agent_click) for m in mismatches]
    assert len(agent_ids) == len(set(agent_ids))


# Feature: human-action-log, Property 4: Minimum Distance Matching
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=4999),
            coordinate,
            coordinate,
        ),
        min_size=2,
        max_size=5,
        unique_by=lambda item: item[0],
    ),
    coordinate,
    coordinate,
)
def test_matched_agent_click_is_closest_candidate(agent_specs, human_x, human_y):
    human_time = 10_000
    agents = [
        make_click("agent", human_time - age_ms, x, y) for age_ms, x, y in agent_specs
    ]
    agents.sort(key=lambda click: click.timestamp)
    log = agents + [make_click("human", human_time, human_x, human_y)]

    mismatches = detect_mismatches(log)

    assert len(mismatches) == 1
    smallest = min(
        math.hypot(human_x - a.normalized_x, human_y - a.normalized_y) for a in agents
    )
    assert mismatches[0].distance == smallest


# Feature: human-action-log, Property 6: Temporal Window Boundary
@settings(max_examples=100)
@given(
    st.integers(min_value=5000, max_value=600_000),
    coordinate,
    coordinate,
    coordinate,
    coordinate,
)
def test_no_mismatch_when_human_click_is_five_seconds_or_more_later(
    delay_ms, agent_x, agent_y, human_x, human_y
):
    log = [
        make_click("agent", 0, agent_x, agent_y),
        make_click("human", delay_ms, human_x, human_y),
    ]
    assert detect_mismatches(log) == []


def test_agent_click_followed_two_seconds_later_creates_mismatch():
    log = [make_click("agent", 0, 100, 200), make_click("human", 2000, 110, 190)]
    mismatches = detect_mismatches(log)
    assert len(mismatches) == 1
    assert mismatches[0].offset_x == 10
    assert mismatches[0].offset_y == -10


def test_agent_click_followed_six_seconds_later_creates_no_mismatch():
    log = [make_click("agent", 0, 100, 200), make_click("human", 6000, 110, 190)]
    assert detect_mismatches(log) == []


def test_human_click_without_prior_agent_click_creates_no_mismatch():
    assert detect_mismatches([make_click("human", 1000, 5, 5)]) == []


def test_closest_of_several_agent_clicks_is_matched():
    far = make_click("agent", 1000, 0, 0)
    near = make_click("agent", 2000, 98, 99)
    human = make_click("human", 3000, 100, 100)
    mismatches = detect_mismatches([far, near, human])
    assert len(mismatches) == 1
    assert mismatches[0].agent_click is near


def test_agent_click_matched_once_is_not_matched_again():
    agent = make_click("agent", 0, 50, 50)
    first = make_click("human", 1000, 60, 60)
    second = make_click("human", 2000, 70, 70)
    mismatches = detect_mismatches([agent, first, second])
    assert len(mismatches) == 1
    assert mismatches[0].human_click is first


def test_identical_positions_create_zero_offset_mismatch():
    log = [make_click("agent", 0, 40, 80), make_click("human", 1000, 40, 80)]
    mismatches = detect_mismatches(log)
    assert len(mismatches) == 1
    assert mismatches[0].offset_x == 0
    assert mismatches[0].offset_y == 0
    assert mismatches[0].distance == 0


def test_exact_five_second_boundary_is_excluded():
    log = [make_click("agent", 0, 1, 1), make_click("human", 5000, 1, 1)]
    assert detect_mismatches(log) == []


def test_just_under_five_seconds_is_included():
    log = [make_click("agent", 0, 1, 1), make_click("human", 4999, 1, 1)]
    assert len(detect_mismatches(log)) == 1


def test_agent_click_after_human_click_is_not_matched():
    log = [make_click("human", 1000, 1, 1), make_click("agent", 2000, 1, 1)]
    assert detect_mismatches(log) == []


def test_distance_never_rejects_a_far_pair():
    log = [make_click("agent", 0, 0, 0), make_click("human", 1000, 5000, 5000)]
    assert len(detect_mismatches(log)) == 1
