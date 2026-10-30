# Stage 3: the watering controller on the ESP32, with Modbus TCP.
# Needs controller.py, config.py and the umodbus library on the board.
# Run from Thonny while testing. Do NOT save as main.py until you have
# checked it on the real plant.
#
# Local control comes first: the controller runs whether or not WiFi, the
# Modbus library or Ignition are available. Nothing in the Modbus code is
# allowed to block the loop or stop it.

from machine import ADC, Pin

# ---------- Relay first: off before anything else happens ----------
RELAY_ON = 1              # this relay module triggers on HIGH
RELAY_OFF = 0
relay = Pin(26, Pin.OUT, value=RELAY_OFF)    # off immediately at startup

import time
import network
from controller import (WateringController, MODE_AUTO, MODE_MANUAL,
                        FAULT_NONE)

try:
    import config
except ImportError:
    config = None
    print("no config.py: running without WiFi or Modbus")

try:
    from umodbus.tcp import ModbusTCP
except ImportError:
    ModbusTCP = None
    print("umodbus not installed: running without Modbus")

# ---------- Settings (all provisional, tune as you learn more) ----------
FLOAT_WATER_PRESENT = 1   # float up reads 1 (known weakness, see ADR-004)

DRY_THRESHOLD = 1700      # soil average above this = too dry, start watering
WET_THRESHOLD = 1300      # soil average below this = watered enough, stop

PUMP_SECONDS = 5          # length of one watering burst
SOAK_SECONDS = 90         # wait after a burst for water to reach the probe
MAX_BURSTS = 3            # most bursts in one watering episode
COOLDOWN_SECONDS = 1800   # rest after an episode where the soil didn't respond
CHECK_SECONDS = 60        # how often to check the soil normally

# Manual mode (from Ignition). Fixed here, never settable over Modbus.
MANUAL_PUMP_SECONDS = 5       # one manual burst
MANUAL_GAP_SECONDS = 10       # rest between manual bursts
MANUAL_TIMEOUT_SECONDS = 600  # no manual activity for this long: back to Auto
MANUAL_BUDGET_SECONDS = 60    # most manual pump time in one hour

LOOP_MS = 100             # main loop pause
STATUS_EVERY_MS = 10000   # how often to print a status line
WIFI_RETRY_MS = 30000     # how often to retry a dropped WiFi connection
SERVER_RETRY_MS = 10000   # how often to retry starting the Modbus server
MODBUS_PORT = 502

# ---------- Modbus register map (addresses are 0-based) ----------
# Coil (Ignition writes)
COIL_MANUAL_PUMP = 0      # 1 = request one manual burst (Manual mode only)
# Holding registers (Ignition writes; thresholds are clamped)
HREG_DRY = 0              # dry threshold
HREG_WET = 1              # wet threshold
HREG_MODE = 2             # 0 = Auto, 1 = Manual
# Input registers (read-only)
IREG_SOIL = 0             # latest averaged soil reading
IREG_STATE = 1            # 0 idle 1 pumping 2 soaking 3 cooldown
                          # 4 manual 5 manual pumping
IREG_BURSTS = 2           # bursts so far in this episode
IREG_HEARTBEAT = 3        # seconds counter, wraps at 65535
IREG_FAULT = 4            # 0 ok 1 reservoir low 2 manual refused
                          # 3 soil not responding
IREG_PUMP_ON = 5          # 0 or 1
IREG_RESERVOIR_OK = 6     # 0 or 1
# There are deliberately no discrete inputs: the library returns the bits
# of a multi-bit read in reverse order, so on/off values live in registers.

# ---------- Hardware ----------
float_sw = Pin(25, Pin.IN, Pin.PULL_UP)
soil = ADC(Pin(34))
soil.atten(ADC.ATTN_11DB)


def read_soil():
    # Average ten quick readings to smooth out the wobble.
    total = 0
    for _ in range(10):
        total += soil.read()
        time.sleep_ms(20)
    return total // 10


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
    manual_pump_ms=MANUAL_PUMP_SECONDS * 1000,
    manual_gap_ms=MANUAL_GAP_SECONDS * 1000,
    manual_timeout_ms=MANUAL_TIMEOUT_SECONDS * 1000,
    manual_budget_ms=MANUAL_BUDGET_SECONDS * 1000,
)

# ---------- WiFi (never blocks) ----------
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
last_wifi_try = time.ticks_ms()


def wifi_connect():
    # connect() returns straight away; the connection completes later.
    try:
        sta.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    except OSError as e:
        print("WiFi connect error:", e)


if config is not None:
    wifi_connect()


def wifi_watch(now):
    global last_wifi_try
    if (config is not None and not sta.isconnected()
            and time.ticks_diff(now, last_wifi_try) >= WIFI_RETRY_MS):
        last_wifi_try = now
        print("WiFi down: retrying")
        wifi_connect()


# ---------- Modbus ----------
server = None
last_server_try = time.ticks_add(time.ticks_ms(), -SERVER_RETRY_MS)
heartbeat = 0
last_beat = time.ticks_ms()
last_error = None
last_error_time = 0


def modbus_error(where, e):
    # Print a Modbus problem, but not on every loop pass.
    global last_error, last_error_time
    text = "modbus %s: %r" % (where, e)
    now = time.ticks_ms()
    if text != last_error or time.ticks_diff(now, last_error_time) >= 10000:
        print(text)
        last_error = text
        last_error_time = now


def build_registers():
    return {
        "COILS": {
            "MANUAL_PUMP": {"register": COIL_MANUAL_PUMP, "len": 1,
                            "val": 0},
        },
        "HREGS": {
            "DRY": {"register": HREG_DRY, "len": 1, "val": DRY_THRESHOLD},
            "WET": {"register": HREG_WET, "len": 1, "val": WET_THRESHOLD},
            "MODE": {"register": HREG_MODE, "len": 1, "val": MODE_AUTO},
        },
        "IREGS": {
            "SOIL": {"register": IREG_SOIL, "len": 1, "val": 0},
            "STATE": {"register": IREG_STATE, "len": 1, "val": 0},
            "BURSTS": {"register": IREG_BURSTS, "len": 1, "val": 0},
            "HEARTBEAT": {"register": IREG_HEARTBEAT, "len": 1, "val": 0},
            "FAULT": {"register": IREG_FAULT, "len": 1, "val": 0},
            "PUMP_ON": {"register": IREG_PUMP_ON, "len": 1, "val": 0},
            "RESERVOIR_OK": {"register": IREG_RESERVOIR_OK, "len": 1,
                             "val": 0},
        },
    }


def first(value):
    # The library may hand back a bare value or a one-item list.
    if isinstance(value, (list, tuple)):
        return value[0] if value else 0
    return value


def clamp16(value):
    return max(0, min(65535, int(value)))


def start_server_if_needed(now):
    global server, last_server_try
    if (server is not None or ModbusTCP is None or config is None
            or not sta.isconnected()
            or time.ticks_diff(now, last_server_try) < SERVER_RETRY_MS):
        return
    last_server_try = now
    try:
        ip = sta.ifconfig()[0]
        srv = ModbusTCP()
        if not srv.get_bound_status():
            srv.bind(local_ip=ip, local_port=MODBUS_PORT)
        srv.setup_registers(registers=build_registers())
        server = srv
        print("Modbus server listening on", ip, MODBUS_PORT)
    except Exception as e:
        modbus_error("start", e)


def modbus_in(now):
    # Answer requests, then apply anything Ignition has written.
    if server is None:
        return
    try:
        server.process()

        mode = first(server.get_hreg(HREG_MODE))
        if mode != controller.mode:
            controller.set_mode(mode, now)      # invalid values are ignored

        dry = first(server.get_hreg(HREG_DRY))
        wet = first(server.get_hreg(HREG_WET))
        if dry != controller.dry_threshold or wet != controller.wet_threshold:
            controller.set_thresholds(dry, wet)

        if first(server.get_coil(COIL_MANUAL_PUMP)):
            controller.manual_request = True
    except Exception as e:
        modbus_error("in", e)


def modbus_out():
    # Publish the controller's state, and write back anything it changed or
    # refused (clamped thresholds, the mode, the consumed manual request).
    if server is None:
        return
    try:
        server.set_hreg(HREG_DRY, controller.dry_threshold)
        server.set_hreg(HREG_WET, controller.wet_threshold)
        server.set_hreg(HREG_MODE, controller.mode)
        server.set_coil(COIL_MANUAL_PUMP, False)
        server.set_ireg(IREG_SOIL, clamp16(controller.last_soil or 0))
        server.set_ireg(IREG_STATE, controller.state_code)
        server.set_ireg(IREG_BURSTS, clamp16(controller.bursts))
        server.set_ireg(IREG_HEARTBEAT, heartbeat)
        server.set_ireg(IREG_FAULT, controller.fault)
        server.set_ireg(IREG_PUMP_ON, 1 if controller.pump_on else 0)
        server.set_ireg(IREG_RESERVOIR_OK, 1 if reservoir_ok() else 0)
    except Exception as e:
        modbus_error("out", e)


# ---------- Main loop ----------
last_message = None
last_status = time.ticks_ms()

try:
    while True:
        now = time.ticks_ms()

        if time.ticks_diff(now, last_beat) >= 1000:
            last_beat = time.ticks_add(last_beat, 1000)
            heartbeat = (heartbeat + 1) & 0xFFFF

        wifi_watch(now)
        start_server_if_needed(now)
        modbus_in(now)

        controller.update(now)
        relay.value(RELAY_ON if controller.pump_on else RELAY_OFF)

        modbus_out()

        if controller.message != last_message:
            print(controller.message)
            last_message = controller.message

        if time.ticks_diff(now, last_status) >= STATUS_EVERY_MS:
            last_status = now
            print(controller.state, "| mode:", controller.mode,
                  "| soil:", controller.last_soil,
                  "| reservoir ok:", reservoir_ok(),
                  "| fault:", controller.fault,
                  "| modbus:", server is not None)

        time.sleep_ms(LOOP_MS)
finally:
    relay.value(RELAY_OFF)