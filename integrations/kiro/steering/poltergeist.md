# Poltergeist: learning from the human's clicks

Poltergeist records the clicks and drags a human makes on the iOS Simulator
while you drive it. The hook prompt that arrives after a simulator tool call
means: a human may have corrected your last gesture, so look before you act again.

## Reading the human's actions

Before your next simulator action, call `get_human_actions` on the poltergeist
server. Pass `since_timestamp` with the time of the latest human action you have
already seen, so you only get new ones. On the first call, leave it out.

## What to do with the result

- A mismatch pairs a human click with the agent click it corrected. The human's
  click shows where you meant to click. Use that point, not yours, and note the
  offset between the two.
- A coordinate scale problem means several corrections share the same ratio
  between your coordinates and the human's. Your coordinates are probably on the
  wrong scale (for example screenshot pixels read as device points). Divide your
  coordinates by the reported ratio, then check with your next click.
- If there are no human actions, carry on.
