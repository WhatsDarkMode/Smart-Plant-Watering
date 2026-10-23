from machine import ADC, Pin
import time

soil = ADC(Pin(34))
soil.atten(ADC.ATTN_11DB)

while True:
    print(soil.read())
    time.sleep(1)