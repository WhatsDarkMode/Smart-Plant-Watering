# Stage 2: the watering controller running on the ESP32.
# Needs controller.py on the board as well. Run from Thonny while testing.
# Do NOT save as main.py until you have checked it on the real plant.

from machine import ADC, Pin
import time
from controller import WateringController

# ---------- Settings (all provisional, tune as you learn more) ----------
RELAY_ON = 1              # this relay module triggers on HIGH
RELAY_OFF = 0
FLOAT_WATER_PRESENT = 1   # float up reads 1

DRY_THRESHOLD = 1700      # soil average above this = too dry, start watering
WET_THRESHOLD = 1300      # soil average below this = watered enough, stop

PUMP_SECONDS = 5          # length of one watering burst
SOAK_SECONDS = 10         # wait after a burst for water to reach the probe
MAX_BURSTS = 3            # most bursts in one watering episode
COOLDOWN_SECONDS = 1800   # rest after an episode where the soil didn't respond
CHECK_SECONDS = 60        # how often to check the soil normally

STATUS_EVERY_MS = 10000   # how often to print a status line

# ---------- Hardware ----------
relay = Pin(26, Pin.OUT, value=RELAY_OFF)    # off immediately at startup
float_sw = Pin(25, Pin.IN, Pin.PULL_UP)
soil = ADC(Pin(34))
soil.atten(ADC.ATTN_11DB)


def read_soil():
    # Average ten quick readings to smooth out the wobble.
    total = 0
    for _ in range(10):
        total += soil.read()
        time.sleep_ms(20)
    return  2000 # total // 10


def reservoir_ok():
    return float_sw.value() == FLOAT_WATER_PRESENT


controller = WateringController(
    read_soil=read_soil,
    reservoir_ok=reservoir_ok,
    dry_threshold=DRY_THRESHOLD,
    wet_threshold=WET_THRESHOLD,
    pump_ms=PUMP_SECONDS * 1000,
    soak_ms=SOAK_SECONDS * 1000,
    max_bursts=MAX_BURSTS,
    cooldown_ms=COOLDOWN_SECONDS * 1000,
    check_ms=CHECK_SECONDS * 1000,
)

last_message = None
last_status = time.ticks_ms()

try:
    while True:
        now = time.ticks_ms()
        controller.update(now)
        relay.value(RELAY_ON if controller.pump_on else RELAY_OFF)

        if controller.message != last_message:
            print(controller.message)
            last_message = controller.message

        if time.ticks_diff(now, last_status) >= STATUS_EVERY_MS:
            last_status = now
            print(controller.state, "| soil:", controller.last_soil,
                  "| reservoir ok:", reservoir_ok())

        time.sleep_ms(100)
finally:
    relay.value(RELAY_OFF)