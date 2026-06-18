from machine import Pin
import neopixel
import time
import network
import espnow

# === Configuration ===
LED_PIN1 = 18
LED_PIN2 = 21
NUM_LEDS_PER_STRIP = 16
BRIGHTNESS = 0.05
DELAY = 0.015  # faster update rate for smoother swirl

# === ESP-NOW Setup ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

esp = espnow.ESPNow()
esp.active(True)

receivers = [
    b'\x08\xa6\xf7\xbc\xf5\x08',  # window
    b'\x08\xa6\xf7\xbd\x18\x10',  # tv lamps
]
for r in receivers:
    esp.add_peer(r)

# === Buttons ===
BUTTON_PINS = [4,5,6,7,8,17,16,15,3,9,10,11,1,2,12,13]
buttons = [Pin(pin, Pin.IN, Pin.PULL_UP) for pin in BUTTON_PINS]
prev_states = [1] * len(buttons)  # previous button state (1=not pressed, 0=pressed)

# === LEDs ===
np1 = neopixel.NeoPixel(Pin(LED_PIN1, Pin.OUT), NUM_LEDS_PER_STRIP, bpp=3)
np2 = neopixel.NeoPixel(Pin(LED_PIN2, Pin.OUT), NUM_LEDS_PER_STRIP, bpp=3)

r = int(255 * BRIGHTNESS)
START_COLOR = (0, r, r)

for i in range(NUM_LEDS_PER_STRIP):
    np1[i] = START_COLOR
    np2[i] = START_COLOR
np1.write()
np2.write()

# Explicit mapping: button_index -> (strip, led1, led2)
BUTTON_LED_MAP = [
    (np1, 0,1), (np1, 2,3), (np1, 4,5), (np1, 6,7),
    (np1, 8,9), (np1,10,11), (np1,12,13), (np1,14,15),
    (np2, 0,1), (np2, 2,3), (np2, 4,5), (np2, 6,7),
    (np2, 8,9), (np2,10,11), (np2,12,13), (np2,14,15)
]

# === Color Wheel ===
def button_light_wheel(pos):
    pos = pos % 256
    if pos < 85:
        return (int(pos*3*BRIGHTNESS), int((255-pos*3)*BRIGHTNESS), 0)
    elif pos < 170:
        pos -= 85
        return (int((255-pos*3)*BRIGHTNESS), 0, int(pos*3*BRIGHTNESS))
    else:
        pos -= 170
        return (0, int(pos*3*BRIGHTNESS), int((255-pos*3)*BRIGHTNESS))

# Keep track of color position per button
wheel_pos = [0] * len(buttons)

# === Send Pattern ===
def send_pattern(pattern_id):
    try:
        for r in receivers:
            esp.send(r, bytes([pattern_id]))
        print(f"Sent pattern {pattern_id}")
    except Exception as e:
        print(f"Error sending pattern {pattern_id}: {e}")

# === Main Loop ===
while True:
    strip1_colors = [START_COLOR] * NUM_LEDS_PER_STRIP
    strip2_colors = [START_COLOR] * NUM_LEDS_PER_STRIP

    for i, button in enumerate(buttons):
        current = button.value()
        prev = prev_states[i]

        strip, led1, led2 = BUTTON_LED_MAP[i]

        if current == 0:  # pressed
            color1 = button_light_wheel(wheel_pos[i])
            color2 = button_light_wheel((wheel_pos[i]+32) % 256)
            wheel_pos[i] = (wheel_pos[i] + 10) % 256
        else:
            color1 = START_COLOR
            color2 = START_COLOR
            wheel_pos[i] = 0

        # Detect *new* press (transition from 1 → 0)
        if prev == 1 and current == 0:
            send_pattern(i)

        prev_states[i] = current  # update state

        # Apply LED color changes
        if strip == np1:
            strip1_colors[led1] = color1
            strip1_colors[led2] = color2
        else:
            strip2_colors[led1] = color1
            strip2_colors[led2] = color2

    # Write both strips at once
    for i in range(NUM_LEDS_PER_STRIP):
        np1[i] = strip1_colors[i]
        np2[i] = strip2_colors[i]

    np1.write()
    np2.write()

    time.sleep(DELAY)

