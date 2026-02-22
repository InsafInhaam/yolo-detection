# YOLO Traffic Intersection Detection

An intelligent traffic intersection management system using YOLOv8 object detection to monitor vehicle flow and control traffic signals across multiple lanes.

## Features

- **Real-time Vehicle Detection**: Uses YOLOv8 (small or large models) to detect cars, trucks, buses, motorcycles, and bicycles
- **Multi-Lane Support**: Supports up to 8 configurable traffic lanes with polygon boundaries
- **Adaptive Traffic Signal Control**: Automated green/yellow/red signal timing based on vehicle density
- **Paired Lane Synchronization**: Synchronized signals across lane pairs (lane_1↔lane_2, lane_3↔lane_4, lane_6↔lane_7)
- **Multi-Intersection Simulation**: Simulate vehicle flow between multiple intersections with automatic handoff
- **Vehicle Tracking**: Tracks individual vehicles across frames and detects movement direction
- **Lane Drawing Interface**: Interactive tool to define custom lane boundaries
- **Web Dashboard**: Real-time monitoring via Flask web application with live video feed
- **MongoDB Logging**: Automatic real-time data persistence for analysis and reporting

## Project Structure

- **`app.py`**: Flask web application with real-time traffic monitoring
- **`detect.py`**: Basic detection with predefined rectangular lane regions
- **`draw_and_detect.py`**: Interactive lane drawing tool followed by detection mode
- **`intersection_final.py`**: Advanced detection with polygon-based lanes and occupancy tracking
- **`lanes.json`**: Stores custom lane polygon definitions
- **`real_lane.json`**: Real lane boundaries for Colombo city traffic video
- **`intersections.json`**: Multi-intersection configuration with vehicle handoff rules
- **`templates/index.html`**: Web dashboard UI
- **`yolov8s.pt`**: YOLOv8 Small model (faster, lighter)
- **`yolov8l.pt`**: YOLOv8 Large model (more accurate)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/InsafInhaam/yolo-detection.git
cd yolo-final
```

2. Create and activate virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Web Application (Flask)

Start the Flask web server for real-time traffic monitoring:

```bash
source venv/bin/activate
PORT=5001 python app.py
```

Then open your browser to:

```
http://127.0.0.1:5001
```

Features:

- **Live Video Feed**: Real-time vehicle detection from Colombo city traffic
- **Lane Status Panel**: Current vehicle counts and signal states
- **Simulation Intersections**: Multi-intersection traffic flow simulation with handoff
- **MongoDB Logging**: Automatic saving of real-time data for analysis

### OpenCV Scripts

#### Option 1: Basic Detection (detect.py)

Predefined rectangular lanes - adjust lane coordinates in the config section:

```bash
python detect.py
```

#### Option 2: Interactive Lane Drawing (draw_and_detect.py)

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

#### Option 3: Advanced Detection (intersection_final.py)

Uses previously saved lane polygons with occupancy tracking:

```bash
python intersection_final.py
```

Press 'q' to quit any script.

## Configuration

### Flask Web App (app.py)

Edit the config section or set environment variables:

```bash
# Optional: Change port (default: 5000)
PORT=5001 python app.py

# Optional: Use different lane file
LANE_FILE=real_lane.json PORT=5001 python app.py

# Optional: Use different intersections config
INTERSECTIONS_FILE=intersections.json PORT=5001 python app.py

# Optional: Connect to MongoDB (default included in code)
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/?appName=Cluster0 PORT=5001 python app.py
```

### OpenCV Scripts

Edit the config section in any script to adjust:

- `CAMERA_INDEX`: Camera device (0 for default webcam) or video file path
- `MODEL_PATH`: Path to YOLO model file (yolov8s.pt or yolov8l.pt)
- `VEHICLE_CLASSES`: Classes to detect (car, truck, bus, motorcycle, bicycle)
- `GREEN_TIME`: Duration of green light (seconds)
- `YELLOW_TIME`: Duration of yellow light (seconds)
- `EMPTY_TIMEOUT`: Time before marking lane as empty (seconds)
- `SIM_TICK_SECONDS`: Simulation update interval
- `SIM_HANDOFF_RATIO`: Percentage of vehicles to handoff to next intersection

## System Output

### Web Application

- **Live Video Stream**: Real-time vehicle detection with bounding boxes
- **Lane Status Cards**: Vehicle count per lane with signal state (Green/Yellow/Red)
- **Total Vehicle Count**: Aggregated vehicles across all lanes
- **Simulation Panel**: Multi-intersection simulation with vehicle handoff
- **MongoDB Logging**: Automatic data persistence to MongoDB (every 2 seconds)

### OpenCV Scripts

The system displays:

- **Frame**: Live video with detected vehicles and lane boundaries
- **Terminal**: Real-time lane status including signal state and vehicle count

### Lane Colors:

- **Green**: Active lane (green light)
- **Yellow**: Lane in transition (yellow light)
- **Red**: Inactive lanes (red light)

## Data Storage

### MongoDB Collections

Real-time traffic data is automatically saved to MongoDB:

- **`lanes`**: Lane vehicle counts and signal states
  - Fields: `timestamp`, `lanes[].lane`, `lanes[].count`, `lanes[].signal`
- **`simulations`**: Multi-intersection vehicle flow
  - Fields: `timestamp`, `intersections[].intersection`, `intersections[].lanes[]`

Access your MongoDB dashboard at [console.mongodb.com](https://console.mongodb.com)

## Requirements

- Python 3.8+
- Webcam or video input device / video file
- MongoDB account (optional, for data logging)
- See `requirements.txt` for Python dependencies

## License

MIT License
