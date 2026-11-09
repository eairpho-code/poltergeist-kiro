# Requirements Document

## Introduction

A single web page, `demo/index.html`, that lets a visitor try Poltergeist without installing anything. A phone on the page runs a small Messages app. A scripted agent is sending Maya Chen a photo, but it reads screen coordinates about 1.5 times too big, so its taps miss. The visitor plays the human: they correct the agent by tapping where it should have tapped, and they can also poke around the phone freely. The page shows the agent's reasoning, what Poltergeist tells the agent, and the 5 second pairing windows on a timeline. After three corrections Poltergeist names the scale bug, the agent divides its coordinates by the measured factor and finishes the task alone.

The page is one HTML file with inline CSS and JavaScript. It has no build step and no dependency except web fonts. It runs from a plain static file server, such as GitHub Pages.

## Glossary

- **Device points**: the phone screen is 430 x 932 points, origin top left. Everything on the phone is placed in device points.
- **The agent**: the scripted agent on the page. It is not a language model.
- **The human**: the visitor. On the page the human is a ghost.
- **Correction window**: how long after an agent tap a human click counts as a correction. The real server uses 5 seconds. The page lets the visitor choose 5, 15 or 30 seconds, with 15 as the default.
- **Core**: the part of the script that ports the Python detection rules and the sentences of the activity module.
- **App**: the part of the script that holds the pure logic of the phone's Messages app.

## Requirements

### Requirement 1: The core follows the Python rules

**User Story:** As a maintainer, I want the page to apply the same rules as the server, so that what the visitor sees is what the server would do.

#### Acceptance Criteria

1. THE script SHALL contain the core between the marker lines `// <core>` and `// </core>`, with no browser objects in it, so that it can run in Node.
2. THE core SHALL provide `makeAction`, `detectMismatches(actions, windowMs)`, `detectScaleProblem`, `describeAction`, `describeMismatch`, `describeScale` and the helpers named in the design.
3. FOR any log of clicks and drags and any window of 5, 15 or 30 seconds, THE core SHALL pair the same actions, give the same offsets and distances, report the same scale problem and produce the same sentences as the Python modules `poltergeist.detection` and `poltergeist.activity`. `demo/check_port.py` compares them on 3000 random logs.
4. Number formatting SHALL round exact ties to the even digit, as Python does (0.25 gives `0.2`).

### Requirement 2: The phone's Messages app

**User Story:** As a visitor, I want a phone that behaves like a real app, so that my taps and swipes have consequences, and so does a wrong tap by the agent.

#### Acceptance Criteria

1. THE script SHALL contain the app between the marker lines `// <app>` and `// </app>`, as pure functions that run in Node, with the contract of the design: `initialApp`, `elementsFor`, `hitTest`, `perform`, `tapApp`, `swipeApp`, `describeScreen`, `taskDone`, `policy`, `worked`, `screenHtml`.
2. THE app SHALL have four screens: the chat list, a chat thread, a photo picker and a settings page, plus a delete-confirmation dialog and a toast.
3. A tap SHALL do what the visible control says: open a chat, go back, share a photo, pick and confirm a photo, send, switch tabs, flip a switch, open and answer the dialog. Taps outside the 430 x 932 screen SHALL do nothing.
4. A horizontal swipe SHALL change page between the two tab screens, and a swipe in from the left edge SHALL go back from a thread or the photo picker. A dialog SHALL block swipes and taps behind it.
5. THE agent's wrong taps SHALL land somewhere harmless or fixable, as the design's story table states, so that one human tap on the intended control always puts the app back on track.
6. `demo/check_app.py` runs this story and the free-play behaviour in Node.

### Requirement 3: The page

**User Story:** As a visitor, I want a clear page that explains itself and works on a laptop and on a phone.

#### Acceptance Criteria

1. THE page SHALL have, in this order: a top bar (the ghost mark and the name Poltergeist, links to the sections, a theme button), a headline, a stage (what to do and the controls on the left, the phone in the middle, the agent's reasoning on the right), a section that shows what the agent is told, a section about the pairing rule with a timeline and an event log, a how-it-works section, a run-it section with copyable commands, and a footer.
2. THE headline SHALL be `Stop haunting your agent.` and the text SHALL say that to the agent the human is the poltergeist.
3. WHEN JavaScript is not available, THE page SHALL still show the phone with the chat list, the empty states of every panel, and a note that the demo needs JavaScript.
4. THE page SHALL state that it runs a JavaScript port of the rules and a scripted agent, and SHALL NOT present the scripted reasoning as a language model.
5. THE page SHALL work at 390 px wide without horizontal scrolling, in light and dark themes, and SHALL respect reduced motion.

### Requirement 4: The first screen shows the whole demo

**User Story:** As a visitor, I want to see the phone and the controls without scrolling.

#### Acceptance Criteria

1. THE phone's height SHALL be computed from the viewport height so that the top bar, the headline, the phone, the controls and the status all fit in the first screen, between a minimum of 380 px and a maximum of 780 px.
2. THE agent panel SHALL be exactly as tall as the phone.
3. WHEN the viewport is lower than 760 px, THE three-step text SHALL be hidden. WHEN it is lower than 660 px, THE intro line and the label above the headline SHALL be hidden as well.
4. BELOW 900 px width THE agent panel SHALL move below the phone, and below 640 px everything SHALL stack in one column with the controls above the phone.

### Requirement 5: The agent

**User Story:** As a visitor, I want to watch an agent that finds out what I did and reacts.

#### Acceptance Criteria

1. THE agent SHALL move only when the visitor presses the agent button, or during the automatic demo, or on its own after it has corrected its scale.
2. EACH agent step SHALL: hear what Poltergeist would add to its context since the last step; look at the screen; choose the next control with the policy of the app; read that control's position 1.5 times too big (divided by the measured factors once it has corrected itself); tap it for real; look at the result.
3. WHEN a tap does not do what the agent wanted, THE page SHALL show the control it meant (dashed outline and a pulsing dot at its centre), a countdown of the correction window, and say what the agent meant and what it hit.
4. WHEN the human corrects the agent, THE page SHALL say how many seconds later it happened and whether Poltergeist paired the two. A click after the window SHALL NOT pair.
5. AFTER three paired corrections whose ratios agree, THE agent SHALL say that its coordinates are about 1.5 times too big, divide by the measured factors, and finish the task without help.
6. THE agent SHALL react to what the human did: a pair, a free tap or swipe, a stuck repeat, and a carried cursor (Requirement 7).
7. THE agent's reasoning SHALL be shown beside the phone as a feed with the kinds: task, thinking, action, result, hook text, live watcher lines and done. The page SHALL label the agent `scripted`.
8. A button SHALL start the agent, with the text changing between first step, next step and replay. A second button SHALL play the whole story with a ghost that corrects the agent, and a third SHALL reset everything.

### Requirement 6: The human is a ghost

**User Story:** As a visitor, I want the pointer to feel like a ghost.

#### Acceptance Criteria

1. WHILE the pointer is over the phone, THE page SHALL replace the system pointer with a semi-transparent violet ghost that tilts in the direction of movement. On touch screens it SHALL appear at the touch point.
2. A click SHALL make the ghost squint and then call out `boo!`, with two expanding rings and a few wisps. A drag SHALL leave wisps along its path.
3. A click or a drag SHALL be recorded as a human action at the position in device points, with the role of the control under it, and SHALL be applied to the app. A gesture that moves more than 8 points SHALL be a drag.
4. EACH human action SHALL appear at once in the agent's feed as a live watcher line, and in the event log.

### Requirement 7: Carry the agent's cursor away

**User Story:** As a visitor, I want to be able to hijack the agent's cursor, to see how it notices.

#### Acceptance Criteria

1. BEFORE its tap, THE agent's cursor SHALL glide to the point it aims at and stay there for about 1.5 seconds, with a ring around the aim point.
2. WHEN the ghost comes within 90 points of the agent's cursor, THE cursor SHALL shake and show an exclamation mark.
3. WHEN the human presses within 60 points of the agent's cursor, THE human SHALL pick it up and carry it with the pointer. Letting go SHALL drop it; the agent SHALL then tap at the drop point.
4. THE carry SHALL be recorded as a human drag, from where the cursor was to where it was dropped, marked as carried. No app action SHALL result from it.
5. AT its next step THE agent SHALL say that the human dragged right before its tap, that its tap landed elsewhere than it aimed, and that they probably carried its cursor.

### Requirement 8: What the agent is told, the rule, and the log

**User Story:** As a visitor, I want to see exactly what Poltergeist produces.

#### Acceptance Criteria

1. THE page SHALL show, from the live log, the text that the Claude Code hook adds to the agent's context (the header sentence followed by one `- ` line per action, mismatch and scale problem), and the raw result of the `get_human_actions` tool as JSON.
2. THE page SHALL show a card that reports the scale problem with the factor, the sample count, both factors and the spreads; before there are three corrections it SHALL say how many are still needed; when there are three or more corrections whose ratios disagree it SHALL say so and give the spread.
3. THE page SHALL show a timeline with an agent lane and a human lane: a dot for each action, a bar for each agent tap's window, lines between paired actions, and a moving marker while a window is open.
4. THE page SHALL show an event log table with time, actor, action, device points and pairing, newest first.
5. A pair SHALL also be drawn on the phone as a dashed line with the signed offset until the agent moves again.

### Requirement 9: Controls, themes and copying

#### Acceptance Criteria

1. THE visitor SHALL be able to choose a correction window of 5, 15 or 30 seconds; the choice SHALL apply to the pairing, the countdown and the timeline.
2. THE theme button SHALL switch between light and dark, and the page SHALL follow the system theme by default.
3. EACH command in the run-it section SHALL have a copy button that copies its text and says `Copied`, with a fallback that selects the text.
4. THE footer SHALL link to the repository when the script's `REPO_URL` is set.

### Requirement 10: A test hook

#### Acceptance Criteria

1. THE page SHALL expose `window.__poltergeistDemo` with `agentStep()`, `humanGesture(x0, y0, x1, y1)`, `reset()`, `snapshot()`, `state()` and `setWindow(ms)`, so that the page can be tested from a browser console. `snapshot()` returns `{humans, mism, scale}`.
