## ADR-001:
Use a relay module instead of a MOSFET to switch the pump

## Context:
The ESP32's GPIO pins can't drive a pump motor directly (too little
current) — some form of switching device was needed between the GPIO
signal and the pump's actual power. A MOSFET-based driver module (IRF520,
a very commonly sold hobbyist "driver module") was the original plan.

## Decision:
Use a 5V optocoupler-isolated relay module instead.

## Reasoning / Alternatives considered:
Investigated the IRF520 specifically after a secondhand report that it
doesn't work reliably with 3.3V/5V logic despite being marketed as
compatible. Confirmed via multiple independent sources (Arduino/ESP32/
Raspberry Pi community forums) that the IRF520's gate threshold voltage
is genuinely too high to fully switch on at 3.3V — the chip runs in a
partially-conducting state rather than cleanly on/off, generating
unnecessary heat.

Considered sourcing a genuine logic-level MOSFET (IRLB8721) instead, but
found these are sold almost exclusively as bare transistors, not
ready-made modules — using one would require building a small supporting
circuit (pull-down resistor, flyback diode) from scratch, reintroducing
a breadboard/soldering requirement this project was deliberately trying
to avoid.

A relay module sidesteps the gate-voltage problem entirely (mechanical
switch, not voltage-threshold-dependent), already includes its own
flyback diode protection on the coil as standard, and is sold in the
same solderless, screw-terminal, 3-pin-header format the MOSFET module
would have been — no change to the overall wiring plan.

## Consequences:
Mechanical switch rather than solid-state — audible click, and contact
wear over a very large number of cycles (not a concern at this project's
scale). Genuinely safer for the ESP32 than an unprotected/under-driven
MOSFET would have been. Also arguably a more directly OT-relevant choice
than a MOSFET — relay-based switching is standard in real industrial
digital output hardware.
