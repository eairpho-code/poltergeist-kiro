"""Shared builders for detection tests."""

from datetime import datetime, timedelta, timezone

from poltergeist.action_log import ClickAction, Mismatch

BASE_TIME = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)


def timestamp_at(ms: int) -> str:
    """ISO 8601 UTC timestamp `ms` milliseconds after BASE_TIME."""
    moment = BASE_TIME + timedelta(milliseconds=ms)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_click(actor: str, ms: int, x: float, y: float) -> ClickAction:
    """A click already in device points, at `ms` milliseconds after BASE_TIME."""
    return ClickAction(
        timestamp=timestamp_at(ms),
        actor=actor,
        normalized_x=x,
        normalized_y=y,
        raw_x=x,
        raw_y=y,
        coordinate_space="device_points",
        scale_factor=1.0,
    )


def make_mismatch(agent_x, agent_y, human_x, human_y) -> Mismatch:
    """A Mismatch between an agent click and the human click that followed it."""
    agent = make_click("agent", 0, agent_x, agent_y)
    human = make_click("human", 1000, human_x, human_y)
    return Mismatch(
        agent_click=agent,
        human_click=human,
        offset_x=human_x - agent_x,
        offset_y=human_y - agent_y,
        distance=((human_x - agent_x) ** 2 + (human_y - agent_y) ** 2) ** 0.5,
    )
