import cv2
import json
import time
import numpy as np
import serial
from ultralytics import YOLO

# =========================
# CONFIG
# =========================

CAMERA_INDEX = 0
MODEL_PATH = "yolov8l.pt"
LANE_FILE = "lanes.json"

SERIAL_PORT = "/dev/cu.usbmodem1301"  # Arduino serial port
BAUD_RATE = 115200

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
pending_lane_index = None
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
    """Send traffic light command to Arduino via serial with retry logic"""
    global ser
    try:
        arduino_lane = LANE_TO_ARDUINO.get(lane)
        if not arduino_lane or not ser or not ser.is_open:
            return

        # Format: "lane,color,state\r\n" with carriage return
        command = f"{arduino_lane},{color.lower()},1\r\n"

        # Clear input buffer first
        try:
            ser.flushInput()
        except:
            pass

        # Send command
        ser.write(command.encode())
        ser.flush()
        print(f"📡 {lane}: {color.upper()}")

        # Wait for response with timeout
        time.sleep(0.05)
        response_received = False
        for i in range(5):
            if ser.in_waiting:
                try:
                    response = ser.readline().decode('utf-8', errors='ignore').strip()
                    if response and "OK" in response:
                        response_received = True
                        break
                except:
                    pass
            time.sleep(0.02)

        return response_received

    except Exception as e:
        print(f"❌ Serial error: {e}")
        return False


def update_traffic_lights(lane_counts):
    global light_state, current_lane_index, last_switch_time, pending_lane_index

    elapsed = time.time() - last_switch_time

    if light_state == "GREEN" and elapsed >= GREEN_TIME:
        active_lane = lane_order[current_lane_index]
        best_lane = max(lane_counts, key=lane_counts.get)
        if best_lane != active_lane and (lane_counts[best_lane] - lane_counts[active_lane]) >= COUNT_SWITCH_DELTA:
            # Only switch if another lane has a meaningful advantage
            light_state = "YELLOW"
            pending_lane_index = lane_order.index(best_lane)
            last_switch_time = time.time()
            send_to_arduino(active_lane, "yellow")

    elif light_state == "YELLOW" and elapsed >= YELLOW_TIME:
        light_state = "GREEN"
        if pending_lane_index is not None:
            current_lane_index = pending_lane_index
            pending_lane_index = None
        last_switch_time = time.time()
        # Send green to new active lane
        active_lane = lane_order[current_lane_index]
        send_to_arduino(active_lane, "green")

    active_lane = lane_order[current_lane_index]

    for lane in lanes:
        lanes[lane]["signal"] = light_state if lane == active_lane else "RED"


# =========================
# INIT SERIAL CONNECTION
# =========================

print("✅ Webcam opened. Starting detection...")

# Initialize serial connection
ser = None
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
    time.sleep(2)  # Wait for Arduino to initialize
    print(f"✅ Serial connection established on {SERIAL_PORT}")

    # Clear any buffered data
    ser.flushInput()
    ser.flushOutput()
    time.sleep(0.5)

    # Read startup message from Arduino
    if ser.in_waiting:
        startup = ser.readline().decode('utf-8', errors='ignore').strip()
        print(f"   Arduino: {startup}")

    # Send initial green to first lane
    send_to_arduino(lane_order[0], "green")
    print(f"✅ Initial signal sent")
except Exception as e:
    print(f"❌ Serial connection failed: {e}")
    print("Continuing without Arduino control...")
    ser = None

cv2.namedWindow("Intersection")

# =========================
# VEHICLE MEMORY (lightweight tracking)
# =========================

vehicle_memory = {}
vehicle_id_counter = 0

# Enhanced tracking: Keep historical lane and direction info


def cleanup_old_vehicles(timeout=5):
    """Remove vehicles not seen for timeout seconds"""
    global vehicle_memory
    now = time.time()
    stale = [vid for vid, v in vehicle_memory.items() if now -
             v.get("time", 0) > timeout]
    for vid in stale:
        del vehicle_memory[vid]

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
    cleanup_old_vehicles(timeout=5)  # Clean up stale vehicles

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
        current_lane = point_in_lane(cx, cy)
        if not current_lane:
            continue

        # Draw detected vehicle
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

        # Robust tracking: find BEST match (closest vehicle within threshold)
        vid = None
        best_distance = 50
        for k, v in vehicle_memory.items():
            dist = np.linalg.norm(np.array(v["pos"]) - np.array(centroid))
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
                "lane_history": [current_lane],  # Track lane transitions
                "direction": "UNKNOWN"
            }
        else:
            # Update existing vehicle
            prev_pos = vehicle_memory[vid]["pos"]
            prev_lane = vehicle_memory[vid].get("lane", current_lane)

            # Infer direction only if vehicle moved significantly
            direction = infer_direction(prev_pos, centroid)
            vehicle_memory[vid]["direction"] = direction

            # Track lane transitions (only update lane if moved to different lane)
            if current_lane != prev_lane:
                past_lanes = vehicle_memory[vid].get("lane_history", [])
                # Avoid flicker from noise
                if current_lane not in past_lanes[-3:]:
                    vehicle_memory[vid]["lane_history"].append(current_lane)
                    vehicle_memory[vid]["lane"] = current_lane

            vehicle_memory[vid]["pos"] = centroid
            vehicle_memory[vid]["time"] = now

        # Mark lane as occupied and show direction
        lanes[current_lane]["occupied"] = True
        lanes[current_lane]["last_seen"] = now

        direction = vehicle_memory[vid]["direction"]
        cv2.putText(
            frame,
            f"{current_lane} | {direction}",
            (x1, y1 - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

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

    # Compute per-lane vehicle counts (vehicles seen recently)
    lane_counts = {l: 0 for l in lanes}
    for vid, v in vehicle_memory.items():
        if now - v.get("time", 0) <= EMPTY_TIMEOUT:
            l = v.get("lane")  # Use CURRENT lane
            if l in lane_counts:
                lane_counts[l] += 1

    update_traffic_lights(lane_counts)

    # TERMINAL OUTPUT
    print("\n" + "="*50)
    print("LANE STATUS:")
    for lane, data in lanes.items():
        count = lane_counts.get(lane, 0)
        signal_emoji = "🟢" if data["signal"] == "GREEN" else "🟡" if data["signal"] == "YELLOW" else "🔴"
        print(
            f"  {signal_emoji} {lane}: {data['signal']:6} | Vehicles: {count}")

    # Optional: Show vehicle details (comment out if too verbose)
    # print(f"\nActive vehicles: {len(vehicle_memory)}")
    # for vid, v in vehicle_memory.items():
    #     print(f"  ID {vid}: {v.get('lane')} | {v.get('direction')}")

    cv2.imshow("Intersection", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Cleanup: Close serial connection
if ser and ser.is_open:
    ser.close()
    print("\n✅ Serial connection closed")

cap.release()
cv2.destroyAllWindows()
