## ADR-003:
Allow manual pump control from Ignition, limited by controller-side interlocks

## Context:
The plan so far had Ignition monitoring the rig and tuning thresholds, with watering decided entirely by the ESP32. I want to be able to tell the pump to run when I choose, for example to prime the tubing, test the pump, or water outside the soil-driven cycle. Modbus has no authentication, so anything on the network that can reach port 502 can write to the registers, and the controller can't assume the writer is careful or even friendly.

## Decision:
Add a Manual mode that Ignition selects through a holding register, with a coil that requests one fixed pump burst. Automatic mode stays the default. The ESP32 enforces every limit itself, whatever Ignition writes:
- A request starts one fixed 5-second burst, not a run-while-held switch.
- The reservoir interlock applies before and during the burst (the pump stops at once if the float drops).
- A minimum gap (10 seconds) between manual bursts, and a cap of 60 seconds of manual pumping per hour.
- After 10 minutes with no manual activity the controller returns to Auto.
- The board always starts in Auto with no request pending, so a reboot can never come back up with the pump requested.
- Burst length, burst cap and cooldown stay fixed in the firmware, and Ignition can't change them. Threshold writes are clamped so a bad value can't remove the gap between the dry and wet thresholds.

## Reasoning / Alternatives considered:
Monitor-only (no remote control) was the simpler option, with fewer states to build and test. I rejected it because being able to command the pump is useful in practice and it shows what I want to be able to talk about in an OT context: an operator command that is still limited by local interlocks the operator can't override.

A hold-to-run switch, where the pump runs while the coil is set, was rejected because a crashed HMI, a dropped connection or a stuck tag could leave the pump on. A fixed burst per request means the worst case is one short burst.

Letting manual mode bypass the reservoir check was rejected: the interlock is the main protection against dry running, and an operator override is exactly when it matters most.

Unlimited manual bursts were rejected because a stuck button or a script writing the coil in a loop would chain bursts together. The gap and the hourly cap bound the worst case to a known amount of water, even if the writer misbehaves.

The fall-back to Auto was added because a forgotten Manual mode would otherwise stop the plant being watered automatically, with nothing to show for it except a quiet rig.

## Consequences:
The controller gains a mode, two extra states and a fault code, with a matching set of tests, and the 'state' register now has six values instead of four. Ignition can alarm on the fault code and on a frozen heartbeat, and shows why a request was refused.

Manual mode is bounded but not safe against a determined writer on the network: anyone who can reach port 502 can still trigger up to the hourly cap of manual pumping, switch modes, and move the thresholds inside the clamp range. The network is the only protection against that, so the rig stays on the home network and the port is not exposed.

Threshold and mode writes are not saved, so a reboot returns the rig to the defaults in 'watering_main.py'. The manual limits are firmware constants, so changing them means editing the file.