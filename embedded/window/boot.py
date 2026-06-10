import network
import espnow
from machine import Pin
import neopixel
import time
import math
import random

# WiFi Station Mode
sta = network.WLAN(network.STA_IF)
sta.active(True)

# ESP-NOW
e = espnow.ESPNow()
e.active(True)

# LED Setup
NUM_LEDS = 74 * 2
LED_PIN = 13
leds = neopixel.NeoPixel(Pin(LED_PIN), NUM_LEDS, bpp=4)

BRIGHTNESS = 0.5
current_pattern = 0

# Animation state
frame = 0
comet_pos = 0
comet_dir = 1
wipe_pos = 0
wipe_color_idx = 0

ANIMATED = (8, 9, 10, 11, 12, 13, 14, 15)
WIPE_COLORS = [(255, 0, 0, 0), (0, 255, 0, 0), (0, 0, 255, 0), (0, 0, 0, 255)]


def scale_color(color):
    return tuple(int(c * BRIGHTNESS) for c in color)


def wheel(pos):
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3, 0)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3, 0)


def solid_color(color):
    leds.fill(scale_color(color))
    leds.write()


def decay(factor_num=7, factor_den=10):
    for i in range(NUM_LEDS):
        r, g, b, w = leds[i]
        leds[i] = (r * factor_num // factor_den, g * factor_num // factor_den,
                   b * factor_num // factor_den, w * factor_num // factor_den)


# ---------- STATIC PATTERNS (drawn once on change) ----------

def static_gradient():
    # Magenta -> cyan across the strip
    for i in range(NUM_LEDS):
        t = i / (NUM_LEDS - 1)
        r = int(255 * (1 - t))
        g = int(255 * t)
        b = 255
        leds[i] = scale_color((r, g, b, 0))
    leds.write()


def static_rainbow():
    for i in range(NUM_LEDS):
        leds[i] = scale_color(wheel((i * 256 // NUM_LEDS) & 255))
    leds.write()


def static_bands():
    # Three equal R / G / B bands
    third = NUM_LEDS // 3
    for i in range(NUM_LEDS):
        if i < third:
            leds[i] = scale_color((255, 0, 0, 0))
        elif i < third * 2:
            leds[i] = scale_color((0, 255, 0, 0))
        else:
            leds[i] = scale_color((0, 0, 255, 0))
    leds.write()


# ---------- ANIMATED PATTERNS (one step per call) ----------

def anim_rainbow_cycle():
    for i in range(NUM_LEDS):
        leds[i] = scale_color(wheel(((i * 256 // NUM_LEDS) + frame) & 255))
    leds.write()


def anim_comet():
    global comet_pos
    decay(6, 10)
    leds[comet_pos] = scale_color(wheel((frame * 2) & 255))
    comet_pos = (comet_pos + 1) % NUM_LEDS
    leds.write()


def anim_theater_chase():
    color = wheel((frame * 3) & 255)
    for i in range(NUM_LEDS):
        leds[i] = scale_color(color) if (i + frame) % 3 == 0 else (0, 0, 0, 0)
    leds.write()


def anim_color_wipe():
    global wipe_pos, wipe_color_idx
    leds[wipe_pos] = scale_color(WIPE_COLORS[wipe_color_idx])
    wipe_pos += 1
    if wipe_pos >= NUM_LEDS:
        wipe_pos = 0
        wipe_color_idx = (wipe_color_idx + 1) % len(WIPE_COLORS)
    leds.write()


def anim_twinkle():
    decay(8, 10)
    for _ in range(3):
        i = random.randint(0, NUM_LEDS - 1)
        leds[i] = scale_color((255, 255, 255, 100))
    leds.write()


def anim_fire():
    for i in range(NUM_LEDS):
        flicker = random.randint(100, 255)
        leds[i] = scale_color((flicker, flicker * 50 // 255, 0, 0))
    leds.write()


def anim_breathing():
    factor = (math.sin(frame / 18.0) + 1) / 2  # 0..1
    color = wheel((frame // 2) & 255)
    leds.fill(tuple(int(c * BRIGHTNESS * factor) for c in color))
    leds.write()


def anim_bounce():
    global comet_pos, comet_dir
    decay(5, 10)
    leds[comet_pos] = scale_color((0, 150, 255, 0))
    comet_pos += comet_dir
    if comet_pos >= NUM_LEDS - 1 or comet_pos <= 0:
        comet_dir *= -1
    leds.write()


# Speed per animated pattern (ms between steps)
DELAYS = {8: 20, 9: 15, 10: 60, 11: 10, 12: 50, 13: 60, 14: 20, 15: 12}

last_pattern = None

while True:
    # Non-blocking receive
    # Non-blocking receive
    host, message = e.recv(0)
    if message:
        current_pattern = int.from_bytes(message, "big")
        print("Received Pattern ID:", current_pattern)
        last_pattern = None          # force static redraw
        frame = 0                    # restart animations
        comet_pos = 0
        comet_dir = 1
        wipe_pos = 0
        wipe_color_idx = 0

    # Static patterns: draw once on change
    if current_pattern != last_pattern:
        if current_pattern == 0:
            solid_color((0, 0, 0, 0)); print("Off")
        elif current_pattern == 1:
            solid_color((255, 0, 0, 0)); print("Red")
        elif current_pattern == 2:
            solid_color((0, 255, 0, 0)); print("Green")
        elif current_pattern == 3:
            solid_color((0, 0, 255, 0)); print("Blue")
        elif current_pattern == 4:
            solid_color((0, 0, 0, 255)); print("Warm White (W)")
        elif current_pattern == 5:
            static_gradient(); print("Gradient")
        elif current_pattern == 6:
            static_rainbow(); print("Static Rainbow")
        elif current_pattern == 7:
            static_bands(); print("RGB Bands")
        last_pattern = current_pattern

    # Animated patterns: step every loop
    if current_pattern in ANIMATED:
        if current_pattern == 8:
            anim_rainbow_cycle()
        elif current_pattern == 9:
            anim_comet()
        elif current_pattern == 10:
            anim_theater_chase()
        elif current_pattern == 11:
            anim_color_wipe()
        elif current_pattern == 12:
            anim_twinkle()
        elif current_pattern == 13:
            anim_fire()
        elif current_pattern == 14:
            anim_breathing()
        elif current_pattern == 15:
            anim_bounce()
        frame += 1
        time.sleep_ms(DELAYS[current_pattern])
    else:
        time.sleep_ms(1)