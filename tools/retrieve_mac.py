import network
import ubinascii

# Start the Wi-Fi interface
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Retrieve and format the MAC address
raw_mac = wlan.config('mac')

print("Device MAC Address:", raw_mac)