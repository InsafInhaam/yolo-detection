from flask import Flask, render_template, Response, jsonify, request
import cv2
import json
import time
import numpy as np
import os
from ultralytics import YOLO
from threading import Lock
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

# =========================
# CONFIG
# =========================

CAMERA_INDEX = "videos/traffic.mp4"
MODEL_PATH = "yolov8l.pt"
LANE_FILE = os.environ.get("LANE_FILE", "real_lane.json")
INTERSECTIONS_FILE = os.environ.get("INTERSECTIONS_FILE", "intersections.json")
MONGODB_URI = os.environ.get(
    "MONGODB_URI", "mongodb+srv://insafinhaam732:L9XrUu9J5AnIuGVt@cluster0.cng0d5o.mongodb.net/?appName=Cluster0")
MONGODB_DB = os.environ.get("MONGODB_DB", "traffic_monitoring")
MONGO_LOG_INTERVAL = 2.0

VEHICLE_CLASSES = ["car", "truck", "bus", "motorcycle", "bicycle"]

CLASS_LABELS = {
    "car": "car",
    "truck": "truck",
    "bus": "bus",
    "motorcycle": "bike",
    "bicycle": "bike"
}

GREEN_TIME = 5
YELLOW_TIME = 2
EMPTY_TIMEOUT = 1.5
COUNT_SWITCH_DELTA = 2

SIM_TICK_SECONDS = 1.0
SIM_HANDOFF_RATIO = 0.5
SIM_MIN_HANDOFF = 1
SIM_MIRROR_INTERSECTION = "intersection_1"

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

LANE_ROUTES = {
    "lane_1": "lane_2",
    "lane_3": "lane_4",
    "lane_5": "lane_7",
    "lane_6": None
}

PAIRED_LANES = {
    "lane_1": "lane_2",
    "lane_2": "lane_1",
    "lane_3": "lane_4",
    "lane_4": "lane_3",
    "lane_6": "lane_7",
    "lane_7": "lane_6"
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

intersections = {}
simulation_counts = {}
last_simulation_tick = 0.0
if os.path.exists(INTERSECTIONS_FILE):
    try:
        with open(INTERSECTIONS_FILE, "r") as f:
            intersections = json.load(f).get("intersections", {})
    except (json.JSONDecodeError, ValueError, FileNotFoundError):
        intersections = {}

if intersections:
    for intersection_id, config in intersections.items():
        lanes_list = config.get("lanes", [])
        simulation_counts[intersection_id] = {
            lane: 0 for lane in lanes_list
        }
    print(
        f"✅ Loaded intersections from {INTERSECTIONS_FILE} ({len(intersections)} nodes)")
else:
    print("⚠️  No intersections config found for simulation")

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

last_mongo_log = 0.0
mongo_client = None
mongo_db = None

try:
    mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ping')
    mongo_db = mongo_client[MONGODB_DB]
    print(f"✅ Connected to MongoDB: {MONGODB_DB}")
except Exception as e:
    print(f"⚠️  MongoDB connection failed: {e}")
    mongo_db = None

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
        return ""

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


def _parse_target_lane(target):
    if not target:
        return None, None
    if "." not in target:
        return None, None
    intersection_id, lane_id = target.split(".", 1)
    return intersection_id, lane_id


def _handoff_amount(count):
    if count <= 0:
        return 0
    transfer = int(count * SIM_HANDOFF_RATIO)
    if transfer < SIM_MIN_HANDOFF:
        transfer = SIM_MIN_HANDOFF
    return min(transfer, count)


def save_to_mongodb():
    global last_mongo_log
    if mongo_db is None:
        return

    now = time.time()
    if now - last_mongo_log < MONGO_LOG_INTERVAL:
        return
    last_mongo_log = now

    try:
        lanes_collection = mongo_db["lanes"]
        simulation_collection = mongo_db["simulations"]

        timestamp = datetime.utcnow()

        lanes_data = {
            "timestamp": timestamp,
            "lanes": []
        }
        for lane, data in lanes.items():
            lanes_data["lanes"].append({
                "lane": lane,
                "count": data["count"],
                "signal": data["signal"],
                "occupied": data["occupied"]
            })
        lanes_collection.insert_one(lanes_data)

        sim_data = {
            "timestamp": timestamp,
            "intersections": []
        }
        for intersection_id, lanes_map in simulation_counts.items():
            sim_data["intersections"].append({
                "intersection": intersection_id,
                "lanes": [
                    {"lane": lane_id, "count": count}
                    for lane_id, count in lanes_map.items()
                ]
            })
        simulation_collection.insert_one(sim_data)
    except Exception as e:
        print(f"MongoDB logging error: {e}")


def tick_simulation():
    global last_simulation_tick
    if not intersections:
        return

    now = time.time()
    if now - last_simulation_tick < SIM_TICK_SECONDS:
        return
    last_simulation_tick = now

    if SIM_MIRROR_INTERSECTION in simulation_counts:
        for lane_id in simulation_counts[SIM_MIRROR_INTERSECTION].keys():
            if lane_id in lanes:
                simulation_counts[SIM_MIRROR_INTERSECTION][lane_id] = lanes[lane_id]["count"]

    for intersection_id, lanes_map in simulation_counts.items():
        if intersection_id == SIM_MIRROR_INTERSECTION:
            continue
        for lane_id in lanes_map.keys():
            lanes_map[lane_id] = 0

    transfers = []
    for intersection_id, config in intersections.items():
        outgoing = config.get("outgoing", {})
        for lane_id, target in outgoing.items():
            target_intersection, target_lane = _parse_target_lane(target)
            if not target_intersection or not target_lane:
                continue
            src_count = simulation_counts.get(
                intersection_id, {}).get(lane_id, 0)
            transfer = _handoff_amount(src_count)
            if transfer <= 0:
                continue
            transfers.append((
                intersection_id,
                lane_id,
                target_intersection,
                target_lane,
                transfer
            ))

    for src_intersection, src_lane, dst_intersection, dst_lane, amount in transfers:
        if src_intersection not in simulation_counts:
            continue
        if dst_intersection not in simulation_counts:
            continue
        if src_lane not in simulation_counts[src_intersection]:
            continue
        if dst_lane not in simulation_counts[dst_intersection]:
            continue
        simulation_counts[src_intersection][src_lane] -= amount
        simulation_counts[dst_intersection][dst_lane] += amount


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
    paired_lane = PAIRED_LANES.get(active_lane)
    green_lanes = {active_lane, paired_lane}

    for lane in lanes:
        if lane in green_lanes:
            lanes[lane]["signal"] = light_state
        else:
            lanes[lane]["signal"] = "RED"

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
                        "direction": "",
                        "predicted_next_lane": LANE_ROUTES.get(current_lane)
                    }
                else:
                    prev_pos = vehicle_memory[vid]["pos"]
                    prev_lane = vehicle_memory[vid].get("lane", current_lane)

                    direction = infer_direction(prev_pos, centroid)
                    vehicle_memory[vid]["direction"] = direction

                    if current_lane != prev_lane:
                        vehicle_memory[vid]["lane"] = current_lane
                        vehicle_memory[vid]["predicted_next_lane"] = LANE_ROUTES.get(
                            current_lane)

                    vehicle_memory[vid]["pos"] = centroid
                    vehicle_memory[vid]["time"] = now

                lanes[current_lane]["occupied"] = True
                lanes[current_lane]["last_seen"] = now

                direction = vehicle_memory[vid]["direction"]
                class_label = CLASS_LABELS.get(cls, cls)
                next_lane = vehicle_memory[vid].get("predicted_next_lane")
                label_text = class_label
                if direction:
                    label_text = f"{label_text} | {direction}"
                if next_lane:
                    label_text = f"{label_text} -> {next_lane}"
                cv2.putText(
                    frame,
                    label_text,
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
            save_to_mongodb()

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
                next_lane = LANE_ROUTES.get(lane)
                next_lane_text = f" -> {next_lane}" if next_lane else ""
                cv2.putText(
                    frame,
                    f"{lane} {direction}{next_lane_text} [{data['count']}]",
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
                "next_lane": LANE_ROUTES.get(lane),
                "signal": data["signal"],
                "count": data["count"],
                "occupied": data["occupied"]
            })
        return jsonify(status)


@app.route('/simulation_status')
def simulation_status():
    with lock:
        tick_simulation()
        status = []
        for intersection_id, config in intersections.items():
            outgoing = config.get("outgoing", {})
            lanes_status = []
            for lane_id in config.get("lanes", []):
                target = outgoing.get(lane_id)
                target_intersection, target_lane = _parse_target_lane(target)
                downstream_count = 0
                if target_intersection and target_lane:
                    downstream_count = simulation_counts.get(
                        target_intersection, {}).get(target_lane, 0)
                lanes_status.append({
                    "lane": lane_id,
                    "count": simulation_counts.get(intersection_id, {}).get(lane_id, 0),
                    "outgoing_to": target,
                    "downstream_count": downstream_count
                })
            status.append({
                "intersection": intersection_id,
                "lanes": lanes_status
            })
        return jsonify(status)


@app.route('/simulation/update', methods=['POST'])
def simulation_update():
    if not intersections:
        return jsonify({"error": "simulation config not loaded"}), 400

    payload = request.get_json(silent=True) or {}
    updates = payload.get("counts")

    with lock:
        if updates:
            for intersection_id, lanes_map in updates.items():
                if intersection_id not in simulation_counts:
                    continue
                for lane_id, count in lanes_map.items():
                    if lane_id in simulation_counts[intersection_id]:
                        simulation_counts[intersection_id][lane_id] = max(
                            0, int(count))
        else:
            intersection_id = payload.get("intersection")
            lane_id = payload.get("lane")
            count = payload.get("count")
            if (intersection_id not in simulation_counts or
                    lane_id not in simulation_counts[intersection_id] or
                    count is None):
                return jsonify({"error": "invalid simulation update"}), 400
            simulation_counts[intersection_id][lane_id] = max(0, int(count))

        tick_simulation()
        return jsonify({"ok": True})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print("🚀 Starting Traffic Monitoring Web App...")
    print(f"📹 Open http://127.0.0.1:{port} in your browser")
    app.run(debug=True, threaded=True, use_reloader=False, port=port)
