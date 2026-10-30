# PC-side helper for testing the ESP32's Modbus registers.
# Usage (Command Prompt):  python modbus_check.py <command>
# Commands: read, manual, auto, pump, badmode, badthresh, resetthresh
# Do NOT name this file pymodbus.py.

import sys
import time
from pymodbus.client import ModbusTcpClient

IP = "192.168.1.67"      # the ESP32's address
PORT = 502

STATES = {0: "idle", 1: "pumping", 2: "soaking", 3: "cooldown",
          4: "manual", 5: "manual pumping"}
FAULTS = {0: "ok", 1: "reservoir low", 2: "manual refused",
          3: "soil not responding"}
MODES = {0: "Auto", 1: "Manual"}

c = ModbusTcpClient(IP, port=PORT)
if not c.connect():
    sys.exit("Could not connect to %s:%s. Is watering_main.py running?"
             % (IP, PORT))


def show():
    ir = c.read_input_registers(0, count=7).registers
    hr = c.read_holding_registers(0, count=3).registers
    coil = c.read_coils(0, count=1).bits[:1]
    print("mode              :", hr[2], MODES.get(hr[2], "?"))
    print("dry threshold     :", hr[0])
    print("wet threshold     :", hr[1])
    print("manual request    :", coil[0])
    print("soil              :", ir[0])
    print("state             :", ir[1], STATES.get(ir[1], "?"))
    print("burst count       :", ir[2])
    print("heartbeat (s)     :", ir[3])
    print("fault             :", ir[4], FAULTS.get(ir[4], "?"))
    print("pump on           :", bool(ir[5]))
    print("reservoir ok      :", bool(ir[6]))


def write_reg(address, value):
    r = c.write_register(address, value)
    print("write register", address, "=", value,
          "->", "ERROR" if r.isError() else "ok")
    time.sleep(0.5)     # let the board's loop pick it up


cmd = sys.argv[1] if len(sys.argv) > 1 else "read"

if cmd == "read":
    show()
elif cmd == "manual":
    write_reg(2, 1)
    show()
elif cmd == "auto":
    write_reg(2, 0)
    show()
elif cmd == "pump":
    r = c.write_coil(0, True)
    print("write coil 0 = True ->", "ERROR" if r.isError() else "ok")
    for _ in range(8):
        time.sleep(1)
        ir = c.read_input_registers(1, count=5).registers
        state = ir[0]
        pump = bool(ir[4])
        coil = c.read_coils(0, count=1).bits[0]
        print("state:", STATES.get(state, state), "| pump on:", pump,
              "| coil:", coil)
elif cmd == "badmode":
    write_reg(2, 9)
    print("(mode should be unchanged)")
    show()
elif cmd == "badthresh":
    write_reg(0, 5000)
    write_reg(1, 100)
    print("(expect dry 4000, wet 100)")
    show()
elif cmd == "resetthresh":
    write_reg(0, 1700)
    write_reg(1, 1300)
    show()
else:
    print("unknown command:", cmd)

c.close()