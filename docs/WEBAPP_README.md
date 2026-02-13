# 🚦 Traffic Intersection Web Monitor

A real-time traffic intersection monitoring system with vehicle detection, lane tracking, and traffic signal management using YOLOv8, OpenCV, and Flask.

## 🎯 Features

- **Live Video Stream**: Real-time video processing with YOLO vehicle detection
- **Lane Detection**: Visual lane boundaries drawn on video with signal colors
- **Vehicle Counting**: Track vehicles in each lane in real-time
- **Traffic Signals**: Automatic signal switching based on traffic density
  - 🟢 Green - Lane active
  - 🟡 Yellow - Transition phase
  - 🔴 Red - Lane stopped
- **Web Interface**: Beautiful, responsive dashboard showing all data
- **9-Lane Support**: Handles complex intersections with multiple lanes

## 📋 Prerequisites

- Python 3.8+
- Webcam or video file
- YOLOv8 model file (yolov8l.pt or yolov8s.pt)
- lanes.json file with lane definitions

## 🚀 Quick Start

### Option 1: Using the run script (Recommended)

```bash
./run_webapp.sh
```

### Option 2: Manual setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements_flask.txt

# Run the app
python app.py
```

### Option 3: Direct run (if dependencies already installed)

```bash
python app.py
```

## 🌐 Access the Web App

Once running, open your browser and navigate to:

```
http://127.0.0.1:5000
```

## 📐 Lane Setup

If you haven't created lanes yet:

1. Run the lane drawing tool first:
   ```bash
   python docs/draw_and_detect.py
   ```
2. Click on the video to define lane polygons
3. Save lanes to lanes.json
4. Then run the web app

## 🎨 Web Interface Layout

```
┌─────────────────────────────────────────────────────────┐
│        🚦 Traffic Intersection Monitor                  │
├──────────────────────────────┬──────────────────────────┤
│                              │  Lane Status             │
│                              │  ┌────────────────────┐  │
│     Live Video Feed          │  │ LANE_1 - UP   🟢  │  │
│     (with drawn lanes)       │  │ Signal: GREEN      │  │
│                              │  │ Vehicles: 3    🚗 3│  │
│                              │  └────────────────────┘  │
│                              │  ┌────────────────────┐  │
│                              │  │ LANE_2 - DOWN 🔴  │  │
│                              │  │ Signal: RED        │  │
│                              │  │ Vehicles: 1    🚗 1│  │
│                              │  └────────────────────┘  │
│                              │                          │
│                              │   Total Active: 12       │
│                              │                          │
│                              │   Traffic Signals Legend │
└──────────────────────────────┴──────────────────────────┘
```

## ⚙️ Configuration

Edit [app.py](app.py) to customize:

```python
CAMERA_INDEX = 0          # Webcam index (0 for default)
MODEL_PATH = "yolov8l.pt" # YOLO model path
GREEN_TIME = 5            # Green light duration (seconds)
YELLOW_TIME = 2           # Yellow light duration (seconds)
COUNT_SWITCH_DELTA = 2    # Vehicle difference to trigger switch
```

## 📊 API Endpoints

- `GET /` - Main web interface
- `GET /video_feed` - MJPEG video stream
- `GET /lane_status` - JSON data of all lane statuses

Example `/lane_status` response:

```json
[
  {
    "lane": "lane_1",
    "direction": "UP",
    "signal": "GREEN",
    "count": 3,
    "occupied": true
  },
  ...
]
```

## 🎮 Controls

- The web interface auto-refreshes lane status every 500ms
- Traffic signals switch automatically based on vehicle density
- Green lane gets priority when it has significantly more vehicles

## 🔧 Troubleshooting

**Camera not detected:**

- Check CAMERA_INDEX in app.py
- Ensure webcam permissions are granted
- Try changing to 1, 2, etc. for external cameras

**No lanes shown:**

- Verify lanes.json exists and is valid
- Run draw_and_detect.py to create lanes

**Slow performance:**

- Use yolov8s.pt (faster) instead of yolov8l.pt
- Reduce video resolution in your camera settings

**Port already in use:**

- Change port in app.py: `app.run(port=5001)`

## 📦 Dependencies

- Flask - Web framework
- OpenCV - Video processing
- Ultralytics - YOLO object detection
- NumPy - Numerical operations

## 🏗️ Project Structure

```
yolo-final/
├── app.py                 # Flask web server
├── templates/
│   └── index.html        # Web interface
├── lanes.json            # Lane definitions
├── yolov8l.pt           # YOLO model
├── requirements_flask.txt # Flask dependencies
└── run_webapp.sh        # Quick start script
```

## 🎯 Lane Numbering (9-Lane Intersection)

```
        |   1   |   2   |
________|       |       |________
   3                        4
________                 ________
   6                        7
________|       |       |________
        |   8   |   9   |
```

## 💡 Tips

- Position your camera to capture the entire intersection
- Ensure good lighting for better YOLO detection
- Draw lanes carefully to avoid overlaps
- Test with recorded video first before live deployment

## 🚀 Next Steps

1. **Add Video Recording**: Capture and save traffic footage
2. **Database Integration**: Store traffic data over time
3. **Analytics Dashboard**: Show traffic patterns and statistics
4. **Multiple Camera Support**: Monitor multiple intersections
5. **Mobile App**: Create companion mobile app

## 📝 License

This project is for educational and research purposes.

---

**Made with ❤️ using YOLOv8, OpenCV, and Flask**
