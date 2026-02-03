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
TOTAL_LANES = 4

# =========================
# GLOBALS
# =========================

current_lane_points = []
lanes = {}
lane_index = 1

drawing_mode = True

lane_cycle = []
current_lane_signal = 0
light_state = "GREEN"
last_switch_time = time.time()

# =========================
# MOUSE CALLBACK
# =========================


def mouse_callback(event, x, y, flags, param):
    global current_lane_points

    if event == cv2.EVENT_LBUTTONDOWN and drawing_mode:
        current_lane_points.append((x, y))
        print(f"Point added: ({x}, {y})")

# =========================
# TRAFFIC LOGIC
# =========================


def update_traffic_light():
    global light_state, current_lane_signal, last_switch_time

    elapsed = time.time() - last_switch_time

    if light_state == "GREEN" and elapsed >= GREEN_TIME:
        light_state = "YELLOW"
        last_switch_time = time.time()

    elif light_state == "YELLOW" and elapsed >= YELLOW_TIME:
        light_state = "GREEN"
        current_lane_signal = (current_lane_signal + 1) % len(lane_cycle)
        last_switch_time = time.time()

# =========================
# LANE CHECK
# =========================


def get_lane(cx, cy):
    for lane, points in lanes.items():
        polygon = np.array(points, dtype=np.int32)
        if cv2.pointPolygonTest(polygon, (cx, cy), False) >= 0:
            return lane
    return None

# =========================
# MAIN
# =========================


model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    raise RuntimeError("❌ Webcam not detected")

cv2.namedWindow("Intersection")
cv2.setMouseCallback("Intersection", mouse_callback)

print("\nINSTRUCTIONS:")
print("Left click  : Add lane point")
print("Press 'n'   : Finish current lane")
print("Press 's'   : Save lanes and start detection")
print("Press 'q'   : Quit\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # DRAW CURRENT POINTS
    if drawing_mode:
        for i in range(1, len(current_lane_points)):
            cv2.line(
                frame, current_lane_points[i - 1], current_lane_points[i], (0, 255, 255), 2)

        for p in current_lane_points:
            cv2.circle(frame, p, 5, (0, 0, 255), -1)

        cv2.putText(
            frame,
            f"Drawing lane {lane_index}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 255),
            2,
        )

    # DETECTION MODE
    else:
        update_traffic_light()
        active_lane = lane_cycle[current_lane_signal]

        results = model(frame, verbose=False)[0]
        lane_vehicle_count = {lane: 0 for lane in lanes}

        for box in results.boxes:
            cls = model.names[int(box.cls[0])]
            if cls not in VEHICLE_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            lane = get_lane(cx, cy)
            if lane:
                lane_vehicle_count[lane] += 1

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

        # DRAW LANES
        for lane, points in lanes.items():
            pts = np.array(points, np.int32).reshape((-1, 1, 2))
            color = (0, 255, 0) if lane == active_lane else (0, 0, 255)
            cv2.polylines(frame, [pts], True, color, 2)
            cv2.putText(
                frame, lane, points[0], cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # TERMINAL OUTPUT
        print("\n----------------------------")
        print(f"ACTIVE LANE: {active_lane}")
        print(f"LIGHT: {light_state}")
        for lane in lanes:
            state = light_state if lane == active_lane else "RED"
            print(
                f"{lane} | Vehicles: {lane_vehicle_count[lane]} | Light: {state}")

    cv2.imshow("Intersection", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord("n") and drawing_mode:
        if len(current_lane_points) < 3:
            print("❌ Lane needs at least 3 points")
            continue

        lanes[f"lane_{lane_index}"] = current_lane_points.copy()
        print(f"✅ lane_{lane_index} saved")

        lane_index += 1
        current_lane_points.clear()

        if lane_index > TOTAL_LANES:
            print("All lanes drawn. Press 's' to save.")
            drawing_mode = True

    elif key == ord("s") and drawing_mode:
        if len(lanes) != TOTAL_LANES:
            print("❌ Draw all 4 lanes first")
            continue

        with open(LANE_FILE, "w") as f:
            json.dump(lanes, f, indent=2)

        print("✅ Lanes saved. Switching to detection mode.")
        drawing_mode = False
        lane_cycle = list(lanes.keys())

    elif key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
