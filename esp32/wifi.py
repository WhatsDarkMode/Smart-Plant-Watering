import network
import time

def connect(wifi_ssid, wifi_password):
    sta_if = network.WLAN(network.WLAN.IF_STA)
    sta_if.active(True)

    if not sta_if.isconnected():
        print("Connecting to WiFi...")
        sta_if.connect(wifi_ssid, wifi_password)

        timeout = 20

        while not sta_if.isconnected() and timeout > 0:
            time.sleep(1) 
            timeout -= 1

    return sta_if.isconnected()