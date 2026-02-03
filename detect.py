import cv2
import time
from ultralytics import YOLO

# =========================
# CONFIG
# =========================

CAMERA_INDEX = 0
MODEL_PATH = "yolov8l.pt"   # large model, good accuracy

VEHICLE_CLASSES = ["car", "truck", "bus"]

# ---- LANE DEFINITIONS ----
# Adjust these numbers ONCE based on your camera view
# (x1, y1, x2, y2)
LANES = {
    "lane_1": (100, 0, 300, 240),     # top
    "lane_2": (340, 0, 540, 240),     # right
    "lane_3": (100, 260, 300, 480),   # bottom
    "lane_4": (0, 0, 100, 480),       # left
}

# Traffic light timing (seconds)
GREEN_TIME = 5
YELLOW_TIME = 2

# =========================
# INIT
# =========================

model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    raise RuntimeError("❌ Webcam not detected")

lane_cycle = list(LANES.keys())
current_lane_index = 0
light_state = "GREEN"
last_switch_time = time.time()

# =========================
# FUNCTIONS
# =========================

def get_lane(cx, cy):
    for lane, (x1, y1, x2, y2) in LANES.items():
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            return lane
    return None


def update_traffic_light():
    global light_state, current_lane_index, last_switch_time

    elapsed = time.time() - last_switch_time

    if light_state == "GREEN" and elapsed >= GREEN_TIME:
        light_state = "YELLOW"
        last_switch_time = time.time()

    elif light_state == "YELLOW" and elapsed >= YELLOW_TIME:
        light_state = "GREEN"
        current_lane_index = (current_lane_index + 1) % len(lane_cycle)
        last_switch_time = time.time()


# =========================
# MAIN LOOP
# =========================

while True:
    ret, frame = cap.read()
    if not ret:
        break

    update_traffic_light()

    active_lane = lane_cycle[current_lane_index]

    # Run YOLO
    results = model(frame, verbose=False)[0]

    lane_vehicle_count = {lane: 0 for lane in LANES}

    for box in results.boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]

        if cls_name not in VEHICLE_CLASSES:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        lane = get_lane(cx, cy)
        if lane:
            lane_vehicle_count[lane] += 1

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
            cv2.putText(
                frame,
                f"{cls_name} ({lane})",
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

    # Draw lanes
    for lane, (x1, y1, x2, y2) in LANES.items():
        color = (0, 255, 0) if lane == active_lane else (0, 0, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            lane,
            (x1 + 5, y1 + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

    # =========================
    # TERMINAL OUTPUT
    # =========================
    print("\n==============================")
    print(f"ACTIVE LANE : {active_lane}")
    print(f"LIGHT STATE : {light_state}")
    print("------------------------------")

    for lane in LANES:
        if lane == active_lane:
            state = light_state
        else:
            state = "RED"

        print(f"{lane} | Vehicles: {lane_vehicle_count[lane]} | Light: {state}")

    # Show video
    cv2.imshow("Toy Traffic Intersection", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# =========================
# CLEANUP
# =========================

cap.release()
cv2.destroyAllWindows()
