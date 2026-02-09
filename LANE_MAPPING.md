# Lane Mapping Reference

## Python to Arduino Lane Mapping

| Python Lane | Direction | Arduino Lane | PCF8574 Pins                     |
| ----------- | --------- | ------------ | -------------------------------- |
| lane_1      | UP        | north        | PCF1: P0(R), P1(Y), P2(G)        |
| lane_2      | DOWN      | south        | PCF1: P6(R), P7(Y) + PCF2: P0(G) |
| lane_3      | RIGHT     | east         | PCF1: P3(R), P4(Y), P5(G)        |
| lane_4      | LEFT      | west         | PCF2: P1(R), P2(Y), P3(G)        |

## Physical Intersection Layout

```
           lane_1 (north)
               ↑
               |
               |
lane_4 (west) ← + → lane_3 (east)
               |
               |
               ↓
           lane_2 (south)
```

## Configuration Steps

### 1. Arduino Setup (iot_traffic.ino)

**Update WiFi credentials (lines 8-12):**

```cpp
WiFiCredentials wifiNetworks[] = {
    {"Your-WiFi-SSID", "password"},
    {"Backup-WiFi", "password2"},
    {"Third-WiFi", "password3"}
};
```

**Upload to ESP8266 and note the IP address from Serial Monitor**

### 2. Python Setup (intersection_final.py)

**Update Arduino IP (line 16):**

```python
ARDUINO_IP = "http://192.168.1.XXX"  # Use your ESP8266 IP
```

### 3. Draw Lanes (draw_and_detect.py)

Run `python draw_and_detect.py` to define lanes:

- **lane_1**: Draw polygon for UP/north traffic
- **lane_2**: Draw polygon for DOWN/south traffic
- **lane_3**: Draw polygon for RIGHT/east traffic
- **lane_4**: Draw polygon for LEFT/west traffic

Save lanes.json when all 4 lanes are drawn.

### 4. Run Detection

```bash
python intersection_final.py
```

The system will:

- Load lanes from lanes.json
- Connect to Arduino
- Set Arduino to MANUAL mode
- Control traffic lights based on vehicle detection

## Troubleshooting

**Arduino not responding:**

- Check IP address matches
- Verify Arduino is on same network
- Check Serial Monitor for errors
- Test manually: `http://ARDUINO_IP/mode`

**Wrong lights triggering:**

- Verify physical wiring matches PCF pin assignments
- Check lane polygons are drawn correctly
- Ensure lane_1 is UP, lane_2 is DOWN, etc.

**Vehicles not detected:**

- Ensure lanes.json exists
- Verify YOLO model (yolov8l.pt) is present
- Check camera feed is working
- Adjust VEHICLE_CLASSES if needed
