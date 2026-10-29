import network
import time
import config, wifi
from umodbus.tcp import ModbusTCP

n = 0
t0 = time.ticks_ms()

if not wifi.connect(config.WIFI_SSID, config.WIFI_PASSWORD):
    raise RuntimeError("WiFi failed")

local_ip = network.WLAN(network.STA_IF).ifconfig()[0]
tcp_port = 502

client = ModbusTCP()
if not client.get_bound_status():
    client.bind(local_ip=local_ip, local_port=tcp_port)

register_definitions = {
    "COILS": {"EXAMPLE_COIL": {"register": 123, "len": 1, "val": 1}},
    "HREGS": {"EXAMPLE_HREG": {"register": 93, "len": 1, "val": 19}},
    "ISTS": {"EXAMPLE_ISTS": {"register": 67, "len": 1, "val": 0}},
    "IREGS": {"EXAMPLE_IREG": {"register": 10, "len": 1, "val": 60001}},
}
client.setup_registers(registers=register_definitions)

print("Modbus server listening on", local_ip, tcp_port)

while True:
    try:
        client.process()
    except KeyboardInterrupt:
        print("stopped")
        break
    except Exception as e:
        print("error:", e)
    n += 1
    if time.ticks_diff(time.ticks_ms(), t0) >= 5000:
        print("loops in 5s:", n)
        n = 0
        t0 = time.ticks_ms()