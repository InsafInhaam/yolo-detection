import cv2
import json
import time
import numpy as np
from ultralytics import YOLO

# =========================
# CONFIG
# =========================

CAMERA_INDEX = 0
MODEL_PATH = "yolov8s.pt"
LANE_FILE = "lanes.json"

VEHICLE_CLASSES = ["car", "truck", "bus"]

GREEN_TIME = 5
YELLOW_TIME = 2
EMPTY_TIMEOUT = 1.5  # seconds before lane is considered empty

# =========================
# LOAD LANES
# =========================

with open(LANE_FILE, "r") as f:
    raw_lanes = json.load(f)

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


def update_traffic_lights():
    global light_state, current_lane_index, last_switch_time

    elapsed = time.time() - last_switch_time

    if light_state == "GREEN" and elapsed >= GREEN_TIME:
        light_state = "YELLOW"
        last_switch_time = time.time()

    elif light_state == "YELLOW" and elapsed >= YELLOW_TIME:
        light_state = "GREEN"
        current_lane_index = (current_lane_index + 1) % len(lane_order)
        last_switch_time = time.time()

    active_lane = lane_order[current_lane_index]

    for lane in lanes:
        if lane == active_lane:
            lanes[lane]["signal"] = light_state
        else:
            lanes[lane]["signal"] = "RED"


# =========================
# MAIN LOOP
# =========================

while True:
    ret, frame = cap.read()
    if not ret:
        break

    now = time.time()
    update_traffic_lights()

    # Reset occupancy if timeout passed
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

        lane = point_in_lane(cx, cy)
        if lane:
            lanes[lane]["occupied"] = True
            lanes[lane]["last_seen"] = now

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

    # DRAW LANES
    for lane, data in lanes.items():
        color = (0, 255, 0) if data["signal"] == "GREEN" else \
                (0, 255, 255) if data["signal"] == "YELLOW" else \
                (0, 0, 255)

        cv2.polylines(frame, [data["polygon"]], True, color, 2)
        cv2.putText(
            frame,
            f"{lane} | {data['signal']} | {'OCC' if data['occupied'] else 'EMPTY'}",
            tuple(data["polygon"][0]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

    # TERMINAL OUTPUT
    print("\n==============================")
    for lane, data in lanes.items():
        print(f"{lane}: {data['signal']} | {'OCCUPIED' if data['occupied'] else 'EMPTY'}")

    cv2.imshow("Intersection", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
