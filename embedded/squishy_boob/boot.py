import machine
from machine import Pin
import esp32
import espnow
import network
import time
import math
import random
from neopixel import NeoPixel

# ── Config ─────────────────────────────────────────────
LED_PIN       = 15
NUM_LEDS      = 25
WAKE_MODE_PIN = 4
BRIGHTNESS    = 0.2
MODE_FILE     = "mode.txt"
HOLD_MS       = 800
DEBOUNCE_MS   = 50

# ── WiFi + ESP-NOW setup ───────────────────────────────
sta = network.WLAN(network.STA_IF)
sta.active(True)
e = espnow.ESPNow()
e.active(True)

# ── LED setup ──────────────────────────────────────────
np = NeoPixel(Pin(LED_PIN, Pin.OUT), NUM_LEDS)  # RGB bpp=3

# ── Animation state ────────────────────────────────────
current_pattern = 0
last_pattern    = None
frame           = 0
comet_pos       = 0
comet_dir       = 1
wipe_pos        = 0
wipe_color_idx  = 0

ANIMATED = (8, 9, 10, 11, 12, 13, 14, 15)
DELAYS   = {8: 20, 9: 15, 10: 60, 11: 10, 12: 50, 13: 60, 14: 20, 15: 12}
WIPE_COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
NUM_PATTERNS = 16

# ── Mode persistence ───────────────────────────────────
def load_mode():
    try:
        with open(MODE_FILE, "r") as f:
            return int(f.read())
    except:
        return 0

def save_mode(m):
    with open(MODE_FILE, "w") as f:
        f.write(str(m))

# ── LED helpers ────────────────────────────────────────
def scale(c):
    return tuple(int(x * BRIGHTNESS) for x in c)

def fill(c):
    for i in range(NUM_LEDS):
        np[i] = c
    np.write()

def clear():
    fill((0, 0, 0))

def decay(factor_num=7, factor_den=10):
    for i in range(NUM_LEDS):
        r, g, b = np[i]
        np[i] = (r * factor_num // factor_den,
                 g * factor_num // factor_den,
                 b * factor_num // factor_den)

def wheel(pos):
    pos &= 255
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    pos -= 170
    return (0, pos * 3, 255 - pos * 3)

# ── Static patterns ────────────────────────────────────
def static_off():
    fill((0, 0, 0))

def static_red():
    fill(scale((255, 0, 0)))

def static_green():
    fill(scale((0, 255, 0)))

def static_blue():
    fill(scale((0, 0, 255)))

def static_warm_white():
    fill(scale((255, 200, 60)))   # warm white approximation in RGB

def static_gradient():
    for i in range(NUM_LEDS):
        t = i / (NUM_LEDS - 1)
        r = int(255 * (1 - t))
        g = int(255 * t)
        b = 255
        np[i] = scale((r, g, b))
    np.write()

def static_rainbow():
    for i in range(NUM_LEDS):
        np[i] = scale(wheel((i * 256 // NUM_LEDS) & 255))
    np.write()

def static_bands():
    third = NUM_LEDS // 3
    for i in range(NUM_LEDS):
        if i < third:
            np[i] = scale((255, 0, 0))
        elif i < third * 2:
            np[i] = scale((0, 255, 0))
        else:
            np[i] = scale((0, 0, 255))
    np.write()

# ── Animated patterns (one step per call) ──────────────
def anim_rainbow_cycle():
    for i in range(NUM_LEDS):
        np[i] = scale(wheel(((i * 256 // NUM_LEDS) + frame) & 255))
    np.write()

def anim_comet():
    global comet_pos
    decay(6, 10)
    np[comet_pos] = scale(wheel((frame * 2) & 255))
    comet_pos = (comet_pos + 1) % NUM_LEDS
    np.write()

def anim_theater_chase():
    color = wheel((frame * 3) & 255)
    for i in range(NUM_LEDS):
        np[i] = scale(color) if (i + frame) % 3 == 0 else (0, 0, 0)
    np.write()

def anim_color_wipe():
    global wipe_pos, wipe_color_idx
    np[wipe_pos] = scale(WIPE_COLORS[wipe_color_idx])
    wipe_pos += 1
    if wipe_pos >= NUM_LEDS:
        wipe_pos = 0
        wipe_color_idx = (wipe_color_idx + 1) % len(WIPE_COLORS)
    np.write()

def anim_twinkle():
    decay(8, 10)
    for _ in range(3):
        i = random.randint(0, NUM_LEDS - 1)
        np[i] = scale((255, 255, 255))
    np.write()

def anim_fire():
    for i in range(NUM_LEDS):
        flicker = random.randint(100, 255)
        np[i] = scale((flicker, flicker * 50 // 255, 0))
    np.write()

def anim_breathing():
    factor = (math.sin(frame / 18.0) + 1) / 2
    color = wheel((frame // 2) & 255)
    np.fill(tuple(int(c * BRIGHTNESS * factor) for c in color))
    np.write()

def anim_bounce():
    global comet_pos, comet_dir
    decay(5, 10)
    np[comet_pos] = scale((0, 150, 255))
    comet_pos += comet_dir
    if comet_pos >= NUM_LEDS - 1 or comet_pos <= 0:
        comet_dir *= -1
    np.write()

# ── Pattern dispatcher ─────────────────────────────────
def apply_static(pattern):
    if   pattern == 0:  static_off();       print("Off")
    elif pattern == 1:  static_red();       print("Red")
    elif pattern == 2:  static_green();     print("Green")
    elif pattern == 3:  static_blue();      print("Blue")
    elif pattern == 4:  static_warm_white();print("Warm White")
    elif pattern == 5:  static_gradient();  print("Gradient")
    elif pattern == 6:  static_rainbow();   print("Static Rainbow")
    elif pattern == 7:  static_bands();     print("RGB Bands")

def apply_animated(pattern):
    if   pattern == 8:  anim_rainbow_cycle()
    elif pattern == 9:  anim_comet()
    elif pattern == 10: anim_theater_chase()
    elif pattern == 11: anim_color_wipe()
    elif pattern == 12: anim_twinkle()
    elif pattern == 13: anim_fire()
    elif pattern == 14: anim_breathing()
    elif pattern == 15: anim_bounce()

def reset_anim_state():
    global frame, comet_pos, comet_dir, wipe_pos, wipe_color_idx
    frame = 0; comet_pos = 0; comet_dir = 1; wipe_pos = 0; wipe_color_idx = 0

def set_pattern(p):
    """Switch to a pattern, resetting animation state and forcing redraw."""
    global current_pattern, last_pattern
    current_pattern = p
    last_pattern    = None
    reset_anim_state()
    save_mode(p)

# ── Button ─────────────────────────────────────────────
btn = Pin(WAKE_MODE_PIN, Pin.IN, Pin.PULL_UP)

def measure_hold_ms():
    if btn.value() == 1:
        deadline = time.ticks_add(time.ticks_ms(), 300)
        while btn.value() == 1:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return 0
            time.sleep_ms(10)
    time.sleep_ms(DEBOUNCE_MS)
    if btn.value() == 1:
        return 0
    t_down = time.ticks_ms()
    while btn.value() == 0:
        time.sleep_ms(10)
    return time.ticks_diff(time.ticks_ms(), t_down)

def go_to_sleep():
    print("Going to sleep...")
    clear()
    esp32.wake_on_ext1(pins=(btn,), level=esp32.WAKEUP_ALL_LOW)
    time.sleep_ms(100)
    machine.deepsleep()

# ── Boot ───────────────────────────────────────────────
woke_from_sleep = machine.reset_cause() == machine.DEEPSLEEP_RESET
current_pattern = load_mode()

if not woke_from_sleep:
    held = measure_hold_ms()
    if held >= HOLD_MS:
        go_to_sleep()
    elif held >= DEBOUNCE_MS:
        current_pattern = (current_pattern + 1) % NUM_PATTERNS
        save_mode(current_pattern)
        print("Mode changed to:", current_pattern)

print("Running pattern:", current_pattern)

# ── Main loop ──────────────────────────────────────────
while True:
    # ── ESP-NOW receive ────────────────────────────────
    host, message = e.recv(0)
    if message:
        p = int.from_bytes(message, "big")
        print("Received pattern:", p)
        set_pattern(p)

    # ── Button check ───────────────────────────────────
    if btn.value() == 0:
        held = measure_hold_ms()
        if held >= HOLD_MS:
            go_to_sleep()
        elif held >= DEBOUNCE_MS:
            current_pattern = (current_pattern + 1) % NUM_PATTERNS
            set_pattern(current_pattern)
            print("Button → pattern:", current_pattern)

    # ── Draw ───────────────────────────────────────────
    if current_pattern not in ANIMATED:
        if current_pattern != last_pattern:
            apply_static(current_pattern)
            last_pattern = current_pattern
        time.sleep_ms(1)
    else:
        apply_animated(current_pattern)
        frame += 1
        time.sleep_ms(DELAYS[current_pattern])

