# Smart Plant Watering — Build Guide (Stage 0 and Stage 1)

Companion to `plant-project-summary.md`. Covers preparing the repo and
board (Stage 0) and getting local watering working with no Ignition
(Stage 1), in small steps that each prove one thing in isolation. Stages
2-7 follow the plan in the original project draft and get their own
guide once Stage 1 is done.

As with the sensor project, record what you actually did in
`build-journey.md`, not what this guide says you should do.

---

## Pin plan (verify against your board's printed labels first)

| Function | ESP32 pin | Why this pin |
|---|---|---|
| Soil sensor analog out | GPIO34 | ADC1 pin. ADC2 pins stop working once WiFi is on, which Stage 3 needs. GPIO34 is input-only, which is fine for a sensor. |
| Float switch | GPIO27 | Has an internal pull-up. GPIO34-39 do not, so avoid those for this. |
| Relay IN | GPIO26 | Stays quiet at boot. Pins like 0, 2, 5, 12, 15 toggle during boot and could blip the pump. |
| Sensor/relay logic power | 3.3V (soil sensor), VIN/5V (relay) | See the power notes in Step 1.3. |
| Ground | GND | The ESP32, sensors and the relay's control side share one ground. The pump's supply circuit stays separate (see Step 1.4). |

---

## Stage 0 — Prepare the repo and the board

### 0.1 Create the repo
New GitHub repo (separate from the sensor project), cloned locally, with
this structure:

```
plant-project/
├── esp32/
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
  exists. It is gitignored, so it is not in the repo, and the copy on the
  board is the only other one.
- The sensor project's code is all in its repo, so nothing in the repo is
  lost by clearing the board.

### 0.3 Clear the old program off the board
The board currently has the sensor project's `main.py`, which runs
automatically on every boot. With the BME280 unplugged it would crash at
startup; with it plugged in it would keep posting to your live dashboard.
In Thonny, open **View → Files**, find `main.py` in the device pane,
right-click it and delete it from the device. Then unplug the BME280's
four jumper wires from GPIO21/22 and 3.3V/GND.

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

Calibrate: record the value with the sensor dry in air, then with the
probe in a cup of water (only up to the marked line, keeping the
component end dry). A capacitive sensor reads **higher when dry and lower
when wet**, which is the opposite of what most people expect. Write both
numbers into your notes; Stage 2's threshold depends on them.

Optional: the exposed PCB edges can absorb water over time. A coat of
clear nail varnish on the edges is a common cheap fix.

**Commit point.**

### 1.2 Float switch
Wiring: one lead to GPIO27, the other to GND. The leads are bare wire, so
join each to a jumper wire (cut a spare jumper's connector off, strip it,
twist it to the lead and tape it for bench testing).

```python
from machine import Pin
float_sw = Pin(27, Pin.IN, Pin.PULL_UP)
print(float_sw.value())
```

Hold the float in a cup of water at different heights and note which
value means "water present" and which means "water low". Whether the
switch is normally open or normally closed depends on its orientation,
and getting this backwards would silently invert your interlock, so test
it rather than assuming.

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
reboot could start the pump.

With the cap on H, the ESP32's 3.3V is a clean on-signal. The quirk where
3.3V HIGH fails to fully release a relay applies to low-level-trigger
setups, so leave the cap on H.

**Commit point.**

### 1.4 Pump on the relay, in a cup of water
The pump has its own supply path, separate from the ESP32's. The relay
contacts are dry (electrically isolated from the control side), so the
pump circuit does not need to touch the ESP32's ground at all.

Power path, wired with the charger unplugged:
- charger USB-A port, then a male USB-to-screw-terminal adapter
- that adapter's VBUS to relay COM
- relay NO (normally open, so the pump is off whenever the relay is
  unpowered or the board is rebooting) to the female adapter's VBUS
- first adapter's GND straight through to the female adapter's GND
- pump's USB plug into the female adapter

Use only the VBUS and GND terminals on each adapter. Plug the charger in
last. Keep the adapters and relay in the dry zone, because the VBUS
terminal is live whenever the charger is on.

Do the first run with the pump sitting in a cup of water, over a sink, on
a towel. Run it for three seconds, then stop.

Because the pump no longer draws through the ESP32's VIN path, its
startup surge shouldn't brown the board out. If the ESP32 still resets
when the pump starts, note it in the journey.

**Commit point.**

### 1.5 Delivery path and flow rate
Fit the 6mm tubing onto the pump's 8mm nozzle and check it grips. Put the
pump in the reservoir, route the tubing to the plant, and leave a small
drip loop so water cannot run back along the tubing toward the dry
electronics. Time a fixed run (say 5 seconds) into a measuring jug and
record the volume. Stage 2's pump runtime limits come from this number.

**Commit point.**

### 1.6 Simple local watering
Combine the pieces into one script: read soil, check the float switch,
run the pump while the soil is above your dry threshold and the reservoir
is OK, stop when it drops below. This is deliberately crude; hysteresis,
maximum runtime, and Auto/Manual states belong to Stage 2.

Set the relay pin to its off state as the very first line of the script,
before WiFi or anything else, so a reboot can never leave the pump running.

**Commit point and journey entry. Stage 1 is done when the plant gets
watered by itself and stops when the reservoir is empty.**

---

## Safety checklist for every stage

- No mains electricity anywhere near water. Everything runs from the USB
  charger.
- Electronics (ESP32, relay, USB adapter, wiring) sit in the dry zone,
  above the water level and away from splashes.
- Only the sealed pump, the tubing, the soil probe's lower section and the
  float switch go in or near the water.
- First run of anything involving the pump is over a sink.
- Do not leave the rig running unattended until the maximum-runtime
  protection from Stage 2 is in place.