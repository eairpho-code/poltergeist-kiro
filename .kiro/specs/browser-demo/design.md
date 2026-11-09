# Design Document

## Overview

One file, `demo/index.html`: a full HTML document with a `<style>` and one `<script>`. The script is wrapped in an immediately-invoked function so that none of its names are global, and holds, in this order: the **core** (`// <core>` ... `// </core>`), the **app** (`// <app>` ... `// </app>`), and the page code that uses `document`. Core and app contain no browser objects, so `demo/check_port.py` and `demo/check_app.py` can cut them out of the file by their marker lines and run them in Node.

Two checks are provided and may not be changed: `demo/check_port.py` (the core against the Python modules) and `demo/check_app.py` (the app).

## The core

Times are milliseconds. Constants: `WINDOW_MS = 5000`, `MAX_SPREAD = 0.10`, `MIN_SAMPLES = 3`, `NEAR_ZERO = 1.0`.

- `makeAction(actor, kind, x, y, endX, endY, scale, t)` returns `{actor, kind, t, nx, ny, rawX, rawY, scale, endX, endY}`. `nx` and `ny` are `x / scale` and `y / scale`. For a drag `endX` and `endY` are divided by `scale` too; for a click they are `null`.
- `detectMismatches(actions, windowMs = WINDOW_MS)` returns `[{agent, human, offX, offY, distance}]`. Same algorithm as `poltergeist/detection.py`: clicks only; human clicks in time order; for each, the unmatched agent clicks with `0 < human.t - agent.t < windowMs`; the closest by Euclidean distance in `nx`, `ny` wins, first in list order on ties; one to one.
- `detectScaleProblem(mismatches)` returns `null` or `{sampleSize, scaleX, scaleY, spreadX, spreadY}`. A pair is skipped when a human coordinate is closer to zero than `NEAR_ZERO`. At least `MIN_SAMPLES` pairs are needed, and the population standard deviation divided by the absolute mean must not exceed `MAX_SPREAD` on either axis.
- `relSpread(values)`, `fixed(v, n)` (like Python's `format`: exact ties go to the even digit), `pt(x, y)` (`(1.0, 2.0)`), `signed(v)` (`+1.0`, `-0.5`), `clock(t)` (`HH:MM:SS` of the UTC time).
- `describeAction(action, role)`, `describeMismatch(m)`, `describeScale(p)`: the sentences of `poltergeist/activity.py`.

## The app

Pure functions on a state object. Device points, origin top left, width `SW = 430`, height `SH = 932`.

### State

`{screen, chat, attached, selected, sent, alert, toast, toggles}`: `screen` is `'chats'`, `'settings'`, `'thread'` or `'photos'`; `chat` is a chat name or `null`; `attached` and `selected` are a photo id or `null`; `sent` is `{chat, photo}` or `null`; `alert` is a boolean; `toast` is a string; `toggles` is `{notif: true, receipts: false, airplane: false}`. `initialApp()` returns the state with `screen: 'chats'`.

### Functions

- `elementsFor(app)` returns the elements of the current screen in drawing order. An element is `{id, x, y, w, h, cls, html, st?, hit?, role?, label?}`. `hit` marks the elements a tap can land on. The later an element comes, the higher it is.
- `hitTest(app, x, y)` returns the top-most `hit` element whose rectangle contains the point (edges included), or `null`.
- `perform(app, id)` returns the next state (always a new object, with `toast` cleared and `toggles` copied). `tapApp(app, x, y)` returns `{app, hit, off}`: `off` is true and nothing happens when the point is outside the screen.
- `swipeApp(app, x0, y0, x1, y1)` returns `{app, did}` where `did` is a phrase or `null`. A swipe needs `|dx| >= 70` and `|dx| >= 2 |dy|`, and is ignored while a dialog is open. On `chats`, a swipe left goes to settings (`swiped to Settings`). On `settings`, a swipe right goes to chats (`swiped back to Messages`). On `thread` or `photos`, a swipe right that starts at `x0 < 80` goes back (`swiped back`).
- `describeScreen(app)`: `a dialog asks “Delete all conversations?”`, `the Messages list`, `the Settings page`, `the photo picker, <Name> selected` or `the photo picker, nothing selected`, or `<chat>'s chat` with `, <Name> attached` and `, a photo was sent` appended when true.
- `taskDone(app)`: a photo `beach` was sent to `Maya Chen`.
- `policy(app)`: what the agent wants to tap next, as `{id, label, why}`, or `null`. A dialog open: `alert-cancel`. Something was sent: `null`. On settings: `tab-chats`. On the chat list: `chat-maya`. In the picker: `done` when `beach` is selected, else `tile-beach`. In a thread of another chat: `back`. In Maya's thread: `sendbtn` when `beach` is attached, else `share`.
- `worked(app, id)`: whether the tap of `id` did its job: `chat-maya` leads to Maya's thread; `share` to the picker; `tile-beach` selects beach; `done` leads to a thread with beach attached; `sendbtn` makes `taskDone` true; `back` and `tab-chats` lead to the chat list; `alert-cancel` closes the dialog; any other id is false.
- `screenHtml(app)` returns the elements as markup: for each, a `div` with its `cls` as class, `data-id`, and a `style` holding its box as percentages of 430 x 932 with three decimals (`left`, `top`, `width`, `height`) and, when present, `st`.

### Elements

| Screen | id | role | x | y | w | h | Notes |
|---|---|---|---|---|---|---|---|
| chats | `title` | | 22 | 48 | 300 | 46 | not hit; text `Messages` |
| chats | `hdr-pinned` | | 22 | 96 | 200 | 20 | not hit; text `Pinned` |
| chats | `hdr-earlier` | header | 0 | 200 | 430 | 66 | hit; label `the “Earlier” header`; text `Earlier` |
| chats | `chat-maya` | row | 16 | 118 | 398 | 76 | hit; label `Maya Chen`; opens the thread |
| chats | `chat-dev` | row | 16 | 272 | 398 | 76 | label `Dev Team` |
| chats | `chat-mom` | row | 16 | 354 | 398 | 76 | label `Mom` |
| chats | `chat-delivery` | row | 16 | 436 | 398 | 76 | label `Delivery` |
| chats, settings | `tabbar` | | 0 | 846 | 430 | 86 | not hit |
| chats, settings | `tab-chats` | tab | 0 | 850 | 215 | 70 | label `the Messages tab` |
| chats, settings | `tab-settings` | tab | 215 | 850 | 215 | 70 | label `the Settings tab` |
| settings | `title` | | 22 | 48 | 300 | 46 | text `Settings` |
| settings | `set-notif` | switch | 16 | 118 | 398 | 56 | label `the Notifications switch` |
| settings | `set-receipts` | switch | 16 | 182 | 398 | 56 | `the Read receipts switch` |
| settings | `set-airplane` | switch | 16 | 246 | 398 | 56 | `the Airplane mode switch` |
| settings | `set-delete` | button | 16 | 326 | 398 | 56 | label `“Delete all conversations”`; opens the dialog |
| thread | `back` | button | 8 | 52 | 120 | 40 | label `Back`; text `‹ Messages` |
| thread | `navtitle` | | 130 | 52 | 170 | 40 | not hit; the chat name |
| thread | `sendbtn` | button | 322 | 52 | 92 | 40 | only while a photo is attached; label `Send` |
| thread | `share` | button | 16 | 112 | 398 | 58 | while nothing is attached; label `Share a photo`; opens the picker with the attached photo selected |
| thread | `attached` | attachment | 16 | 112 | 398 | 58 | while a photo is attached; label `the attached photo` |
| thread | `bubble-1` | message | 16 | 186 | 288 | 44 | label `a message` |
| thread | `bubble-2` | message | 16 | 238 | 236 | 44 | label `a message` |
| thread | `sent-photo` | photo | 214 | 296 | 200 | 140 | when something was sent in this chat; label `the sent photo` |
| thread | `delivered` | | 300 | 442 | 114 | 20 | same condition; not hit; text `Delivered` |
| photos | `cancel` | button | 8 | 52 | 90 | 40 | label `Cancel`; back to the thread |
| photos | `navtitle` | | 110 | 52 | 210 | 40 | not hit; `Choose photo` |
| photos | `done` | button | 322 | 52 | 92 | 40 | label `Done`; does nothing until a photo is selected |
| photos | `tile-<photo>` | photo | 16 or 215 | 118 + 148 × row | 199 | 140 | label `the <Name> photo`; photos in order beach, forest, city, sunset, dog, coffee, two per row, even index at x 16 |
| any, when the dialog is open | `scrim` | dialog | 0 | 0 | 430 | 932 | hit, blocks everything behind; label `the dialog backdrop` |
| dialog | `alertbox` | | 60 | 360 | 310 | 170 | not hit |
| dialog | `alert-cancel` | button | 60 | 470 | 155 | 60 | label `Cancel` |
| dialog | `alert-delete` | button | 215 | 470 | 155 | 60 | label `Delete`; closes the dialog with the toast `Demo only: nothing was deleted` |
| any, when `toast` is set | `toast` | | 75 | 796 | 280 | 44 | not hit |

Chats and their messages: Maya Chen (`Did you get any beach photos?`, `Send me the best one!`), Dev Team (`Build is green`, `Ship it?`), Mom (`Call me when you land`, `Love you`), Delivery (`Your parcel is nearby`, `Arriving in 10 minutes`). Photos: Beach, Forest, City, Sunset, Dog, Coffee, each drawn as a colour gradient.

Taps: `chat-*` opens the thread (screen `thread`, the chat's name, nothing attached). `back`, `tab-chats` go to the chat list; `tab-settings` to settings. `tile-<photo>` selects it. `done` attaches the selected photo and returns to the thread. `sendbtn` sets `sent` to the chat and photo, clears `attached` and sets the toast `Sent to <chat>`. A switch flips its toggle. `set-delete` opens the dialog; `alert-cancel` closes it.

### The story the page tells

The agent aims at the centre of the control, times 1.5 on both axes. That lands as follows, so that every miss is harmless or fixable by one tap on the intended control:

| Control | Intended centre | Agent taps | Lands on |
|---|---|---|---|
| `chat-maya` | (215, 156) | (322.5, 234) | `hdr-earlier`, nothing happens |
| `share` | (215, 141) | (322.5, 211.5) | nothing (empty space) |
| `tile-beach` | (115.5, 188) | (173.25, 282) | `tile-city`, the wrong photo is selected |

With the factors measured from those three pairs (about 1.47 and 1.51) divided out, `done` and `sendbtn` (centre (368, 72)) land on their targets.

## The page

### DOM contract

These ids exist, and the checks and the test hook rely on them: `screen` (the phone screen; position is computed from its bounding box), `app` (the app's markup lives here), `wantLayer`, `pairs` (an SVG with viewBox `0 0 430 932`), `botCursor`, `ghostPtr`, `aimRing`, `agentBtn`, `autoBtn`, `resetBtn`, `window` (the status text), `feed`, `told-body`, `verdict`, `tl`, `log` (a table with a `tbody`), `json`, `themeBtn`, `repo`, buttons with `data-win` values 5000, 15000 and 30000, and buttons with `data-copy` naming a `pre`. The phone screen is a container with `aspect-ratio: 430 / 932`, and every size inside it is derived from its width (`100cqw / 430` per device point).

The static markup contains the chat list as `screenHtml(initialApp())` would produce it, the empty state of every panel, and a first line in the feed, so a page without JavaScript is complete.

### Layout and sizing

- `--phoneH = clamp(380px, 100svh - 60px - introH - 34px, 780px)`, with `introH` 156px, 92px below 660px of height. `--phoneW = (phoneH - 22px) / 2.1674 + 22px`. The phone has an 11px bezel. The stage is a grid of `minmax(230px, 1fr) var(--phoneW) minmax(260px, 1fr)`, 28px gap. The agent panel has the height `--phoneH`.
- Breakpoints as in Requirement 4. Max content width 1160px, side gutter at least 16px.

### Look

Colour tokens on `:root`, redefined for dark under `prefers-color-scheme: dark` (unless `data-theme="light"`) and under `data-theme="dark"`. The human is violet, the agent warm orange.

| token | light | dark |
|---|---|---|
| `--bg` | `#eef2f1` | `#0a1110` |
| `--surface` | `#ffffff` | `#111b1a` |
| `--ink` | `#0f1d1c` | `#e6f0ed` |
| `--muted` | `#52676a` | `#93a9a4` |
| `--line` | `#d2dddb` | `#223230` |
| `--human` | `#5836cf` | `#b09dff` |
| `--agent` | `#b84d06` | `#ffb36f` |
| `--warn` | `#b3232b` | `#ff8084` |

Fonts: Bricolage Grotesque (headings, 700 and 800), IBM Plex Sans (text), IBM Plex Mono (code and numbers), from Google Fonts with system fallbacks. The phone uses the system UI font. The ghost mark is a rounded-top body with a wavy bottom and two eyes; the agent is a rounded-square head with an antenna.

### Behaviour

- **Gestures.** Pointer events on `screen`. Press records the start point; release is a click when it moved at most 8 device points, otherwise a drag. Both are applied to the app (`tapApp`, `swipeApp`), recorded with `makeAction(..., scale 1, Date.now())` together with the label and role of the element hit, and shown at once as a watcher line in the feed.
- **Agent step.** Hear (human actions, new mismatches and a not yet adopted scale problem since the last step, by timestamp), say what it heard, look, decide with `policy`, say where it will tap, glide the agent's cursor there in 1.2 s, wait 1.5 s (0.45 s in the automatic demo) for a possible carry, tap, look again. A miss shows the intended control and starts the countdown of the correction window. After a step that worked while the scale is corrected, the next step follows by itself after 1.7 s.
- **Automatic demo.** Resets, then runs steps; after each miss a ghost glides to the dot of the intended control and clicks it, and the next step follows after about 1 s.
- **Window.** `windowMs` (5000, 15000 or 30000, default 15000) feeds `detectMismatches`, the countdown and the timeline.
- **Carry.** As Requirement 7, with `carry` and `dropPoint` state; the drop point replaces the tap point; a carried drag is recorded with a `carried` flag.
- **Panels.** Re-rendered after every recorded action from `snapshot()`.
- **Test hook.** `window.__poltergeistDemo = {agentStep, humanGesture, reset, snapshot, state, setWindow}`.

## Checks

- Provided, run by Node: `python demo/check_port.py` and `python demo/check_app.py`.
- Run in a browser by the reviewer: no console errors; the first screen holds the phone, controls and agent panel at 1000 x 563, 1440 x 800 and 1280 x 900; no horizontal scroll at 390 wide; the full story through the test hook (three corrections give a scale problem near 1.5, then `done` and `sendbtn` finish the task); the carry flow; the page without JavaScript.
