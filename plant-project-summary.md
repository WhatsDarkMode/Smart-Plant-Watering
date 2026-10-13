# Smart Plant Watering — OT Control Project Summary

## Goal

Build a second portfolio project, deliberately more OT-authentic than the
sensor/weather project, to have a genuine, concrete talking point for OT
interviews and conversations (e.g. with Mahesh/the Davids). Uses real
industrial protocol and software — Modbus TCP and Ignition SCADA — rather
than analogues, while staying personally engaging (plants) and safe
(dry/wet electronics separation maintained throughout, same discipline as
the sensor project).

## Architecture (Target Design)

```
[Soil moisture sensor] --\
                           \
[Float switch] ------------+--> ESP32 (local control logic:
                           /     interlock + hysteresis + state machine)
                          /              |
                         /               | Modbus TCP
                        /                v
                  [Relay] --> [Pump] --> [Ignition SCADA]
                  (switches                (HMI, alarms,
                   pump power)              historian)
```

- **Sensing:** capacitive soil moisture sensor (analog, powered from the
  ESP32's 3.3V pin — NOT 5V, to stay within the ADC pin's safe input
  range) and a float switch for reservoir level (digital, passive).
- **Local control:** ESP32 runs the actual control loop and interlock
  logic (e.g. "don't run the pump if soil is dry but reservoir is low")
  — this mirrors the real OT principle of local control surviving even if
  the supervisory layer (Ignition) is unavailable.
- **Actuation:** a 5V relay module switches the pump's power — chosen
  over the originally planned MOSFET after discovering the common IRF520
  module doesn't reliably switch on at ESP32's 3.3V logic level (see
  `decisions/`).
- **Supervisory layer:** Ignition SCADA (free trial, indefinitely
  renewable via 2-hour Gateway restart) communicates with the ESP32 via
  Modbus TCP, providing the HMI, alarms, and historian/trending —
  deliberately separate from the local control logic, same
  local-vs-supervisory split real OT systems use.

## Hardware Plan (Actual Parts Purchased)

| Item | Qty | Approx cost |
|---|---|---|
| ESP32 dev board (pre-soldered headers) | 1 (reused from sensor project's node 1) | £0 |
| Capacitive soil moisture sensor v1.2 (5-pack) | 1 pack | £7.59 |
| USB mini submersible pump (5V, 8mm nozzle) | 1 | £6.95 |
| Water level float switch (vertical, lid-mount) | 1 pack | £7.99 |
| 5V 1-channel relay module (optocoupler, screw terminal) | 1 | £5.58 |
| Silicone tubing, 6mm ID x 8mm OD, 2m | 1 | £5.50 |
| USB female-to-screw-terminal adapter (solderless) | 1 pack | ~£5-7 |

**Running total (excluding ESP32, pending confirmation): ~£33-40**

## Software Stack

- **ESP32:** MicroPython, reading soil/float sensors, driving the relay,
  communicating via Modbus TCP (likely via a MicroPython Modbus library —
  to be confirmed in Stage 1).
- **SCADA/HMI:** Ignition (free trial mode), including Inductive
  University's free official training videos as the primary learning
  resource for the platform itself.

## Decisions

The reasoning behind design choices (relay over MOSFET, pump type, float
switch mounting style, cost-trimming decisions) is documented as
individual ADRs in `decisions/`, same pattern as the sensor project.
Several decisions were already made during parts selection, before any
code was written — worth writing these up as the first ADRs before
building begins, since the reasoning is freshest now.

## Build Journey

The actual steps taken, including mistakes and fixes, will be recorded in
`build-journey.md` as the project progresses — same approach as the
sensor project.

## Open Questions / Next Steps

- Note: reusing node 1's ESP32 means the sensor project's dashboard stops
  receiving new data from this point — a deliberate pause, not a failure
  (historical data and the deployed app remain intact). Worth a note on
  the sensor project's own README reflecting this.
- Confirm MicroPython Modbus TCP library choice before Stage 1.
- Obtain an actual plant.
- Stage the build the same way the sensor project worked well: prove each
  piece in isolation (sensor read, float switch read, relay switching the
  pump, Modbus communication, Ignition tag binding) before combining into
  the full control loop.
