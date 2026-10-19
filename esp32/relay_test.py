from machine import Pin
import time

RELAY_ON = 1
RELAY_OFF = 0

relay = Pin(26, Pin.OUT, value=RELAY_OFF)
print("should be OFF")
time.sleep(3)
print("on")
relay.value(RELAY_ON)
time.sleep(3)
print("off")
relay.value(RELAY_OFF)
time.sleep(3)
print("done")