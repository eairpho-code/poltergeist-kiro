"""Pure detection functions for the human action log.

Two algorithms live here, both implemented as pure functions that take their
input explicitly and never read the system clock:

- ``detect_mismatches`` pairs each human click with the agent click it most
  likely corrected (the closest unmatched agent click within the preceding
  five seconds).
- ``detect_scale_problem`` looks across a set of mismatches for a consistent
  scaling ratio, which suggests a systematic coordinate transformation bug.

These functions operate on the dataclasses defined in
``poltergeist.action_log`` and are the subject of the stage 2 tests
(``tests/test_mismatch.py`` and ``tests/test_scale_problem.py``).
"""

import math
from datetime import datetime
from typing import List, Optional

from poltergeist.action_log import (
    ClickAction,
    CoordinateScaleProblem,
    Mismatch,
)

# The mismatch window: an agent click counts only when it happened strictly
# less than this many seconds before the human click (exclusive boundary).
MISMATCH_WINDOW_SECONDS = 5.0

# A human coordinate with an absolute value below this is treated as "near
# zero" and excluded from scale-ratio calculations (avoids division blow-ups).
NEAR_ZERO = 1.0

# Minimum number of valid scale samples required to flag a scale problem.
MIN_SCALE_SAMPLES = 3

# Maximum relative spread (std_dev / mean) allowed in each dimension.
MAX_RELATIVE_SPREAD = 0.10


def _parse_timestamp(timestamp: str) -> datetime:
    """Parse a UTC ISO 8601 timestamp (trailing 'Z' allowed) to a datetime."""
    normalized = timestamp.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def detect_mismatches(actions: List[ClickAction]) -> List[Mismatch]:
    """Pair human clicks with the agent clicks they most likely corrected.

    For each human click, in chronological order, this finds the closest (by
    Euclidean distance in device points) unmatched agent click that occurred
    strictly within the previous ``MISMATCH_WINDOW_SECONDS`` seconds. Matching
    is one-to-one: every agent click and every human click participates in at
    most one mismatch. There is no distance threshold—any matched pair is a
    mismatch regardless of how far apart the two clicks are.

    Args:
        actions: Click actions. They need not be pre-sorted; this function
            orders them by timestamp internally.

    Returns:
        A list of mismatches, one per matched human click.
    """
    # Work on a time-sorted copy so callers may pass actions in any order.
    # Only clicks take part in pairing; drags (swipes, scrolls, slider moves)
    # are never paired, so they are filtered out before the algorithm runs.
    sorted_actions = sorted(
        (a for a in actions if a.kind == "click"),
        key=lambda click: _parse_timestamp(click.timestamp),
    )

    agent_times = []
    for action in sorted_actions:
        if action.actor == "agent":
            agent_times.append((action, _parse_timestamp(action.timestamp)))

    matched_agents: set[int] = set()
    mismatches: List[Mismatch] = []

    for action in sorted_actions:
        if action.actor != "human":
            continue

        human_time = _parse_timestamp(action.timestamp)
        best_agent: Optional[ClickAction] = None
        best_distance = math.inf

        for agent, agent_time in agent_times:
            if id(agent) in matched_agents:
                continue

            delta_seconds = (human_time - agent_time).total_seconds()
            # Agent must precede the human click (delta > 0) and fall strictly
            # inside the five-second window (delta < 5.0).
            if delta_seconds <= 0 or delta_seconds >= MISMATCH_WINDOW_SECONDS:
                continue

            distance = math.hypot(
                action.normalized_x - agent.normalized_x,
                action.normalized_y - agent.normalized_y,
            )
            if distance < best_distance:
                best_distance = distance
                best_agent = agent

        if best_agent is None:
            continue

        matched_agents.add(id(best_agent))
        mismatches.append(
            Mismatch(
                agent_click=best_agent,
                human_click=action,
                offset_x=action.normalized_x - best_agent.normalized_x,
                offset_y=action.normalized_y - best_agent.normalized_y,
                distance=best_distance,
            )
        )

    return mismatches


def _mean(values: List[float]) -> float:
    return sum(values) / len(values)


def _population_std(values: List[float], mean: float) -> float:
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def detect_scale_problem(
    mismatches: List[Mismatch],
) -> Optional[CoordinateScaleProblem]:
    """Detect a systematic coordinate scaling issue across mismatches.

    For each mismatch the ratios ``scale_x = agent_x / human_x`` and
    ``scale_y = agent_y / human_y`` are computed. Samples whose human
    coordinate is near zero in either dimension (``|coord| < NEAR_ZERO``) are
    skipped, since the ratio would be unstable.

    A problem is flagged only when at least ``MIN_SCALE_SAMPLES`` valid samples
    remain and the relative spread (standard deviation divided by mean) is at
    most ``MAX_RELATIVE_SPREAD`` in both dimensions. A non-positive mean scale
    never qualifies: a legitimate scaling factor is positive, and allowing a
    negative mean could mask a large spread.

    Args:
        mismatches: The mismatches to analyze.

    Returns:
        A ``CoordinateScaleProblem`` when the criteria are met, otherwise
        ``None``.
    """
    scale_xs: List[float] = []
    scale_ys: List[float] = []

    for mismatch in mismatches:
        human_x = mismatch.human_click.normalized_x
        human_y = mismatch.human_click.normalized_y
        if abs(human_x) < NEAR_ZERO or abs(human_y) < NEAR_ZERO:
            continue
        scale_xs.append(mismatch.agent_click.normalized_x / human_x)
        scale_ys.append(mismatch.agent_click.normalized_y / human_y)

    sample_size = len(scale_xs)
    if sample_size < MIN_SCALE_SAMPLES:
        return None

    mean_x = _mean(scale_xs)
    mean_y = _mean(scale_ys)

    # A valid scaling factor is positive; a non-positive mean is not a
    # meaningful scale and must not be reported.
    if mean_x <= 0 or mean_y <= 0:
        return None

    spread_x = _population_std(scale_xs, mean_x) / mean_x
    spread_y = _population_std(scale_ys, mean_y) / mean_y

    if spread_x > MAX_RELATIVE_SPREAD or spread_y > MAX_RELATIVE_SPREAD:
        return None

    return CoordinateScaleProblem(
        sample_size=sample_size,
        scale_x=mean_x,
        scale_y=mean_y,
        spread_x=spread_x,
        spread_y=spread_y,
    )
