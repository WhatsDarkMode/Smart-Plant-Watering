## ADR-002:
Keep the float switch orientation and rely on layered safeguards

## Context:
The float switch is a passive switch wired between GPIO25 (internal pull-up) and GND. Float up (water present) opens the switch and reads 1; float down closes it to GND and reads 0. A cut or disconnected lead also reads 1, which the controller treats as "water present", so the most likely wiring fault would hide an empty reservoir and disable the interlock that stops the pump running dry. A fail-safe orientation would need an open circuit to mean "reservoir low", which requires the switch to be closed when the float is up.

## Decision:
Keep the current orientation ('FLOAT_WATER_PRESENT = 1') and accept the known weakness, relying on the layered safeguards to limit the damage.

## Reasoning / Alternatives considered:
The fail-safe orientation was the first choice, but the float cannot be physically reversed on its stem, and the orientation is set by the hardware, not the code. Changing only 'FLOAT_WATER_PRESENT' to 0 was rejected because it inverts the interlock: float up would be read as "reservoir low" and float down as "water present", so the pump would run when the reservoir is empty. Rewiring cannot fix it either, because a broken lead and a float that is up are both open circuits and look identical to the ESP32 whichever way it is wired.

Two ways to get a real fail-safe remain: replacing the float with one whose contact is closed when the float is up, or a supervised input (a resistor across the switch, read on an ADC1 pin, so closed, open and broken wire read as three different values). Both were rejected for now as more cost and complexity than a low-stakes home rig needs while the other safeguards are in place.

The second float switch could add redundancy, but its purpose is still undecided and it would have the same orientation, so it is not part of this decision.

## Consequences:
A broken float lead combined with an empty reservoir would let the pump dry-run. That exposure is bounded by the other safeguards: the relay is off at startup and released in 'try/finally', each burst is 5 seconds, an episode is capped at three bursts, and the cooldown (30 minutes) applies when the soil does not respond. A lead shorted to GND would read 0 ("water low") and stop watering, which is the safe direction. Stage 6 failure testing should unplug the float lead and record what the pump does. The decision should be revisited if the rig ever runs unattended for long periods, or if a float with the opposite contact type is fitted. The build guide (Step 2.3) needs updating to match.