"""Watch the human's actions and print one line for each.

``poltergeist-watch`` polls ``GET /human-actions`` and prints a short sentence
for every new human action (clicks, drags and the mismatch a click causes). It
starts from the server's current time, so it never replays history, and it
keeps trying when the server is unreachable.
"""

import argparse
import sys
import time
from typing import Callable, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from poltergeist.activity import describe_activity, scale_changed

DEFAULT_SERVER = "http://127.0.0.1:8000"
DEFAULT_INTERVAL = 0.5


def fetch_human_actions(
    server: str, since: Optional[str] = None, timeout: float = 3.0
) -> dict:
    """Fetch the read route and return its parsed JSON.

    Performs ``GET {server}/human-actions`` with ``since`` as a query parameter
    when given.
    """
    import json

    url = server.rstrip("/") + "/human-actions"
    if since:
        url = url + "?" + urlencode({"since": since})
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class Watcher:
    """Poll a fetch function and report each human action once.

    ``fetch`` takes a ``since`` cursor (or ``None``) and returns the parsed
    read-route payload.
    """

    def __init__(self, fetch: Callable[[Optional[str]], dict]) -> None:
        self._fetch = fetch
        self._cursor: Optional[str] = None
        self._reported_scale: Optional[dict] = None

    def start(self) -> None:
        """Fetch once and remember the server's time, so history is skipped."""
        payload = self._fetch(None)
        self._cursor = payload.get("server_time")
        self._reported_scale = payload.get("coordinate_scale_problem")

    def poll(self) -> List[str]:
        """Fetch new actions since the cursor and describe them.

        The cursor advances to the timestamp of the last human action so each
        action is reported only once.
        """
        payload = self._fetch(self._cursor)
        problem = payload.get("coordinate_scale_problem")
        if scale_changed(self._reported_scale, problem):
            self._reported_scale = problem
        else:
            payload = dict(payload, coordinate_scale_problem=None)
            if problem is None:
                self._reported_scale = None
        lines = describe_activity(payload)

        actions = payload.get("human_actions", [])
        if actions:
            self._cursor = actions[-1]["timestamp"]

        return lines


def run(
    server: str,
    interval: float,
    out=None,
    sleep: Callable[[float], None] = time.sleep,
    max_polls: Optional[int] = None,
) -> None:
    """Watch ``server`` and print a line per human action.

    Prints a banner once, then ``poltergeist: <line>`` for each item. When the
    server cannot be reached it prints one ``cannot reach`` line and keeps
    trying; when it recovers it prints one ``reachable again`` line.
    """
    if out is None:
        out = sys.stdout

    def emit(message: str) -> None:
        print(f"poltergeist: {message}", file=out, flush=True)

    emit(f"watching {server} for human actions in the Simulator")

    watcher = Watcher(lambda since: fetch_human_actions(server, since))

    started = False
    unreachable = False
    polls = 0

    while max_polls is None or polls < max_polls:
        try:
            if not started:
                watcher.start()
                started = True
            else:
                for line in watcher.poll():
                    emit(line)
            if unreachable:
                emit(f"{server} is reachable again")
                unreachable = False
        except Exception:
            if not unreachable:
                emit(f"cannot reach {server}, still trying")
                unreachable = True

        polls += 1
        if max_polls is not None and polls >= max_polls:
            break
        sleep(interval)


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point for ``poltergeist-watch``."""
    parser = argparse.ArgumentParser(
        description="Print a line for each human action in the Simulator."
    )
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    args = parser.parse_args(argv)

    run(args.server, args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
