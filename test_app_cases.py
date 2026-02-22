import types
import numpy as np
import pytest
import unittest
import json
import os
from unittest.mock import patch, MagicMock


class TestTrafficApp(unittest.TestCase):
    def setUp(self):
        # Use a sample lane file for testing
        self.lane_file = "test_lanes.json"
        self.lane_data = {
            "lane_1": [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]],
            "lane_2": [[20, 20], [20, 30], [30, 30], [30, 20], [20, 20]]
        }
        with open(self.lane_file, "w") as f:
            json.dump(self.lane_data, f)

    def tearDown(self):
        if os.path.exists(self.lane_file):
            os.remove(self.lane_file)

    def test_lane_json_load(self):
        # Test that lane JSON loads and has correct structure
        with open(self.lane_file) as f:
            data = json.load(f)
        self.assertIn("lane_1", data)
        self.assertEqual(len(data["lane_1"]), 5)

    @patch("app.lanes", {"lane_1": {"signal": "GREEN", "count": 2, "occupied": True}, "lane_2": {"signal": "RED", "count": 0, "occupied": False}})
    def test_lane_status_api(self):
        # Simulate Flask test client for /lane_status
        from app import app
        client = app.test_client()
        response = client.get("/lane_status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(any(lane["signal"] == "GREEN" for lane in data))

    def test_vehicle_detection_logic(self):
        # Simulate a detection and lane assignment
        import numpy as np
        polygon = np.array([[0, 0], [0, 10], [10, 10], [
                           10, 0], [0, 0]], dtype=np.int32)
        point_inside = (5, 5)
        point_outside = (20, 20)
        import cv2
        self.assertGreaterEqual(cv2.pointPolygonTest(
            polygon, point_inside, False), 0)
        self.assertLess(cv2.pointPolygonTest(polygon, point_outside, False), 0)


if __name__ == "__main__":
    unittest.main()


# --- Integration test with mocked YOLO and video frame ---


def test_yolo_detection_pipeline(monkeypatch):
    # Simulate a frame (dummy image)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Simulate YOLO model output
    class DummyBox:
        def __init__(self):
            self.cls = [0]  # class index
            self.xyxy = [[100, 100, 200, 200]]

    class DummyResult:
        def __init__(self):
            self.boxes = [DummyBox()]

    class DummyModel:
        names = {0: "car"}

        def __call__(self, frame, verbose=False):
            return [DummyResult()]

    # Patch YOLO in app.py
    import app
    monkeypatch.setattr(app, "model", DummyModel())

    # Patch lanes to a known polygon
    app.lanes = {
        "lane_1": {
            "polygon": np.array([[90, 90], [90, 210], [210, 210], [210, 90], [90, 90]], dtype=np.int32),
            "occupied": False, "last_seen": 0, "signal": "GREEN", "count": 0
        }
    }

    # Patch point_in_lane to use the test polygon
    def test_point_in_lane(cx, cy):
        if cv2.pointPolygonTest(app.lanes["lane_1"]["polygon"], (cx, cy), False) >= 0:
            return "lane_1"
        return None
    monkeypatch.setattr(app, "point_in_lane", test_point_in_lane)

    # Patch vehicle_memory and vehicle_id_counter
    app.vehicle_memory = {}
    app.vehicle_id_counter = 0

    # Run one iteration of detection logic from generate_frames
    # (simulate only the detection/assignment part)
    results = app.model(frame, verbose=False)[0]
    detected = False
    for box in results.boxes:
        cls = app.model.names[int(box.cls[0])]
        if cls != "car":
            continue
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        current_lane = app.point_in_lane(cx, cy)
        if current_lane:
            detected = True
    assert detected, "Vehicle should be detected and assigned to a lane"
