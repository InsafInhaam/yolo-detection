import argparse
import json
import os

import cv2
import numpy as np


WINDOW_NAME = "Lane Drawer"


class LaneDrawer:
    def __init__(self, source, output_file, total_lanes):
        self.source = source
        self.output_file = output_file
        self.total_lanes = total_lanes

        self.current_points = []
        self.lanes = {}
        self.lane_index = 1

        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"❌ Could not open video source: {self.source}")

        self.base_frame = None

    def load_base_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("❌ Could not read frame from video source")
        self.base_frame = frame

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_points.append([int(x), int(y)])
            print(f"Point added: ({x}, {y})")

    def draw_overlay(self):
        frame = self.base_frame.copy()

        for lane_name, points in self.lanes.items():
            if len(points) >= 2:
                pts = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
            if points:
                cv2.putText(
                    frame,
                    lane_name,
                    tuple(points[0]),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2,
                )

        if len(self.current_points) >= 2:
            pts = np.array(self.current_points,
                           dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], False, (0, 255, 255), 2)

        for p in self.current_points:
            cv2.circle(frame, tuple(p), 5, (0, 0, 255), -1)

        cv2.putText(
            frame,
            f"Drawing lane_{self.lane_index}/{self.total_lanes}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            frame,
            "Left click: add point | N: next lane | U: undo | S: save | Q: quit",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        return frame

    def save_json(self):
        output_dir = os.path.dirname(os.path.abspath(self.output_file))
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(self.output_file, "w") as f:
            json.dump(self.lanes, f, indent=2)

        print(f"✅ Saved {len(self.lanes)} lane(s) to {self.output_file}")

    def run(self):
        self.load_base_frame()

        cv2.namedWindow(WINDOW_NAME)
        cv2.setMouseCallback(WINDOW_NAME, self.mouse_callback)

        print("\nINSTRUCTIONS:")
        print("- Left click: add lane points")
        print("- N: finish current lane (min 3 points)")
        print("- U: undo last point")
        print("- S: save JSON and exit")
        print("- Q: quit without saving\n")

        while True:
            frame = self.draw_overlay()
            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("u"):
                if self.current_points:
                    removed = self.current_points.pop()
                    print(f"↩️  Removed point: {removed}")

            elif key == ord("n"):
                if len(self.current_points) < 3:
                    print("❌ Lane needs at least 3 points")
                    continue

                lane_name = f"lane_{self.lane_index}"
                points = [p[:] for p in self.current_points]
                if points[0] != points[-1]:
                    points.append(points[0][:])

                self.lanes[lane_name] = points
                print(f"✅ Saved {lane_name} with {len(points)} points")

                self.current_points = []
                self.lane_index += 1

                if self.lane_index > self.total_lanes:
                    print("All lanes finished. Press S to save JSON.")

            elif key == ord("s"):
                if not self.lanes:
                    print("❌ No lanes to save")
                    continue

                self.save_json()
                break

            elif key == ord("q"):
                print("Exited without saving.")
                break

        self.cap.release()
        cv2.destroyAllWindows()


def parse_source(value):
    if value.isdigit():
        return int(value)
    return value


def main():
    parser = argparse.ArgumentParser(
        description="Draw lane polygons and export them as JSON."
    )
    parser.add_argument(
        "--source",
        default="videos/traffic.mp4",
        help="Video source path or webcam index (e.g. 0)",
    )
    parser.add_argument(
        "--output",
        default="real_lane.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--lanes",
        type=int,
        default=4,
        help="Expected number of lanes to draw",
    )

    args = parser.parse_args()
    source = parse_source(args.source)

    drawer = LaneDrawer(
        source=source, output_file=args.output, total_lanes=args.lanes)
    drawer.run()


if __name__ == "__main__":
    main()
