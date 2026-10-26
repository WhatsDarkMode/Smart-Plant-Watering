from machine import ADC, Pin
import time

# ---------- Settings (all provisional, tune as you learn more) ----------
RELAY_ON = 1              # this relay module triggers on HIGH
RELAY_OFF = 0
FLOAT_WATER_PRESENT = 1   # float up reads 1

DRY_THRESHOLD = 1700      # soil average above this = too dry, start watering
WET_THRESHOLD = 1300      # soil average below this = watered enough, stop

PUMP_SECONDS = 5          # length of one watering burst
SOAK_SECONDS = 90         # wait after a burst for water to reach the probe
MAX_BURSTS = 3            # most bursts in one watering episode
COOLDOWN_SECONDS = 1800   # rest after a failed episode before trying again
CHECK_SECONDS = 60        # how often to check the soil normally

WATERED = "watered"
RESERVOIR_LOW = "reservoir_low"
NO_RESPONSE = "no_response"

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
    return 2500 # total // 10


def reservoir_ok():
    return float_sw.value() == FLOAT_WATER_PRESENT


def run_pump(seconds):
    # The relay is always switched off afterwards, even if interrupted.
    try:
        relay.value(RELAY_ON)
        time.sleep(seconds)
    finally:
        relay.value(RELAY_OFF)


def water_episode():
    # Returns why the episode ended: WATERED, RESERVOIR_LOW or NO_RESPONSE.
    for burst in range(1, MAX_BURSTS + 1):
        if not reservoir_ok():
            return RESERVOIR_LOW
        print("burst", burst)
        run_pump(PUMP_SECONDS)
        time.sleep(SOAK_SECONDS)
        moisture = read_soil()
        print("after burst:", moisture)
        if moisture < WET_THRESHOLD:
            return WATERED
    return NO_RESPONSE
 
 
try:
    while True:
        moisture = read_soil()
        print("soil:", moisture, "| reservoir ok:", reservoir_ok())
        if moisture > DRY_THRESHOLD:
            if not reservoir_ok():
                print("soil is dry but reservoir is low: not watering")
            else:
                result = water_episode()
                if result == WATERED:
                    print("watered enough")
                elif result == RESERVOIR_LOW:
                    print("reservoir ran low during watering: stopped")
                else:
                    print("soil still dry after", MAX_BURSTS, "bursts: "
                          "check pump, tubing, probe.")
                    print("cooling down for", COOLDOWN_SECONDS, "seconds")
                    time.sleep(COOLDOWN_SECONDS)
        time.sleep(CHECK_SECONDS)
finally:
    relay.value(RELAY_OFF)