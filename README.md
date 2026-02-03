# YOLO Traffic Intersection Detection

An intelligent traffic intersection management system using YOLOv8 object detection to monitor vehicle flow and control traffic signals across multiple lanes.

## Features

- **Real-time Vehicle Detection**: Uses YOLOv8 (small or large models) to detect cars, trucks, and buses
- **Multi-Lane Support**: Supports up to 4 configurable traffic lanes
- **Traffic Signal Control**: Automated green/yellow/red signal timing
- **Lane Drawing Interface**: Interactive tool to define custom lane boundaries
- **Vehicle Counting**: Tracks vehicle count per lane
- **Occupancy Detection**: Detects if lanes are occupied or empty with timeout handling

## Project Structure

- **`detect.py`**: Basic detection with predefined rectangular lane regions
- **`draw_and_detect.py`**: Interactive lane drawing tool followed by detection mode
- **`intersection_final.py`**: Advanced detection with polygon-based lanes and occupancy tracking
- **`lanes.json`**: Stores custom lane polygon definitions
- **`yolov8s.pt`**: YOLOv8 Small model (faster, lighter)
- **`yolov8l.pt`**: YOLOv8 Large model (more accurate)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/InsafInhaam/yolo-detection.git
cd yolo-final
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Option 1: Basic Detection (detect.py)

Predefined rectangular lanes - adjust lane coordinates in the config section:

```bash
python detect.py
```

### Option 2: Interactive Lane Drawing (draw_and_detect.py)

1. Run the script:

```bash
python draw_and_detect.py
```

2. Left-click to add lane points (minimum 3 points per lane)
3. Press 'n' to finish a lane
4. Draw all 4 lanes
5. Press 's' to save and start detection

Controls:

- **Left Click**: Add lane point
- **'n'**: Finish current lane
- **'s'**: Save lanes and switch to detection mode
- **'q'**: Quit

### Option 3: Advanced Detection (intersection_final.py)

Uses previously saved lane polygons with occupancy tracking:

```bash
python intersection_final.py
```

Press 'q' to quit any script.

## Configuration

Edit the config section in any script to adjust:

- `CAMERA_INDEX`: Camera device (0 for default webcam)
- `MODEL_PATH`: Path to YOLO model file
- `VEHICLE_CLASSES`: Classes to detect (car, truck, bus)
- `GREEN_TIME`: Duration of green light (seconds)
- `YELLOW_TIME`: Duration of yellow light (seconds)
- `EMPTY_TIMEOUT`: Time before marking lane as empty (seconds)

## System Output

The system displays:

- **Frame**: Live video with detected vehicles and lane boundaries
- **Terminal**: Real-time lane status including signal state and vehicle count

### Lane Colors:

- **Green**: Active lane (green light)
- **Yellow**: Lane in transition (yellow light)
- **Red**: Inactive lanes (red light)

## Requirements

- Python 3.8+
- Webcam or video input device
- See `requirements.txt` for dependencies

## License

MIT License
