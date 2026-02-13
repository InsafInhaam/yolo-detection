from flask import Flask, render_template, Response, jsonify
import cv2
import json
import time
import numpy as np
import os
from ultralytics import YOLO
from threading import Lock

app = Flask(__name__)

# =========================
# CONFIG
# =========================

CAMERA_INDEX = "videos/traffic.mp4"
MODEL_PATH = "yolov8l.pt"
LANE_FILE = os.environ.get("LANE_FILE", "real_lane.json")

VEHICLE_CLASSES = ["car", "truck", "bus"]

GREEN_TIME = 5
YELLOW_TIME = 2
EMPTY_TIMEOUT = 1.5
COUNT_SWITCH_DELTA = 2

LANE_DIRECTIONS = {
    "lane_1": "UP",
    "lane_2": "DOWN",
    "lane_3": "RIGHT",
    "lane_4": "LEFT",
    "lane_6": "LEFT",
    "lane_7": "RIGHT",
    "lane_8": "DOWN",
    "lane_9": "UP",
}

# =========================
# LOAD LANES
# =========================

raw_lanes = {}
selected_lane_file = None
lane_file_candidates = [
    LANE_FILE, "lanes.json"] if LANE_FILE != "lanes.json" else [LANE_FILE]

for candidate in lane_file_candidates:
    try:
        with open(candidate, "r") as f:
            data = json.load(f)
        if not data:
            raise ValueError("Lanes file is empty")
        raw_lanes = data
        selected_lane_file = candidate
        break
    except (json.JSONDecodeError, ValueError, FileNotFoundError):
        continue

if not raw_lanes:
    print("❌ Error loading lanes: no valid lane JSON found")
    print(f"⚠️  Tried files: {lane_file_candidates}")
    print("⚠️  Run: python draw_lanes.py --output real_lane.json")
else:
    print(f"✅ Loaded lanes from {selected_lane_file} ({len(raw_lanes)} lanes)")

lanes = {}
for lane, points in raw_lanes.items():
    lanes[lane] = {
        "polygon": np.array(points, dtype=np.int32),
        "occupied": False,
        "last_seen": 0,
        "signal": "RED",
        "count": 0
    }

lane_order = list(lanes.keys())
current_lane_index = 0
pending_lane_index = None
light_state = "GREEN"
last_switch_time = time.time()

# =========================
# GLOBALS
# =========================

model = YOLO(MODEL_PATH)
vehicle_memory = {}
vehicle_id_counter = 0
lock = Lock()

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


def cleanup_old_vehicles(timeout=5):
    global vehicle_memory
    now = time.time()
    stale = [vid for vid, v in vehicle_memory.items()
             if now - v.get("time", 0) > timeout]
    for vid in stale:
        del vehicle_memory[vid]


def update_traffic_lights(lane_counts):
    global light_state, current_lane_index, last_switch_time, pending_lane_index

    if not lane_order:
        return

    elapsed = time.time() - last_switch_time

    if light_state == "GREEN" and elapsed >= GREEN_TIME:
        active_lane = lane_order[current_lane_index]
        best_lane = max(lane_counts, key=lane_counts.get)
        if best_lane != active_lane and (lane_counts[best_lane] - lane_counts[active_lane]) >= COUNT_SWITCH_DELTA:
            light_state = "YELLOW"
            pending_lane_index = lane_order.index(best_lane)
            last_switch_time = time.time()

    elif light_state == "YELLOW" and elapsed >= YELLOW_TIME:
        light_state = "GREEN"
        if pending_lane_index is not None:
            current_lane_index = pending_lane_index
            pending_lane_index = None
        last_switch_time = time.time()

    active_lane = lane_order[current_lane_index] if lane_order else None

    for lane in lanes:
        lanes[lane]["signal"] = light_state if lane == active_lane else "RED"

# =========================
# VIDEO PROCESSING
# =========================


def generate_frames():
    global vehicle_id_counter

    source = CAMERA_INDEX
    if isinstance(CAMERA_INDEX, str):
        source = os.path.abspath(CAMERA_INDEX)
        if not os.path.exists(source):
            print(f"❌ Video file not found: {source}")
            return

    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"❌ Video source not detected: {source}")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            if isinstance(CAMERA_INDEX, str):
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            break

        now = time.time()

        with lock:
            cleanup_old_vehicles(timeout=5)

            # Reset lane counts
            for lane in lanes:
                lanes[lane]["count"] = 0
                if now - lanes[lane]["last_seen"] > EMPTY_TIMEOUT:
                    lanes[lane]["occupied"] = False

            # YOLO Detection
            results = model(frame, verbose=False)[0]

            for box in results.boxes:
                cls = model.names[int(box.cls[0])]
                if cls not in VEHICLE_CLASSES:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                centroid = (cx, cy)

                current_lane = point_in_lane(cx, cy)
                if not current_lane:
                    continue

                # Draw detection
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

                # Track vehicle
                vid = None
                best_distance = 50
                for k, v in vehicle_memory.items():
                    dist = np.linalg.norm(
                        np.array(v["pos"]) - np.array(centroid))
                    if dist < best_distance:
                        best_distance = dist
                        vid = k

                if vid is None:
                    vid = vehicle_id_counter
                    vehicle_id_counter += 1
                    vehicle_memory[vid] = {
                        "pos": centroid,
                        "time": now,
                        "lane": current_lane,
                        "direction": "UNKNOWN"
                    }
                else:
                    prev_pos = vehicle_memory[vid]["pos"]
                    prev_lane = vehicle_memory[vid].get("lane", current_lane)

                    direction = infer_direction(prev_pos, centroid)
                    vehicle_memory[vid]["direction"] = direction

                    if current_lane != prev_lane:
                        vehicle_memory[vid]["lane"] = current_lane

                    vehicle_memory[vid]["pos"] = centroid
                    vehicle_memory[vid]["time"] = now

                lanes[current_lane]["occupied"] = True
                lanes[current_lane]["last_seen"] = now

                direction = vehicle_memory[vid]["direction"]
                cv2.putText(
                    frame,
                    f"{cls} | {direction}",
                    (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )

            # Count vehicles per lane
            lane_counts = {l: 0 for l in lanes}
            for vid, v in vehicle_memory.items():
                if now - v.get("time", 0) <= EMPTY_TIMEOUT:
                    l = v.get("lane")
                    if l in lane_counts:
                        lane_counts[l] += 1

            for lane in lanes:
                lanes[lane]["count"] = lane_counts.get(lane, 0)

            update_traffic_lights(lane_counts)

            # Draw lanes with signals
            for lane, data in lanes.items():
                if data["signal"] == "GREEN":
                    color = (0, 255, 0)
                elif data["signal"] == "YELLOW":
                    color = (0, 255, 255)
                else:
                    color = (0, 0, 255)

                cv2.polylines(frame, [data["polygon"]], True, color, 3)

                # Lane label with count
                label_pos = tuple(data["polygon"][0])
                direction = LANE_DIRECTIONS.get(lane, "")
                cv2.putText(
                    frame,
                    f"{lane} {direction} [{data['count']}]",
                    label_pos,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color,
                    2
                )

        # Encode frame
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# =========================
# ROUTES
# =========================


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/lane_status')
def lane_status():
    with lock:
        status = []
        for lane, data in lanes.items():
            status.append({
                "lane": lane,
                "direction": LANE_DIRECTIONS.get(lane, ""),
                "signal": data["signal"],
                "count": data["count"],
                "occupied": data["occupied"]
            })
        return jsonify(status)


if __name__ == '__main__':
    print("🚀 Starting Traffic Monitoring Web App...")
    print("📹 Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True, threaded=True, use_reloader=False)
