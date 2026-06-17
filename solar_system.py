#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║   REAL-TIME 3D SOLAR SYSTEM — Terminal Simulation    ║
║   Press Q to quit, +/- to speed up/slow down        ║
╚══════════════════════════════════════════════════════╝

Kepler orbital mechanics + perspective projection + ANSI color
"""

import math
import time
import sys
import os
import select
import termios
import tty

# ─── ANSI colors ───────────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD  = "\033[1m"

def rgb(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"

def bg(r, g, b):
    return f"\033[48;2;{r};{g};{b}m"

SUN_COLOR      = rgb(255, 220,  50)
STAR_COLORS    = [rgb(200,200,255), rgb(255,255,200), rgb(255,200,200), rgb(150,200,255)]

# ─── Planets: (name, color, orbital_radius, period_years, size, eccentricity, inclination_deg) ──
PLANETS = [
    ("Mercury", rgb(180, 140, 120), 0.39,   0.24, 1, 0.206, 7.0),
    ("Venus",   rgb(230, 200, 100), 0.72,   0.62, 2, 0.007, 3.4),
    ("Earth",   rgb( 80, 160, 255), 1.00,   1.00, 2, 0.017, 0.0),
    ("Mars",    rgb(220,  80,  50), 1.52,   1.88, 2, 0.093, 1.8),
    ("Jupiter", rgb(230, 180, 130), 2.60,  11.86, 4, 0.049, 1.3),
    ("Saturn",  rgb(220, 200, 150), 3.20,  29.46, 4, 0.057, 2.5),
    ("Uranus",  rgb(100, 210, 220), 3.80,  84.01, 3, 0.046, 0.8),
    ("Neptune", rgb( 60, 100, 240), 4.30, 164.80, 3, 0.010, 1.8),
]

# ─── Moon ─────────────────────────────────────────────────────────────────────
MOON = ("Moon", rgb(200, 200, 200), 0.12, 0.075)  # name, color, orbit_r, period_years

# ─── Asteroid belt ────────────────────────────────────────────────────────────
import random
random.seed(42)
ASTEROIDS = [(random.uniform(2.0, 2.5), random.uniform(0, 2*math.pi)) for _ in range(60)]

# ─── Stars background ─────────────────────────────────────────────────────────
random.seed(99)
STARS = [(random.randint(0, 300), random.randint(0, 80), random.choice(['·', '✦', '·', '·', '*'])) for _ in range(200)]

# ─── Perspective projection ───────────────────────────────────────────────────
FOCAL = 5.0   # camera focal length
CAM_Z = 8.0   # camera distance

def project(x, y, z, tilt=0.45):
    """Rotate around X axis (tilt), then perspective project."""
    # Tilt
    y2 = y * math.cos(tilt) - z * math.sin(tilt)
    z2 = y * math.sin(tilt) + z * math.cos(tilt)
    # Perspective
    dz = CAM_Z - z2
    if dz < 0.1:
        dz = 0.1
    sx = x * FOCAL / dz
    sy = y2 * FOCAL / dz
    return sx, sy

# ─── Planet position in 3D (Kepler ellipse) ───────────────────────────────────
def planet_pos(radius, period, ecc, incl_deg, t):
    """Returns (x, y, z) in AU."""
    angle = (2 * math.pi / period) * t
    incl = math.radians(incl_deg)
    # Ellipse (simplified: just scale x)
    r = radius * (1 - ecc * math.cos(angle))
    x = r * math.cos(angle)
    y = r * math.sin(angle) * math.cos(incl)
    z = r * math.sin(angle) * math.sin(incl)
    return x, y, z

# ─── Drawing buffer ───────────────────────────────────────────────────────────
def make_buffer(W, H):
    return [[(' ', RESET)] * W for _ in range(H)]

def draw_char(buf, W, H, sx, sy, ch, color, cx, cy, scale):
    px = int(cx + sx * scale)
    py = int(cy - sy * scale * 0.5)  # y squish for terminal aspect ratio
    if 0 <= px < W and 0 <= py < H:
        buf[py][px] = (ch, color)

def render_buffer(buf):
    lines = []
    for row in buf:
        line = ""
        for ch, col in row:
            line += col + ch
        line += RESET
        lines.append(line)
    return "\n".join(lines)

# ─── Non-blocking keyboard input ─────────────────────────────────────────────
def kbhit():
    return select.select([sys.stdin], [], [], 0)[0] != []

def getch():
    return sys.stdin.read(1)

# ─── Intro splash ─────────────────────────────────────────────────────────────
SPLASH = f"""
{rgb(255,220,50)}{BOLD}
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ☀  SOLAR SYSTEM — Real-time Terminal Simulation  ☀        ║
    ║                                                              ║
    ║   Kepler orbital mechanics + ANSI 24-bit color + 3D tilt    ║
    ║                                                              ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Q / Ctrl-C : quit          +/- : speed × 2 / ÷ 2          ║
    ║  T          : toggle trails  P : pause                      ║
    ╚══════════════════════════════════════════════════════════════╝
{RESET}
    Starting in 2 seconds…
"""

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(SPLASH)
    time.sleep(2)

    # terminal raw mode
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())

    try:
        W, H = os.get_terminal_size()
        H -= 2  # leave status bar

        cx, cy = W // 2, H // 2
        scale = min(W, H * 2) * 0.10   # AU → pixels

        t = 0.0
        dt = 0.02          # years per frame
        paused = False
        trails = True
        trail_buf = {}     # planet_name -> list of (sx,sy)
        TRAIL_LEN = 60

        frame = 0
        t0 = time.time()

        while True:
            # ── Input ──────────────────────────────────────────────────────
            if kbhit():
                ch = getch()
                if ch in ('q', 'Q', '\x03'):
                    break
                elif ch == '+':
                    dt = min(dt * 2, 1.0)
                elif ch == '-':
                    dt = max(dt / 2, 0.001)
                elif ch in ('p', 'P'):
                    paused = not paused
                elif ch in ('t', 'T'):
                    trails = not trails
                    trail_buf.clear()

            if not paused:
                t += dt

            # ── Build scene ────────────────────────────────────────────────
            buf = make_buffer(W, H)

            # Stars
            for sx, sy, ch in STARS:
                if 0 <= sx < W and 0 <= sy < H:
                    ci = (sx * 3 + sy * 7) % len(STAR_COLORS)
                    buf[sy][sx] = (ch, STAR_COLORS[ci])

            # Sun glow rings
            sun_glyphs = ['✦', '☀', '✦']
            for ring, (g, color_scale) in enumerate([(3, 0.6), (1, 0.8), (0, 1.0)]):
                r = 255
                g2 = int(150 + 70 * color_scale)
                b = int(20 * color_scale)
                c = rgb(r, g2, b)
                for gx in range(-ring, ring+1):
                    for gy in range(-ring//2, ring//2+1):
                        px = cx + gx
                        py = cy + gy
                        if 0 <= px < W and 0 <= py < H:
                            buf[py][px] = ('●' if ring == 0 else '○', c)

            # Orbit ellipses (dotted)
            for name, color, radius, period, size, ecc, incl_deg in PLANETS:
                incl = math.radians(incl_deg)
                for i in range(120):
                    angle = 2 * math.pi * i / 120
                    r = radius * (1 - ecc * math.cos(angle))
                    x = r * math.cos(angle)
                    y = r * math.sin(angle) * math.cos(incl)
                    z = r * math.sin(angle) * math.sin(incl)
                    sx, sy = project(x, y, z)
                    px = int(cx + sx * scale)
                    py = int(cy - sy * scale * 0.5)
                    if 0 <= px < W and 0 <= py < H:
                        if buf[py][px][0] == ' ':
                            buf[py][px] = ('·', rgb(40,40,70))

            # Asteroid belt
            for r_au, angle0 in ASTEROIDS:
                angle = angle0 + t * 0.5
                x = r_au * math.cos(angle)
                y = r_au * math.sin(angle) * 0.98
                z = r_au * math.sin(angle) * 0.02
                sx, sy = project(x, y, z)
                draw_char(buf, W, H, sx, sy, '·', rgb(120,100,80), cx, cy, scale)

            # Trails
            if trails:
                for name, color, _, trail in trail_buf.items():
                    for i, (tsx, tsy) in enumerate(trail):
                        fade = i / TRAIL_LEN
                        alpha = int(80 * fade)
                        draw_char(buf, W, H, tsx, tsy, '·', rgb(alpha,alpha,alpha), cx, cy, scale)

            # Planets + Moon
            for idx, (name, color, radius, period, size, ecc, incl_deg) in enumerate(PLANETS):
                x, y, z = planet_pos(radius, period, ecc, incl_deg, t)
                sx, sy = project(x, y, z)

                # Trail update
                if trails:
                    trail = trail_buf.setdefault(name, [])
                    trail.append((sx, sy))
                    if len(trail) > TRAIL_LEN:
                        trail.pop(0)

                # Planet glyph by size
                glyphs = {1: '·', 2: '●', 3: '◉', 4: '⬡'}
                glyph = glyphs.get(size, '●')

                draw_char(buf, W, H, sx, sy, glyph, BOLD + color, cx, cy, scale)

                # Label (every other frame for performance)
                if frame % 2 == 0:
                    lx = int(cx + sx * scale) + size + 1
                    ly = int(cy - sy * scale * 0.5)
                    if 0 <= lx < W - len(name) and 0 <= ly < H:
                        for i, c in enumerate(name[:8]):
                            if lx + i < W:
                                buf[ly][lx + i] = (c, color)

                # Moon (only for Earth)
                if name == "Earth":
                    mn, mc, mr, mp = MOON
                    ma = (2 * math.pi / mp) * t
                    mx = x + mr * math.cos(ma)
                    my = y + mr * math.sin(ma)
                    mz = z
                    msx, msy = project(mx, my, mz)
                    draw_char(buf, W, H, msx, msy, '○', mc, cx, cy, scale)

            # ── Status bar ─────────────────────────────────────────────────
            elapsed = time.time() - t0
            fps = frame / max(elapsed, 0.001)
            speed_label = f"{dt*365:.1f} days/frame"
            status = (
                f"{BOLD}{rgb(255,220,50)}  ☀ SOLAR SYSTEM  {RESET}"
                f"{rgb(150,200,255)}T={t:.2f}yr  {speed_label}  FPS={fps:.1f}  "
                f"{'[PAUSED]' if paused else ''}  "
                f"{'[TRAILS]' if trails else ''}  "
                f"[Q]uit [+/-]speed [P]ause [T]rails{RESET}"
            )

            # ── Render ─────────────────────────────────────────────────────
            rendered = render_buffer(buf)
            sys.stdout.write("\033[H")          # cursor home
            sys.stdout.write(rendered)
            sys.stdout.write("\n" + status)
            sys.stdout.flush()

            frame += 1
            time.sleep(0.03)  # ~33 fps cap

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write(f"{BOLD}{SUN_COLOR}  ☀  See you in another orbit.  {RESET}\n")
        sys.stdout.flush()

if __name__ == "__main__":
    # hide cursor
    sys.stdout.write("\033[?25l\033[2J")
    sys.stdout.flush()
    try:
        main()
    finally:
        sys.stdout.write("\033[?25h")  # show cursor
        sys.stdout.flush()
