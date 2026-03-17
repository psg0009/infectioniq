"""
Generate Demo Video for InfectionIQ
====================================
Creates an animated top-down view of an OR entrance showing:
  - 5 people who sanitize before entering (COMPLIANT)
  - 3 people who skip sanitizer (NON-COMPLIANT)

Usage: python cv_module/scripts/generate_demo_video.py
Output: demo_or_entry.mp4
"""

import cv2
import numpy as np
import math
import os

# ── Video settings ────────────────────────────────────────────────
WIDTH, HEIGHT = 1280, 720
FPS = 30
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "demo_or_entry.mp4")

# ── Colors (BGR) ──────────────────────────────────────────────────
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GRAY = (60, 60, 60)
LIGHT_GRAY = (200, 200, 200)
MED_GRAY = (140, 140, 140)
BG_COLOR = (245, 242, 235)  # warm off-white

# Zone colors
HALLWAY_COLOR = (230, 225, 215)
SANITIZER_ZONE_COLOR = (200, 230, 200)  # light green
OR_ZONE_COLOR = (200, 215, 240)  # light blue
DOOR_ZONE_COLOR = (220, 210, 230)  # light purple

# Person colors
NEUTRAL_COLOR = (180, 140, 80)   # tan/neutral
CLEAN_COLOR = (80, 180, 80)      # green = sanitized
DIRTY_COLOR = (60, 60, 220)      # red = non-compliant
SANITIZING_COLOR = (0, 220, 220) # yellow = actively sanitizing

# UI colors
ACCENT_BLUE = (200, 140, 40)
ACCENT_GREEN = (60, 170, 60)
ACCENT_RED = (50, 50, 210)
PANEL_BG = (40, 40, 50)

# ── Layout positions ─────────────────────────────────────────────
# Hallway on left, sanitizer station in middle, OR door on right
HALLWAY_X = 100
SANITIZER_X = 500
DOOR_X = 800
OR_X = 1000

LANE_Y = 360  # center of walking lane

# Sanitizer dispenser
SANITIZER_BOX = (480, 240, 540, 300)

# OR Door
DOOR_TOP = (790, 200)
DOOR_BOTTOM = (790, 520)

# ── Person definition ────────────────────────────────────────────
PERSON_RADIUS = 22

PEOPLE = [
    {"name": "Dr. Chen",       "compliant": True,  "delay_frames": 0},
    {"name": "Dr. Patel",      "compliant": True,  "delay_frames": 120},
    {"name": "RN Gonzalez",    "compliant": True,  "delay_frames": 240},
    {"name": "RN Kim",         "compliant": True,  "delay_frames": 360},
    {"name": "CST Thompson",   "compliant": True,  "delay_frames": 480},
    {"name": "R. Jackson",     "compliant": False, "delay_frames": 600},
    {"name": "Dr. Liu",        "compliant": False, "delay_frames": 720},
    {"name": "RN Rivera",      "compliant": False, "delay_frames": 840},
]

# Speeds
WALK_SPEED = 3.0        # pixels per frame
SANITIZE_FRAMES = 60    # 2 seconds sanitizing


def ease_in_out(t):
    """Smooth easing function."""
    return t * t * (3 - 2 * t)


def draw_rounded_rect(img, pt1, pt2, color, radius=10, thickness=-1):
    """Draw a rounded rectangle."""
    x1, y1 = pt1
    x2, y2 = pt2
    cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, thickness)
    cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, thickness)
    cv2.circle(img, (x1 + radius, y1 + radius), radius, color, thickness)
    cv2.circle(img, (x2 - radius, y1 + radius), radius, color, thickness)
    cv2.circle(img, (x1 + radius, y2 - radius), radius, color, thickness)
    cv2.circle(img, (x2 - radius, y2 - radius), radius, color, thickness)


def draw_background(frame):
    """Draw the static OR entrance layout."""
    frame[:] = BG_COLOR

    # Hallway area
    cv2.rectangle(frame, (50, 150), (460, 570), HALLWAY_COLOR, -1)
    cv2.rectangle(frame, (50, 150), (460, 570), MED_GRAY, 2)
    cv2.putText(frame, "HALLWAY", (200, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.6, MED_GRAY, 2)

    # Sanitizer zone
    cv2.rectangle(frame, (460, 150), (650, 570), SANITIZER_ZONE_COLOR, -1)
    cv2.rectangle(frame, (460, 150), (650, 570), (120, 180, 120), 2)
    cv2.putText(frame, "SANITIZER", (490, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 140, 80), 2)
    cv2.putText(frame, "ZONE", (515, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 140, 80), 2)

    # Sanitizer dispenser (wall-mounted box)
    sx1, sy1, sx2, sy2 = SANITIZER_BOX
    draw_rounded_rect(frame, (sx1, sy1), (sx2, sy2), (180, 180, 180), radius=5, thickness=-1)
    draw_rounded_rect(frame, (sx1, sy1), (sx2, sy2), (100, 100, 100), radius=5, thickness=2)
    cv2.putText(frame, "DISP", (sx1 + 5, sy1 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.4, DARK_GRAY, 1)
    # Drip indicator
    cv2.rectangle(frame, (sx1 + 15, sy2), (sx2 - 15, sy2 + 8), (160, 200, 160), -1)

    # Door zone
    cv2.rectangle(frame, (650, 150), (830, 570), DOOR_ZONE_COLOR, -1)
    cv2.rectangle(frame, (650, 150), (830, 570), (160, 150, 180), 2)
    cv2.putText(frame, "DOOR", (710, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 110, 140), 2)

    # Door frame
    cv2.line(frame, DOOR_TOP, DOOR_BOTTOM, DARK_GRAY, 4)
    # Door handle
    cv2.circle(frame, (795, 360), 6, DARK_GRAY, -1)

    # OR interior
    cv2.rectangle(frame, (830, 150), (1230, 570), OR_ZONE_COLOR, -1)
    cv2.rectangle(frame, (830, 150), (1230, 570), (140, 160, 190), 2)
    cv2.putText(frame, "OPERATING ROOM (OR-1)", (870, 185),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 120, 150), 2)

    # OR table (simplified)
    cv2.rectangle(frame, (920, 320), (1140, 420), (170, 185, 210), -1)
    cv2.rectangle(frame, (920, 320), (1140, 420), (130, 145, 170), 2)
    cv2.putText(frame, "Surgical Table", (960, 378),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 115, 140), 1)

    # Walking path arrows
    for x in range(150, 750, 80):
        cv2.arrowedLine(frame, (x, LANE_Y + 80), (x + 40, LANE_Y + 80),
                        (200, 195, 185), 1, tipLength=0.4)

    # Floor markings at sanitizer
    cv2.line(frame, (510, 310), (510, 410), (140, 190, 140), 2, cv2.LINE_AA)
    cv2.putText(frame, "STOP", (495, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (140, 190, 140), 1)


def draw_person(frame, x, y, color, name, state_text="", show_hands=False):
    """Draw a person as a circle with label."""
    # Body circle
    cv2.circle(frame, (int(x), int(y)), PERSON_RADIUS, color, -1)
    cv2.circle(frame, (int(x), int(y)), PERSON_RADIUS, DARK_GRAY, 2)

    # Head (smaller circle on top)
    head_y = int(y) - PERSON_RADIUS - 8
    cv2.circle(frame, (int(x), head_y), 10, color, -1)
    cv2.circle(frame, (int(x), head_y), 10, DARK_GRAY, 2)

    # Arms when sanitizing
    if show_hands:
        cv2.circle(frame, (int(x) - 18, int(y) - 5), 6, SANITIZING_COLOR, -1)
        cv2.circle(frame, (int(x) + 18, int(y) - 5), 6, SANITIZING_COLOR, -1)
        cv2.line(frame, (int(x) - 18, int(y) - 5), (int(x) + 18, int(y) - 5),
                 SANITIZING_COLOR, 2)

    # Name label
    text_size = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
    tx = int(x) - text_size[0] // 2
    ty = int(y) + PERSON_RADIUS + 20
    cv2.putText(frame, name, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.4, DARK_GRAY, 1)

    # State label
    if state_text:
        st_size = cv2.getTextSize(state_text, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)[0]
        stx = int(x) - st_size[0] // 2
        sty = ty + 16
        bg_color = ACCENT_GREEN if "CLEAN" in state_text else ACCENT_RED if "VIOLATION" in state_text else ACCENT_BLUE
        cv2.rectangle(frame, (stx - 3, sty - 12), (stx + st_size[0] + 3, sty + 3), bg_color, -1)
        cv2.putText(frame, state_text, (stx, sty), cv2.FONT_HERSHEY_SIMPLEX, 0.35, WHITE, 1)


def draw_status_panel(frame, frame_num, total_frames, compliant_count, violation_count, current_person_name):
    """Draw the status panel at the top."""
    # Top banner
    cv2.rectangle(frame, (0, 0), (WIDTH, 60), PANEL_BG, -1)

    # Title
    cv2.putText(frame, "InfectionIQ", (20, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 2)
    cv2.putText(frame, "Hand Hygiene Compliance Monitor", (20, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, LIGHT_GRAY, 1)

    # Stats
    total = compliant_count + violation_count
    rate = (compliant_count / total * 100) if total > 0 else 0

    stats_x = 450
    cv2.putText(frame, f"Entries: {total}/8", (stats_x, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, LIGHT_GRAY, 1)
    cv2.putText(frame, f"Compliant: {compliant_count}", (stats_x, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, ACCENT_GREEN, 1)
    cv2.putText(frame, f"Violations: {violation_count}", (stats_x + 180, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, ACCENT_RED, 1)

    # Compliance rate
    rate_text = f"Compliance: {rate:.0f}%"
    rate_color = ACCENT_GREEN if rate >= 80 else (0, 180, 220) if rate >= 60 else ACCENT_RED
    cv2.putText(frame, rate_text, (stats_x + 380, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, rate_color, 2)

    # Progress bar
    progress = frame_num / total_frames
    bar_x, bar_y, bar_w = 20, 68, WIDTH - 40
    cv2.rectangle(frame, (0, 60), (WIDTH, 80), (50, 50, 60), -1)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(bar_w * progress), bar_y + 6),
                  ACCENT_BLUE, -1)

    # Current action
    if current_person_name:
        cv2.rectangle(frame, (0, 80), (WIDTH, 110), (50, 50, 55), -1)
        cv2.putText(frame, f"NOW: {current_person_name}", (20, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 220), 1)


def draw_bottom_legend(frame):
    """Draw legend at the bottom."""
    y = HEIGHT - 40
    cv2.rectangle(frame, (0, HEIGHT - 55), (WIDTH, HEIGHT), PANEL_BG, -1)

    items = [
        (NEUTRAL_COLOR, "Approaching"),
        (SANITIZING_COLOR, "Sanitizing"),
        (CLEAN_COLOR, "Clean (Compliant)"),
        (DIRTY_COLOR, "Non-Compliant"),
    ]
    x = 30
    for color, label in items:
        cv2.circle(frame, (x, y), 8, color, -1)
        cv2.circle(frame, (x, y), 8, DARK_GRAY, 1)
        cv2.putText(frame, label, (x + 14, y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, LIGHT_GRAY, 1)
        x += 30 + cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0][0] + 20


def draw_alert_popup(frame, text, frame_in_alert):
    """Draw an alert popup that fades in."""
    alpha = min(1.0, frame_in_alert / 15.0)
    overlay = frame.copy()

    # Alert box
    box_w, box_h = 500, 60
    bx = WIDTH // 2 - box_w // 2
    by = HEIGHT - 130
    cv2.rectangle(overlay, (bx, by), (bx + box_w, by + box_h), (30, 30, 180), -1)
    cv2.rectangle(overlay, (bx, by), (bx + box_w, by + box_h), (50, 50, 220), 2)

    # Alert icon
    cv2.putText(overlay, "!", (bx + 15, by + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, WHITE, 3)
    cv2.putText(overlay, text, (bx + 45, by + 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1)

    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def generate_video():
    """Generate the demo video."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, FPS, (WIDTH, HEIGHT))

    if not out.isOpened():
        print(f"ERROR: Could not create video writer at {OUTPUT_PATH}")
        return

    # Calculate total frames needed
    # Each person: walk to sanitizer (~100f) + sanitize (60f) + walk to OR (~100f) + pause (30f)
    # Or for non-compliant: walk straight through (~200f) + pause (30f)
    last_person_delay = PEOPLE[-1]["delay_frames"]
    frames_per_person = 300  # generous per-person animation
    total_frames = last_person_delay + frames_per_person + 120  # extra for outro

    # Intro frames
    intro_frames = 90  # 3 seconds

    # Person animation state
    person_states = []
    for p in PEOPLE:
        person_states.append({
            "name": p["name"],
            "compliant": p["compliant"],
            "start_frame": intro_frames + p["delay_frames"],
            "x": HALLWAY_X,
            "y": LANE_Y + (20 if p["compliant"] else -20),  # slight Y offset
            "phase": "waiting",  # waiting, walking_to_sanitizer, sanitizing, walking_to_or, inside_or, walking_through
            "phase_frame": 0,
            "color": NEUTRAL_COLOR,
            "state_text": "",
            "show_hands": False,
            "done": False,
        })

    compliant_count = 0
    violation_count = 0
    current_action = ""
    alert_text = ""
    alert_frame = 0

    total_frames = intro_frames + last_person_delay + frames_per_person + 150

    print(f"Generating demo video: {total_frames} frames ({total_frames / FPS:.1f}s) at {FPS} FPS")
    print(f"Output: {OUTPUT_PATH}")

    for f in range(total_frames):
        frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

        # Draw background
        draw_background(frame)

        # Intro overlay
        if f < intro_frames:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (WIDTH, HEIGHT), (30, 30, 40), -1)
            alpha = max(0, 1.0 - f / intro_frames)
            cv2.addWeighted(overlay, alpha * 0.7, frame, 1 - alpha * 0.7, 0, frame)

            if f < intro_frames - 10:
                cv2.putText(frame, "InfectionIQ Demo", (WIDTH // 2 - 200, HEIGHT // 2 - 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, WHITE, 3)
                cv2.putText(frame, "OR-1 Hand Hygiene Monitoring", (WIDTH // 2 - 220, HEIGHT // 2 + 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, LIGHT_GRAY, 2)
                cv2.putText(frame, "8 Staff Members | 5 Compliant | 3 Non-Compliant",
                            (WIDTH // 2 - 260, HEIGHT // 2 + 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 1)

        # Update person states
        current_action = ""
        for ps in person_states:
            if f < ps["start_frame"] or ps["done"]:
                continue

            elapsed = f - ps["start_frame"]

            if ps["phase"] == "waiting":
                ps["phase"] = "walking_to_sanitizer" if ps["compliant"] else "walking_through"
                ps["phase_frame"] = 0
                ps["color"] = NEUTRAL_COLOR

            if ps["compliant"]:
                if ps["phase"] == "walking_to_sanitizer":
                    # Walk from hallway to sanitizer
                    target_x = SANITIZER_X
                    ps["x"] += WALK_SPEED
                    ps["state_text"] = ""
                    current_action = f"{ps['name']} approaching sanitizer..."
                    if ps["x"] >= target_x:
                        ps["x"] = target_x
                        ps["phase"] = "sanitizing"
                        ps["phase_frame"] = 0
                        ps["show_hands"] = True
                        ps["color"] = SANITIZING_COLOR

                elif ps["phase"] == "sanitizing":
                    ps["phase_frame"] += 1
                    ps["state_text"] = "SANITIZING..."
                    current_action = f"{ps['name']} sanitizing hands..."
                    # Bobbing animation
                    ps["y"] = LANE_Y + 20 + int(3 * math.sin(ps["phase_frame"] * 0.3))
                    if ps["phase_frame"] >= SANITIZE_FRAMES:
                        ps["phase"] = "walking_to_or"
                        ps["phase_frame"] = 0
                        ps["color"] = CLEAN_COLOR
                        ps["state_text"] = "CLEAN"
                        ps["show_hands"] = False
                        compliant_count += 1

                elif ps["phase"] == "walking_to_or":
                    ps["x"] += WALK_SPEED
                    ps["state_text"] = "CLEAN"
                    current_action = f"{ps['name']} entering OR (COMPLIANT)"
                    if ps["x"] >= OR_X:
                        ps["phase"] = "inside_or"
                        ps["phase_frame"] = 0
                        ps["x"] = OR_X + 30

                elif ps["phase"] == "inside_or":
                    ps["phase_frame"] += 1
                    ps["state_text"] = "CLEAN"
                    if ps["phase_frame"] > 60:
                        ps["done"] = True

            else:
                # Non-compliant: walk straight through
                if ps["phase"] == "walking_through":
                    ps["x"] += WALK_SPEED * 1.3  # walks faster, skipping sanitizer
                    ps["color"] = NEUTRAL_COLOR
                    current_action = f"{ps['name']} bypassing sanitizer..."

                    # Passing sanitizer zone - turn red
                    if ps["x"] >= SANITIZER_X - 30:
                        ps["color"] = DIRTY_COLOR
                        ps["state_text"] = "VIOLATION"

                    if ps["x"] >= DOOR_X:
                        violation_count += 1
                        alert_text = f"ALERT: {ps['name']} entered OR without hand hygiene!"
                        alert_frame = 0
                        ps["phase"] = "inside_or_dirty"
                        ps["phase_frame"] = 0
                        current_action = f"ALERT: {ps['name']} entered WITHOUT sanitizing!"

                elif ps["phase"] == "inside_or_dirty":
                    ps["x"] += WALK_SPEED * 0.5
                    ps["phase_frame"] += 1
                    ps["state_text"] = "VIOLATION"
                    if ps["phase_frame"] > 90:
                        ps["done"] = True

        # Draw all active persons (back to front for overlap)
        active_persons = [ps for ps in person_states if not (f < ps["start_frame"] or ps["done"])]
        for ps in sorted(active_persons, key=lambda p: p["y"]):
            draw_person(frame, ps["x"], ps["y"], ps["color"], ps["name"],
                       ps["state_text"], ps["show_hands"])

        # Draw alert popup
        if alert_text:
            alert_frame += 1
            if alert_frame < 90:  # Show for 3 seconds
                draw_alert_popup(frame, alert_text, alert_frame)
            else:
                alert_text = ""

        # Draw status panel (on top)
        draw_status_panel(frame, f, total_frames, compliant_count, violation_count, current_action)

        # Draw legend
        draw_bottom_legend(frame)

        # Outro
        if f > total_frames - 90:
            overlay = frame.copy()
            alpha = (f - (total_frames - 90)) / 90.0
            cv2.rectangle(overlay, (0, 0), (WIDTH, HEIGHT), (30, 30, 40), -1)
            cv2.addWeighted(overlay, alpha * 0.8, frame, 1 - alpha * 0.8, 0, frame)

            if alpha > 0.3:
                total = compliant_count + violation_count
                rate = (compliant_count / total * 100) if total > 0 else 0
                cv2.putText(frame, "Demo Complete", (WIDTH // 2 - 160, HEIGHT // 2 - 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, WHITE, 3)
                cv2.putText(frame, f"Compliance Rate: {rate:.0f}%", (WIDTH // 2 - 170, HEIGHT // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 200), 2)
                cv2.putText(frame, f"{compliant_count} Compliant | {violation_count} Violations",
                            (WIDTH // 2 - 180, HEIGHT // 2 + 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, LIGHT_GRAY, 1)
                cv2.putText(frame, "Events synced to InfectionIQ Dashboard",
                            (WIDTH // 2 - 230, HEIGHT // 2 + 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 200, 100), 1)

        out.write(frame)

        if (f + 1) % (FPS * 5) == 0:
            print(f"  {f + 1}/{total_frames} frames ({(f + 1) / FPS:.0f}s)")

    out.release()
    file_size = os.path.getsize(OUTPUT_PATH) / 1024 / 1024
    print(f"\nVideo saved: {OUTPUT_PATH} ({file_size:.1f} MB)")
    print(f"Duration: {total_frames / FPS:.1f} seconds")


if __name__ == "__main__":
    generate_video()
