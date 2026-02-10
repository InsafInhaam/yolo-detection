import cv2
import json
import time
import numpy as np
import requests
from ultralytics import YOLO

# =========================
# CONFIG
# =========================

CAMERA_INDEX = 0
MODEL_PATH = "yolov8l.pt"
LANE_FILE = "lanes.json"

ARDUINO_IP = "http://192.168.1.100"  # Update with your ESP8266 IP

VEHICLE_CLASSES = ["car", "truck", "bus"]

GREEN_TIME = 5
YELLOW_TIME = 2
EMPTY_TIMEOUT = 1.5

LANE_DIRECTIONS = {
    "lane_1": "UP",
    "lane_2": "DOWN",
    "lane_3": "RIGHT",
    "lane_4": "LEFT",
}

# Map Python lanes to Arduino lanes
LANE_TO_ARDUINO = {
    "lane_1": "north",   # UP
    "lane_2": "south",   # DOWN
    "lane_3": "east",    # RIGHT
    "lane_4": "west",    # LEFT
}

# =========================
# LOAD LANES
# =========================

try:
    with open(LANE_FILE, "r") as f:
        raw_lanes = json.load(f)

    if not raw_lanes:
        raise ValueError("Lanes file is empty")
except (json.JSONDecodeError, ValueError, FileNotFoundError) as e:
    print(f"❌ Error loading lanes: {e}")
    print("⚠️  Please run draw_and_detect.py first to define lanes")
    exit(1)

lanes = {}
for lane, points in raw_lanes.items():
    lanes[lane] = {
        "polygon": np.array(points, dtype=np.int32),
        "occupied": False,
        "last_seen": 0,
        "signal": "RED"
    }

lane_order = list(lanes.keys())
current_lane_index = 0
light_state = "GREEN"
last_switch_time = time.time()

# =========================
# INIT
# =========================

model = YOLO(MODEL_PATH)

cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    raise RuntimeError("❌ Webcam not detected")

# =========================
# HELPERS
# =========================


def point_in_lane(cx, cy):
    for lane, data in lanes.items():
        if cv2.pointPolygonTest(data["polygon"], (cx, cy), False) >= 0:
            return lane
    return None


def infer_direction(prev, curr, threshold=8):
    dx = curr[0] - prev[0]
    dy = curr[1] - prev[1]

    if abs(dx) < threshold and abs(dy) < threshold:
        return "STATIONARY"

    if abs(dx) > abs(dy):
        return "RIGHT" if dx > 0 else "LEFT"
    else:
        return "DOWN" if dy > 0 else "UP"


def send_to_arduino(lane, color):
    """Send traffic light command to Arduino"""
    try:
        arduino_lane = LANE_TO_ARDUINO.get(lane)
        if not arduino_lane:
            return

        url = f"{ARDUINO_IP}/control"
        params = {
            "lane": arduino_lane,
            "color": color.lower(),
            "state": 1
        }
        requests.get(url, params=params, timeout=0.5)
    except Exception as e:
        pass  # Silently continue if Arduino is unreachable


def update_traffic_lights():
    global light_state, current_lane_index, last_switch_time

    elapsed = time.time() - last_switch_time

    if light_state == "GREEN" and elapsed >= GREEN_TIME:
        light_state = "YELLOW"
        last_switch_time = time.time()
        # Send yellow signal to active lane
        active_lane = lane_order[current_lane_index]
        send_to_arduino(active_lane, "yellow")

    elif light_state == "YELLOW" and elapsed >= YELLOW_TIME:
        light_state = "GREEN"
        current_lane_index = (current_lane_index + 1) % len(lane_order)
        last_switch_time = time.time()
        # Send green to new active lane
        active_lane = lane_order[current_lane_index]
        send_to_arduino(active_lane, "green")

    active_lane = lane_order[current_lane_index]

    for lane in lanes:
        lanes[lane]["signal"] = light_state if lane == active_lane else "RED"


# =========================
# INIT ARDUINO CONNECTION
# =========================

print("✅ Webcam opened. Starting detection...")

# Set Arduino to MANUAL mode and initialize first green light
try:
    requests.get(f"{ARDUINO_IP}/mode?set=manual", timeout=1)
    print("✅ Arduino set to MANUAL mode")
    # Set first lane to green
    send_to_arduino(lane_order[0], "green")
    print(f"✅ Initial green signal sent to {lane_order[0]}")
except Exception as e:
    print(f"⚠️  Arduino connection failed: {e}")
    print("Continuing without Arduino control...")

cv2.namedWindow("Intersection")

# =========================
# VEHICLE MEMORY (lightweight tracking)
# =========================

vehicle_memory = {}
vehicle_id_counter = 0

# =========================
# MAIN LOOP
# =========================


# =========================
# MAIN LOOP
# =========================

while True:
    ret, frame = cap.read()
    if not ret:
        break

    now = time.time()
    update_traffic_lights()

    for lane in lanes:
        if now - lanes[lane]["last_seen"] > EMPTY_TIMEOUT:
            lanes[lane]["occupied"] = False

    results = model(frame, verbose=False)[0]

    for box in results.boxes:
        cls = model.names[int(box.cls[0])]
        if cls not in VEHICLE_CLASSES:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        centroid = (cx, cy)

        # Detect vehicles in lanes
        lane = point_in_lane(cx, cy)
        if not lane:
            continue

        # Draw detected vehicle
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

        # Simple tracking: assign or update vehicle ID
        vid = None
        for k, v in vehicle_memory.items():
            if np.linalg.norm(np.array(v["pos"]) - np.array(centroid)) < 50:
                vid = k
                break

        if vid is None:
            vid = vehicle_id_counter
            vehicle_id_counter += 1

        prev_pos = vehicle_memory.get(vid, {}).get("pos")

        # Mark lane as occupied (with or without direction check)
        lanes[lane]["occupied"] = True
        lanes[lane]["last_seen"] = now

        # If we have previous position, infer direction
        if prev_pos:
            direction = infer_direction(prev_pos, centroid)
            cv2.putText(
                frame,
                f"{lane} | {direction}",
                (x1, y1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        vehicle_memory[vid] = {"pos": centroid, "time": now}

    # DRAW LANES
    for lane, data in lanes.items():
        color = (0, 255, 0) if data["signal"] == "GREEN" else \
                (0, 255, 255) if data["signal"] == "YELLOW" else \
                (0, 0, 255)

        cv2.polylines(frame, [data["polygon"]], True, color, 2)
        cv2.putText(
            frame,
            f"{lane} {LANE_DIRECTIONS[lane]}",
            tuple(data["polygon"][0]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

    # TERMINAL OUTPUT
    print("\n==============================")
    for lane, data in lanes.items():
        print(
            f"{lane}: {data['signal']} | {'OCCUPIED' if data['occupied'] else 'EMPTY'}")

    cv2.imshow("Intersection", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Cleanup: Return Arduino to AUTO mode
try:
    requests.get(f"{ARDUINO_IP}/mode?set=auto", timeout=1)
    print("\n✅ Arduino set back to AUTO mode")
except:
    pass

cap.release()
cv2.destroyAllWindows()
