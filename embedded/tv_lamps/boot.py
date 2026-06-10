import network
import espnow
from machine import Pin
import neopixel
import time
import math
import random

# WiFi Station Mode (required for ESP-NOW)
sta = network.WLAN(network.STA_IF)
sta.active(True)

# ESP-NOW
e = espnow.ESPNow()
e.active(True)

# LED Setup -- two identical 10-pixel RGB strips, mirrored on pins 14 and 27
NUM_LEDS = 10
LED_PINS = (14, 27)
_strips = [neopixel.NeoPixel(Pin(p), NUM_LEDS, bpp=3) for p in LED_PINS]


class MirroredStrips:
    """Fans every pixel operation out to all physical strips so they stay in
    lockstep. Patterns can keep treating `leds` as a single NeoPixel."""

    def __init__(self, strips):
        self._strips = strips

    def __setitem__(self, i, value):
        for s in self._strips:
            s[i] = value

    def __getitem__(self, i):
        # Strips are identical, so reading the first is representative.
        return self._strips[0][i]

    def fill(self, value):
        for s in self._strips:
            s.fill(value)

    def write(self):
        for s in self._strips:
            s.write()


leds = MirroredStrips(_strips)

BRIGHTNESS = 0.5
current_pattern = 0

# Animation state
frame = 0
comet_pos = 0
comet_dir = 1
wipe_pos = 0
wipe_color_idx = 0

ANIMATED = (8, 9, 10, 11, 12, 13, 14, 15)
# RGB only -- white slot dropped, white wipe color is full RGB white
WIPE_COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]


def scale_color(color):
    # Patterns are written in RGB; strip expects GRB on the wire, so swap here.
    r, g, b = color
    return (int(g * BRIGHTNESS), int(r * BRIGHTNESS), int(b * BRIGHTNESS))


def wheel(pos):
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


def solid_color(color):
    leds.fill(scale_color(color))
    leds.write()


def decay(factor_num=7, factor_den=10):
    for i in range(NUM_LEDS):
        r, g, b = leds[i]
        leds[i] = (r * factor_num // factor_den, g * factor_num // factor_den,
                   b * factor_num // factor_den)


# ---------- STATIC PATTERNS (drawn once on change) ----------

def static_gradient():
    # Magenta -> cyan across the strip
    for i in range(NUM_LEDS):
        t = i / (NUM_LEDS - 1)
        r = int(255 * (1 - t))
        g = int(255 * t)
        b = 255
        leds[i] = scale_color((r, g, b))
    leds.write()


def static_rainbow():
    for i in range(NUM_LEDS):
        leds[i] = scale_color(wheel((i * 256 // NUM_LEDS) & 255))
    leds.write()


def static_bands():
    # Three roughly equal R / G / B bands
    third = NUM_LEDS // 3
    for i in range(NUM_LEDS):
        if i < third:
            leds[i] = scale_color((255, 0, 0))
        elif i < third * 2:
            leds[i] = scale_color((0, 255, 0))
        else:
            leds[i] = scale_color((0, 0, 255))
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
        leds[i] = scale_color(color) if (i + frame) % 3 == 0 else (0, 0, 0)
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
        leds[i] = scale_color((255, 255, 255))
    leds.write()


def anim_fire():
    for i in range(NUM_LEDS):
        flicker = random.randint(100, 255)
        leds[i] = scale_color((flicker, flicker * 50 // 255, 0))
    leds.write()


def anim_breathing():
    factor = (math.sin(frame / 18.0) + 1) / 2  # 0..1
    r, g, b = wheel((frame // 2) & 255)
    leds.fill((int(g * BRIGHTNESS * factor), int(r * BRIGHTNESS * factor),
               int(b * BRIGHTNESS * factor)))
    leds.write()


def anim_bounce():
    global comet_pos, comet_dir
    decay(5, 10)
    leds[comet_pos] = scale_color((0, 150, 255))
    comet_pos += comet_dir
    if comet_pos >= NUM_LEDS - 1 or comet_pos <= 0:
        comet_dir *= -1
    leds.write()


# Speed per animated pattern (ms between steps).
# Length-dependent patterns (a pixel travels the strip) are derived from
# NUM_LEDS so one full lap/wipe/sweep takes the same wall-clock time as the
# original 148-pixel strip. Length-independent patterns keep their fixed delay.
DELAYS = {
    8: 20,                              # rainbow cycle: 256-frame loop, length-independent
    9: max(1, 2220 // NUM_LEDS),        # comet: full lap ~2220 ms (148 * 15)
    10: 60,                             # theater chase: 3-frame loop, length-independent
    11: max(1, 1480 // NUM_LEDS),       # color wipe: full wipe ~1480 ms (148 * 10)
    12: 50,                             # twinkle: refresh rate, length-independent
    13: 60,                             # fire: flicker rate, length-independent
    14: 20,                             # breathing: sine period, length-independent
    15: max(1, 1764 // (NUM_LEDS - 1)), # bounce: one-way sweep ~1764 ms (147 * 12)
}

last_pattern = None

while True:
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
            solid_color((0, 0, 0)); print("Off")
        elif current_pattern == 1:
            solid_color((255, 0, 0)); print("Red")
        elif current_pattern == 2:
            solid_color((0, 255, 0)); print("Green")
        elif current_pattern == 3:
            solid_color((0, 0, 255)); print("Blue")
        elif current_pattern == 4:
            solid_color((255, 170, 90)); print("Warm White (RGB approx)")
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