from machine import Pin
import time

RELAY_ON = 1
RELAY_OFF = 0
PUMP_SECONDS = 3 #Speed setting 2 on the pump

relay = Pin(26, Pin.OUT, value=RELAY_OFF)

try:
    print("pump on")
    relay.value(RELAY_ON)
    time.sleep(PUMP_SECONDS)
finally:
    relay.value(RELAY_OFF)
    print("pump off")