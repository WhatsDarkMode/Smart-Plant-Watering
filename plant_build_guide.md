# Smart Plant Watering — Build Guide (Stages 0 to 2)

Companion to `plant-project-summary.md`. Covers preparing the repo and
board (Stage 0), getting local watering working with no Ignition
(Stage 1), and making the control logic safe for unattended running
(Stage 2). Each step proves one thing in isolation. Stages 3-7 follow the
plan in the original project draft and get their own guide. Stage 3
(Modbus) can be started on the bench before Step 2.4 is finished, because
it does not need the plant or the pump.

This guide is the plan, not the record. Record what you actually did in
`build-journey.md`, not what this guide says you should do.

## Progress at a glance

| Step | Status |
|---|---|
| 0 Repo and board prepared | Done |
| 1.1 Soil sensor reading and calibrated | Done (sensor 3 only; see 1.1) |
| 1.2 Float switch | Done |
| 1.3 Relay with no load | Done |
| 1.4 Pump through the relay | Done |
| 1.5 Delivery path and flow rate | Not done |
| 1.6 Simple local watering (blocking script) | Bench-tested with forced readings; not run on the real plant |
| 2.1 Controller state machine and pytest | Done (all 14 tests pass on the PC) |
| 2.2 Controller on the board | Done (bench-tested with forced readings; not run on the real plant) |
| 2.3 Float fail-safe decision | Done (keep the orientation; ADR-004) |
| 2.4 Unattended running | Not done |

---

## Pin plan (verify against your board's printed labels first)

| Function | ESP32 pin | Why this pin |
|---|---|---|
| Soil sensor analog out | GPIO34 | ADC1 pin. ADC2 pins stop working once WiFi is on, which Stage 3 needs. GPIO34 is input-only, which is fine for a sensor. |
| Float switch | GPIO25 | Digital input with an internal pull-up. GPIO34-39 have no pull-up, so avoid those for this. Originally planned as GPIO27; moved to 25 to avoid tangling wires with the relay. WiFi does not affect it. |
| Relay IN | GPIO26 | Stays quiet at boot. Pins like 0, 2, 5, 12, 15 toggle during boot and could blip the pump. |
| Sensor/relay logic power | 3.3V (soil sensor), VIN/5V (relay) | See the power notes in Steps 1.1 and 1.3. |
| Ground | GND | The ESP32, sensors and the relay's control side share one ground. The pump's supply circuit stays separate (see Step 1.4). |

---

## Stage 0 — Prepare the repo and the board

### 0.1 Create the repo
New GitHub repo (separate from the sensor project), cloned locally, with
this structure:

```
plant-project/
├── esp32/              device code, plus tests/ and pytest.ini
├── ignition/
├── decisions/
├── photos/
├── plant-project-summary.md
├── plant-build-guide.md
├── build-journey.md
├── README.md
└── .gitignore
```

Put this in `.gitignore` before anything else, using the `**/` form so it
matches at any depth (the lesson from the sensor project's secrets slip):

```
**/config.py
__pycache__/
*.pyc
.vscode/
.DS_Store
```

### 0.2 Protect the sensor project
- Confirm your PC copy of the sensor project's `node/config.py` still
  exists **before** deleting anything from the board. It is gitignored, so
  it is not in the repo, and the copy on the board is the only other one.
- The sensor project's code is all in its repo, so nothing in the repo is
  lost by clearing the board.

### 0.3 Clear the old program off the board
The board currently has the sensor project's `main.py`, which runs
automatically on every boot. With the BME280 unplugged it would crash at
startup; with it plugged in it would keep posting to your live dashboard.
In Thonny, open **View → Files**, find the files in the device pane,
right-click each and delete it from the device:

- delete: `main.py`, `config.py`, `db.py`, `bme280_float.py`
- keep: `wifi.py` (its `connect()` function takes the credentials as
  arguments, so it is not tied to the sensor project) and `boot.py`
  (leave it alone)

Then unplug the BME280's four jumper wires from GPIO21/22 and 3.3V/GND.

Add a build journey entry noting the sensor node is now paused, and a
status line on the sensor project's README saying the same.

---

## Stage 1 — Physical hardware, local watering

### 1.1 Soil sensor
Wiring: sensor VCC to 3.3V, GND to GND, analog out to GPIO34. Power it
from 3.3V, not 5V, so its output can never exceed what the ADC pin
tolerates.

```python
from machine import ADC, Pin
import time

soil = ADC(Pin(34))
soil.atten(ADC.ATTN_11DB)   # full 0-3.3V range; constant name can vary by firmware

while True:
    print(soil.read())
    time.sleep(1)
```

If a sensor reads a flat 0, test the pin before blaming the code: touch
GPIO34 to 3.3V (should read about 4095) and to GND (should read 0). If
the pin passes, try another sensor. On this build sensors 1 and 2 read a
flat 0 and are probably faulty; sensor 3 worked immediately on the same
wiring. Test the spare sensors (4 and 5) and ask the seller for a refund
on the faulty ones.

Calibrate: record the value with the sensor dry in air, then with the
probe in a cup of water (only up to the marked line, keeping the
component end dry). A capacitive sensor reads **higher when dry and lower
when wet**, which is the opposite of what most people expect. Results
with sensor 3:

| Condition | Reading |
|---|---|
| In air | about 2500 (2481-2544) |
| In water | about 590 (582-621), settling over about 50 seconds |
| Pot, bone-dry soil | about 2100 |
| Pot, well-soaked soil | about 750 |

The wobble is roughly ±20, so thresholds need a gap much wider than
that (see Step 1.6).

Optional: the exposed PCB edges can absorb water over time. A coat of
clear nail varnish on the edges is a common cheap fix.

**Commit point.**

### 1.2 Float switch
Wiring: one lead to GPIO25, the other to GND. The switch has no
polarity, so it does not matter which lead goes where. The leads are bare
wire, so join each to a jumper wire (cut a spare jumper's connector off,
strip it, twist it to the lead and tape each join separately). Keep the
joins above the water line.

```python
from machine import Pin
import time

float_sw = Pin(25, Pin.IN, Pin.PULL_UP)
while True:
    print(float_sw.value())
    time.sleep(0.5)
```

Move the float along the stem and note which value means "water present"
and which means "water low". Whether the switch is normally open or
normally closed depends on its orientation, and getting this backwards
would silently invert your interlock, so test it rather than assuming.

Result on this build: float down reads 0 (switch closed, pin pulled to
ground); float raised to about halfway up the stem reads 1 (switch open,
pin held high by the pull-up). The change is clean with no flicker. So
**1 = float up = water present, 0 = float down = water low.**

Known weakness: with this orientation a broken or disconnected lead also
reads 1, which looks like "water present". That is the unsafe way to fail
for a pump interlock. See Step 2.3 and ADR-004.

**Commit point.**

### 1.3 Relay with no load
Wiring: relay DC+ to the ESP32's VIN/5V pin, DC- to GND, IN to GPIO26.
Nothing connected to the relay's output terminals yet. On this module the
control-side connections are screw terminals, so each jumper needs a
stripped end clamped under the screw.

```python
from machine import Pin
import time

RELAY_ON = 1    # this module triggers on HIGH (jumper cap not on L)
RELAY_OFF = 0

relay = Pin(26, Pin.OUT, value=RELAY_OFF)   # off immediately at startup
print("should be OFF")
time.sleep(3)
print("on")
relay.value(RELAY_ON)
time.sleep(3)
print("off")
relay.value(RELAY_OFF)
time.sleep(3)
print("done")
```

Do not assume which pin level switches the relay on. The listing says low
level, but the module has a high/low jumper cap and its position decides
the polarity. On this build the cap was not on L, and the green relay LED
(the relay-on indicator; the red one is just PWR) lit when the pin was
HIGH, so this module triggers on HIGH. Check yours from the cap position,
the clicks and the green LED. Name the polarity as constants, as above,
and never scatter bare 0s and 1s through the pump code.

Also test the state the pin is in at every boot, before your code runs:
`Pin(26, Pin.IN)` in the Shell. The relay must be OFF in that state, or a
reboot could start the pump. (Passed on this build: relay and green LED
stayed off.)

With the cap on H, the ESP32's 3.3V is a clean on-signal. The quirk where
3.3V HIGH fails to fully release a relay applies to low-level-trigger
setups, so leave the cap on H.

**Commit point.**

### 1.4 Pump on the relay, in a cup of water
The pump has its own supply path, separate from the ESP32's. The relay
contacts are dry (electrically isolated from the control side), so the
pump circuit does not need to touch the ESP32's ground at all. The ESP32
only drives the relay's IN terminal from GPIO26.

Power path, wired with the charger unplugged:
- charger USB-A port, then a male USB-to-screw-terminal adapter
- that adapter's VBUS to relay COM
- relay NO (normally open, so the pump is off whenever the relay is
  unpowered or the board is rebooting) to the female adapter's VBUS
- first adapter's GND straight through to the female adapter's GND
- pump's USB plug into the female adapter

Use only the VBUS and GND terminals on each adapter, and read the printed
labels on both adapters before wiring. Ignore D+, D- and shield. Use red
wire for the + side and black for the - side, and tug each wire to check
it is held under its screw. Plug the charger in last. Keep the adapters
and relay in the dry zone, because the VBUS terminal is live whenever the
charger is on.

Test script (`esp32/pump_test.py`): set the relay to its off state at
startup, switch it on for a fixed time (`PUMP_SECONDS`), then off. Put
the off command in a `try/finally` so the relay is always released, even
if the script is interrupted.

Do the first run with the pump fully submerged in a jug or cup of water,
over a sink, on a towel. Run it for a few seconds only. Expected: relay
clicks on, pump runs, a second click when it stops.

Because the pump no longer draws through the ESP32's VIN path, its
startup surge shouldn't brown the board out. If the ESP32
resets or Thonny disconnects when the pump starts, note it in the
journey. On this build it does not reset.

Note: if the charger shares an extension lead with the PC, keep the lead
and charger raised and well away from the water.

**Commit point.**

### 1.5 Delivery path and flow rate
Fit the 6mm tubing onto the pump's 8mm nozzle and check it grips. Put the
pump in the reservoir, route the tubing to the plant, and make sure the
outlet is at or above the reservoir's water level, or add a small drip
loop, so water cannot siphon out of the reservoir or run back along the
tubing toward the dry electronics. Time a fixed run (say 5 seconds) into a
measuring jug and record the volume. Also measure how long water takes to
reach the soil probe after a burst. The pump runtime limits and the soak
time both come from these numbers.

**Not done yet.** `PUMP_SECONDS` and `SOAK_SECONDS` stay provisional
until this is measured with the final tubing.

**Commit point.**

### 1.6 Simple local watering
Combine the pieces into one script (`esp32/watering_local.py`): average
ten soil readings, check the float before every burst, run the pump in
short bursts while the soil is above the dry threshold and the reservoir
is OK, wait for the water to reach the probe, then recheck.

Settings sit in named constants at the top of the script. Provisional
values:

| Constant | Value | Meaning |
|---|---|---|
| `RELAY_ON` / `RELAY_OFF` | 1 / 0 | Relay polarity (module triggers on HIGH) |
| `FLOAT_WATER_PRESENT` | 1 | Float reading that means water is present (see ADR-004) |
| `DRY_THRESHOLD` | 1700 | Start watering when the average goes above this |
| `WET_THRESHOLD` | 1300 | Counts as watered once the average drops below this |
| `PUMP_SECONDS` | 5 | Length of one burst (3 s was enough once primed at speed two) |
| `SOAK_SECONDS` | 90 | Wait for water to spread before rechecking |
| `MAX_BURSTS` | 3 | Bursts allowed per watering episode |
| `COOLDOWN_SECONDS` | 1800 | Wait after the soil fails to respond |
| `CHECK_SECONDS` | 60 | Time between soil checks |

The gap between the two thresholds is deliberate hysteresis, far wider
than the ±20 wobble, so the pump does not chatter around one value.

Safeguards, built in from the start:
- Set the relay pin to its off state as the very first line of the
  script, before WiFi or anything else, so a reboot can never leave the
  pump running.
- Wrap the run in `try/finally` so the relay is released however the
  script ends.
- Cap bursts per episode. If the soil never responds after `MAX_BURSTS`,
  enter the cooldown. This also limits dry running if the float ever
  misreports.
- Have the episode return *why* it ended (`WATERED`, `RESERVOIR_LOW` or
  `NO_RESPONSE`). Only `NO_RESPONSE` triggers the cooldown, because a low
  reservoir is fixed by refilling, not by waiting 30 minutes.

Bench-test over the sink with the pump in a cup of water, **forcing the
soil reading in code** rather than moving the probe:

1. Float down, forced dry reading (2500): should report the reservoir is
   low and never run the pump.
2. Float up, forced dry reading: three bursts, then the "still dry"
   message and the cooldown.
3. Forced wet reading (500): only the status line, no pumping.
4. Soil dry, turning wet after the first burst: needs a fake that starts
   at 2500 and returns 500 after about 8 seconds. (Not yet run.)

Tests 1 to 3 passed on this build. Remove any forced reading (such as a
leftover `return 2500` in `read_soil()`) before real use; it must return
the real average, `total // 10`.

Run it from Thonny, **not saved as `main.py`**, until Stage 2.4 is done.

**Commit point and journey entry. Stage 1 is done when the plant gets
watered by itself and stops when the reservoir is empty.** That needs
Step 1.5 and a real plant, so it is still open.

---

## Stage 2 — Safe, non-blocking control

### Why this stage exists
The blocking script in 1.6 uses `time.sleep()` for bursts and soaks. While
it sleeps the ESP32 cannot do anything else, and in Stage 3 that would
mean it could not answer Modbus requests. So the decision logic is
separated from the hardware and rewritten as a state machine that never
sleeps.

### 2.1 Controller state machine and tests (done)
Files, all in `esp32/`:
- `controller.py`: a `WateringController` with four states: `idle`
  (waiting for the next soil check), `pumping` (a timed burst), `soaking`
  (letting water spread before rechecking) and `cooldown` (30 minutes
  after the burst cap is hit with no response). It takes the soil reading
  and reservoir status as functions passed in, so it never touches
  hardware, and it uses elapsed-time checks instead of sleeps.
- `tests/test_controller.py`: pytest tests using a PC-side test rig with
  a fake clock, fake soil sensor and fake reservoir switch.
- `pytest.ini`: contains `[pytest]` and `pythonpath = .` so pytest can
  import `controller.py`.
- `watering_main.py`: the thin hardware layer. It sets the relay off
  first, then calls `controller.update(time.ticks_ms())` every 100 ms.

Behaviour kept from 1.6: check the reservoir before pumping and during
each burst (stop the pump at once if it goes low), cap bursts per
episode, stop when the soil is below the wet threshold, cooldown only
when the soil does not respond, and an immediate soil check at startup.

Run the tests on your PC from the project folder:

```
pytest
```

Result on this build: all 14 tests pass on the PC. They cover wet and dry
soil, reservoir low, five-second bursts, soak and recheck, repeat bursts,
the burst limit, cooldown, reservoir loss mid-burst, pump-state
consistency and timer wraparound.

What this proves: the logic behaves as intended in simulation. What it
does not prove: anything about the real plant, the real sensor or the
real pump.

**Commit point.**

### 2.2 Controller on the board (done)
Upload `controller.py` and `watering_main.py` to the board (File → Save
as → MicroPython device), keeping them out of `main.py`. Then run
`watering_main.py` from Thonny with F5, which runs it on the board
without saving it as the boot script. `controller.py` only needs
re-uploading when it changes.

Setup for each test: pump in a cup of water over the sink, ESP32 on the
PC's USB, charger plugged in last, green relay LED watched. For the tests
that need a soil reading, temporarily force it inside `read_soil()`
(marked `# TEMP FORCED`) and remove it afterwards.

| Test | Setup | Expected | Result |
|---|---|---|---|
| Float down, forced dry (2500) | Float held down | Pump never starts | Pass |
| Float up, forced dry (2500) | Float up | Bursts, soak, rechecks, burst cap, cooldown | Pass |
| Forced wet (500) | Float up | Status lines only, no pump | Pass |
| Dry, then wet after the first burst | Fake returns 2500 for 8 s, then 500 | One burst, soak, "watered enough", no second burst | Pass |
| Float dropped mid-burst | Forced dry, float lowered during a burst | Pump stops at once, no cooldown | Pass |

The ESP32 does not reset or disconnect when the pump starts. All temporary
forced values have been removed and `read_soil()` returns the real average.

What this proves: the controller makes the right decisions on the real
board with the real relay and float. What it does not prove: anything
about the real soil sensor in the real pot, or the final tubing.

**Commit point and journey entry.**

### 2.3 Float fail-safe orientation (decided)
With the float as fitted, a cut or disconnected lead reads 1, which means
"water present". The float cannot be physically reversed, and no code or
wiring change can tell a broken lead from a raised float, so a true
fail-safe was not possible with this part. Changing only
`FLOAT_WATER_PRESENT` was rejected because it would invert the interlock.

Decision: keep `FLOAT_WATER_PRESENT = 1` and rely on the layered
safeguards (relay off at startup, `try/finally` release, 5-second bursts,
the three-burst cap, the cooldown). Recorded in
`decisions/0004-float-orientation-kept.md`. Two ways to get a real
fail-safe remain if it is ever needed: a float whose contact is closed
when the float is up, or a supervised input (a resistor across the switch
read on an ADC1 pin).

Still open: what the second float switch is for (a spare, or an
overflow/high-level check). Stage 6 failure testing should unplug the
float lead and record what the pump does.

### 2.4 Unattended running
Do this only once the delivery path (Step 1.5) is in place and you have
watched the controller water the real plant, attended, from real
readings.

1. Create a `main.py` on the board containing only `import watering_main`.
   This works because the loop in `watering_main.py` runs at the top
   level, not inside a function. To disable auto-start, delete the small
   `main.py`.
2. Power-cycle test: pull the power and confirm the relay stays off during
   boot. Note that the controller does an immediate soil check at startup,
   so if the soil is dry it may start a burst straight away. That is
   intended, but expect it.
3. A running `main.py` can make Thonny harder to connect to. Press Stop or
   Ctrl+C right after connecting, before editing files.
4. Optional extra protection: a hard maximum pump runtime beyond the burst
   cap.
5. Auto/Manual states, needed for control from Ignition, come with
   Stage 3.

---

## Safety checklist for every stage

- No mains electricity anywhere near water. Everything runs from the USB
  charger.
- Electronics (ESP32, relay, USB adapters, wiring) sit in the dry zone,
  above the water level and away from splashes. The charger and any
  shared extension lead stay raised and away from the water too.
- Only the sealed pump, the tubing, the soil probe's lower section and the
  float switch go in or near the water.
- First run of anything involving the pump is over a sink.
- Do not leave the rig running unattended until Stage 2.4 is complete.
  Until then, run scripts from Thonny and never save them as `main.py`.