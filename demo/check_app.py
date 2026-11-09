"""Check the phone's mini app in demo/index.html, without a browser.

Runs the app's pure functions in Node: the screens, taps, swipes, and the exact
story the page tells (a 1.5x coordinate bug lands each agent tap somewhere
harmless or wrong, a human tap on the intended spot puts it right, and the same
steps with the bug removed finish the task). Needs Node.js. From the repository root:

    python demo/check_app.py
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = """
const assert = require('assert');
%APP%
const center = id => { const e = elementsFor(app).find(e => e.id === id); return [e.x + e.w / 2, e.y + e.h / 2]; };
let app = initialApp();
const BUG = 1.5;

// Each agent tap, read 1.5x too big, lands where the story says; a human tap on the dot fixes it.
const story = [
  ['chat-maya', 'hdr-earlier', a => a.screen === 'thread' && a.chat === 'Maya Chen'],
  ['share', null, a => a.screen === 'photos'],
  ['tile-beach', 'tile-city', a => a.selected === 'beach'],
];
for (const [id, landsOn, fixed] of story) {
  assert.strictEqual(policy(app).id, id, 'policy picks ' + id);
  const [cx, cy] = center(id);
  const miss = tapApp(app, cx * BUG, cy * BUG);
  assert.ok(!miss.off, id + ' stays on screen');
  assert.strictEqual(miss.hit && miss.hit.id, landsOn, id + ' lands on ' + landsOn);
  assert.ok(!worked(miss.app, id), id + ' did not work');
  app = miss.app;
  app = tapApp(app, cx + 3, cy - 2).app;
  assert.ok(fixed(app), 'human tap fixed ' + id);
}
// With the bug divided out, the agent finishes alone.
for (const id of ['done', 'sendbtn']) {
  assert.strictEqual(policy(app).id, id);
  const [cx, cy] = center(id);
  app = tapApp(app, cx * BUG / 1.47, cy * BUG / 1.51).app;
  assert.ok(worked(app, id), id + ' worked');
}
assert.ok(taskDone(app) && policy(app) === null, 'task done');

// Free play: pages, switches, dialogs, back gestures.
app = initialApp();
app = swipeApp(app, 330, 400, 120, 410).app;             assert.strictEqual(app.screen, 'settings');
app = tapApp(app, 215, 146).app;                          assert.strictEqual(app.toggles.notif, false);
app = tapApp(app, 215, 354).app;                          assert.ok(app.alert);
assert.strictEqual(tapApp(app, 215, 146).app.toggles.notif, false, 'a dialog blocks the page behind it');
app = tapApp(app, 300, 500).app;                          assert.ok(!app.alert && app.toast);
app = swipeApp(app, 120, 400, 340, 410).app;              assert.strictEqual(app.screen, 'chats');
app = tapApp(app, 215, 310).app;                          assert.strictEqual(app.chat, 'Dev Team');
app = swipeApp(app, 20, 500, 220, 505).app;               assert.strictEqual(app.screen, 'chats');
assert.strictEqual(swipeApp(app, 200, 500, 240, 500).did, null, 'a short drag is not a swipe');
assert.ok(tapApp(app, -5, 100).off && tapApp(app, 100, 1000).off, 'taps outside the screen do nothing');
console.log('ok');
"""


def main() -> int:
    html = (ROOT / "demo" / "index.html").read_text()
    match = re.search(r"// <app>\n(.*?)// </app>", html, re.S)
    if not match:
        sys.exit("could not find the <app> block in demo/index.html")
    result = subprocess.run(["node", "-e", SCRIPT.replace("%APP%", match.group(1))], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        return 1
    print("the phone's app behaves as the page describes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
