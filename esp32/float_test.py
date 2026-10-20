from machine import Pin
import time

float_sw = Pin(25, Pin.IN, Pin.PULL_UP)

while True:
    print(float_sw.value())
    time.sleep(0.5)
