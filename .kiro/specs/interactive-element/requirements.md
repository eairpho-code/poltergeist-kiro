# Requirements Document

## Introduction

The macOS observer reports the accessibility element under a human click. It takes the deepest element at that point. When a person clicks a button, the deepest element is often the text inside the button. The observer then reports `{"role": "text", "label": "I"}`, and the hook tells the agent "the human clicked (159.7, 302.4) on a text". A real model read that as a click on meaningless text that changed nothing, decided that its own click had been right, and failed the task. When the same control was a real `<button aria-label="Candle I">`, the report named the button and the model understood.

This change makes the observer report the control the person meant to press, when there is one, and changes the sentence so that a bare text is not called "a text".

## Glossary

- **Chain**: the element under the click, then its parent, then its grandparent, and so on.
- **Interactive element**: an element that has the accessibility action `AXPress`, or whose role is one of `AXButton`, `AXLink`, `AXCell`, `AXCheckBox`, `AXRadioButton`, `AXSwitch`, `AXTextField`, `AXTextArea`, `AXSlider`, `AXMenuItem`, `AXPopUpButton`.
- **Frame element**: an element whose role is `AXWindow` or `AXApplication`. It is never chosen, whatever its actions are.

## Requirements

### Requirement 1: Choose the control, not the text inside it

**User Story:** As an agent, I want to be told which control the human pressed.

#### Acceptance Criteria

1. THE observer core SHALL provide a pure function that, given a chain, returns the index of the element to report.
2. WHEN the element under the click is interactive, THE function SHALL return `0`.
3. OTHERWISE THE function SHALL return the index of the nearest interactive element among the next 6 ancestors (indexes 1 to 6), and SHALL NOT choose a frame element.
4. WHEN there is none, THE function SHALL return `0`, so that the report is what it was before this change.
5. THE function SHALL not read the labels of elements. It works on role and actions only.

### Requirement 2: Use it in the observer

1. THE observer SHALL build the chain by walking `kAXParentAttribute` up to 6 levels from the element under the click, reading each element's role and action names, SHALL choose with the function of Requirement 1, and SHALL report the role of the chosen element, and its label only when labels are on, as before.
2. THE label of the chosen element SHALL be read with the same attributes as before (title, then description, then value) and shortened as before.
3. WHEN reading the parent or the actions fails, THE observer SHALL stop walking up and use what it has. It SHALL NOT fail the click.

### Requirement 3: The sentence

**User Story:** As an agent, I should not read "a text" as "nothing happened".

#### Acceptance Criteria

1. `describe_action` in `poltergeist/activity.py` SHALL name the element as follows, inserted before ` at <time>`:
   - role `text` with a label: ` on the text "<label>"`
   - role `text` without a label: ` on some text`
   - any other role with a label: ` on a <role> "<label>"`
   - any other role without a label: ` on a <role>` (as before)
   - no role: nothing (as before)
2. A label is used as it is stored. The server already shortens it to 50 characters and drops it when redaction is on. An empty label counts as no label.
3. THE demo's `describeAction` SHALL produce the same sentences from the action's `role` and `label`. `demo/check_port.py` compares them on random actions that have roles and labels.

### Requirement 4: Documentation

1. `docs/usage.md` SHALL say that the observer reports the nearest interactive element up to 6 levels above the click, and `README.md` SHALL say so in the observer section in one sentence.
