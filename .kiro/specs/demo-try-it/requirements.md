# Requirements Document

## Introduction

Visitors open `demo/index.html` and many do not understand how to use it. The page has two modes. In the automatic mode a ghost corrects the agent and the visitor only watches. In the manual mode the visitor is the human and clicks where the agent should have tapped. Today nothing says which button is which, the big purple button starts the automatic mode and hides the part that makes the demo convincing, and the numbered instructions disappear when the browser window is less than 760 px high. This change names the two modes, makes the manual one the primary action and keeps the instruction visible at every window height.

## Glossary

- **Manual run**: a run in which the visitor corrects the agent. It starts with `#agentBtn`.
- **Automatic run**: a run in which a ghost corrects the agent. It starts with `#autoBtn`.
- **Task done**: the state in which the beach photo has been sent to Maya Chen (`taskDone(app)` of the app).
- **Status line**: the element `id="window"` under the buttons.
- **Labels block**: a new block of the script between the marker lines `// <labels>` and `// </labels>`, with pure functions and no browser objects, so that it runs in Node.

## Requirements

### Requirement 1: The two buttons say what they do

**User Story:** As a visitor, I want to know which button lets me play and which one only shows me the story.

#### Acceptance Criteria

1. THE button `#autoBtn` SHALL read `Watch the story` and SHALL NOT have the class `primary`.
2. THE button `#agentBtn` SHALL have the class `primary` and SHALL read `Try it yourself` in the markup.
3. THE button `#agentBtn` SHALL read `Try it yourself` before the first step and `Next step` after the first step of a run.
4. WHEN the task is done after a manual run, THE button `#agentBtn` SHALL read `Replay`.
5. WHEN the task is done after an automatic run, THE button `#agentBtn` SHALL read `Try it yourself`.
6. THE button `#resetBtn` SHALL still read `Reset`. THE ids `agentBtn`, `autoBtn`, `resetBtn`, `window`, `screen` and `app` SHALL each appear exactly once.

### Requirement 2: One press starts a fresh manual run

**User Story:** As a visitor, I want the button that says Replay or Try it yourself to start playing at once.

#### Acceptance Criteria

1. WHEN `#agentBtn` is pressed while the task is done, THE page SHALL reset and then perform the agent's first step, in one press. It SHALL NOT only reset.
2. WHEN `#agentBtn` is pressed while the task is not done, THE page SHALL perform the agent's next step as before.
3. THE decision (restart or step) SHALL be made by a pure function of the labels block.

### Requirement 3: The visitor can always see what to do

**User Story:** As a visitor on a laptop, I want the instruction on screen whatever the height of my window.

#### Acceptance Criteria

1. BEFORE the first step, THE status line SHALL say to press `Try it yourself` and then to click where the agent should have tapped.
2. NO `@media` rule with `max-height` (for example the one at 760 px) SHALL hide or change the status line, `#window` or `.status`.
3. THE numbered steps in the left card (`<ol class="steps">`) SHALL use the new names: the first step SHALL tell the visitor to press `Try it yourself`.
4. THE status line SHALL say the same thing again every time the page returns to its first state (reset, window choice before the first step, a closed window).

### Requirement 4: The end of the automatic story invites the visitor

**User Story:** As a visitor who watched the story, I want to be told what to do next.

#### Acceptance Criteria

1. WHEN the automatic story ends, THE status line SHALL say that the ghost did the correcting and SHALL invite the visitor to press `Try it yourself`.
2. THE sentence SHALL come from a pure function of the labels block.

### Requirement 5: No old name remains

**User Story:** As a maintainer, I want one vocabulary.

#### Acceptance Criteria

1. THE file `demo/index.html` SHALL NOT contain the old button names `Agent step` and `Play the story`, anywhere (markup, script, comments).
2. THE labels `Next step` and `Replay` SHALL remain in the page.

### Requirement 6: The README names the two modes

**User Story:** As a reader of the README, I want to know the two modes.

#### Acceptance Criteria

1. THE README section `The demo` SHALL name the two modes and the two button names, `Watch the story` and `Try it yourself`, in a sentence or two. (Stage 3.)

### Requirement 7: What does not change

**User Story:** As a maintainer, I want the detection untouched.

#### Acceptance Criteria

1. THE blocks `// <core>` and `// <app>` of `demo/index.html` SHALL be byte for byte as before. THE test hook, the correction window logic, and the way anything is detected or paired SHALL NOT change.
2. THE page SHALL NOT be restyled beyond making `#agentBtn` primary and `#autoBtn` secondary.
3. `demo/check_app.py` and `demo/check_port.py` SHALL still pass.

### Requirement 8: The invitation stays (requirement 7 of the brief)

**User Story:** As a visitor, I want the invitation at the end of a run to stay on screen, so that I know what to do next.

#### Acceptance Criteria

1. ONCE a run is finished (the task is done), THE status line `#window` SHALL keep its text until the visitor does something. THE correction-window countdown ("Correct it! ... s left", "Window closed ...") SHALL NOT write to it any more.
2. WHEN the countdown ticks and the task is done, IT SHALL stop its timer and write nothing to the status line.
3. WHEN a run is reset or restarted, THE countdown timer SHALL be stopped (it already is, by `reset()`).
4. WHILE a run is in progress, THE correction window SHALL work as before.
