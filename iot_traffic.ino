#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <Wire.h>
#include <PCF8574.h>
#include <ArduinoJson.h>

// ====== WiFi Credentials ======
struct WiFiCredentials
{
    const char *ssid;
    const char *password;
};

// Add multiple WiFi networks - will connect to first available one
WiFiCredentials wifiNetworks[] = {
    {"Insaf-SLT-Fiber-2.4G", "InsafD@1234"},
    {"YourSecondWiFi", "password2"},
    {"YourThirdWiFi", "password3"}};
const int numNetworks = sizeof(wifiNetworks) / sizeof(wifiNetworks[0]);

// ====== Web Server ======
ESP8266WebServer server(80);

// ====== PCF8574 Boards ======
PCF8574 pcf1(0x20); // first board
PCF8574 pcf2(0x21); // second board

// ====== Modes ======
enum Mode
{
    AUTO,
    MANUAL
};
Mode currentMode = AUTO;

// ====== Lane Structure ======
struct Lane
{
    int redDevice, redPin;
    int yellowDevice, yellowPin;
    int greenDevice, greenPin;
};

// ====== Lanes ======
// IMPORTANT: Lane mapping must match Python intersection_final.py
// Python → Arduino:
//   lane_1 (UP direction)    → north
//   lane_2 (DOWN direction)  → south
//   lane_3 (RIGHT direction) → east
//   lane_4 (LEFT direction)  → west
//

// Hardware connections (PCF8574 pins):
Lane north = {1, 0, 1, 1, 1, 2}; // PCF1 P0,P1,P2
Lane east = {1, 3, 1, 4, 1, 5};  // PCF1 P3,P4,P5
Lane south = {1, 6, 1, 7, 2, 0}; // PCF1 P6,P7 + PCF2 P0
Lane west = {2, 1, 2, 2, 2, 3};  // PCF2 P1,P2,P3

// ====== Timing ======
unsigned long lastChange = 0;
int autoStep = 0;
const unsigned long greenTime = 5000;
const unsigned long yellowTime = 2000;

// ====== Function Helpers ======
void writeLED(int device, int pin, bool state)
{
    if (device == 1)
        pcf1.write(pin, state ? HIGH : LOW);
    else
        pcf2.write(pin, state ? HIGH : LOW);
}

void setLane(Lane lane, bool r, bool y, bool g)
{
    writeLED(lane.redDevice, lane.redPin, r);
    writeLED(lane.yellowDevice, lane.yellowPin, y);
    writeLED(lane.greenDevice, lane.greenPin, g);
}

void allStop()
{
    setLane(north, 1, 0, 0);
    setLane(east, 1, 0, 0);
    setLane(south, 1, 0, 0);
    setLane(west, 1, 0, 0);
}

// ====== Smart Light Control ======
void smartSetLight(String laneName, String color, int state)
{
    Lane *lane;
    if (laneName == "north")
        lane = &north;
    else if (laneName == "east")
        lane = &east;
    else if (laneName == "south")
        lane = &south;
    else if (laneName == "west")
        lane = &west;
    else
        return;

    // Safety logic
    if (color == "green" && state == 1)
    {
        setLane(*lane, 0, 0, 1);
        if (laneName == "north")
            setLane(south, 1, 0, 0);
        if (laneName == "south")
            setLane(north, 1, 0, 0);
        if (laneName == "east")
            setLane(west, 1, 0, 0);
        if (laneName == "west")
            setLane(east, 1, 0, 0);
    }
    else if (color == "red" && state == 1)
    {
        setLane(*lane, 1, 0, 0);
    }
    else if (color == "yellow" && state == 1)
    {
        setLane(*lane, 0, 1, 0);
    }
    else
    {
        // Turn off single LED
        if (color == "red")
            writeLED(lane->redDevice, lane->redPin, 0);
        if (color == "yellow")
            writeLED(lane->yellowDevice, lane->yellowPin, 0);
        if (color == "green")
            writeLED(lane->greenDevice, lane->greenPin, 0);
    }
}

// ====== Auto Mode ======
void autoTrafficControl()
{
    unsigned long now = millis();
    static unsigned long phaseTime = 0;
    static int phase = 0;

    if (now - phaseTime > (phase % 2 == 0 ? greenTime : yellowTime))
    {
        phase++;
        if (phase > 7)
            phase = 0;
        phaseTime = now;

        allStop();

        switch (phase)
        {
        case 0:
            setLane(north, 0, 0, 1);
            break;
        case 1:
            setLane(north, 0, 1, 0);
            break;
        case 2:
            setLane(east, 0, 0, 1);
            break;
        case 3:
            setLane(east, 0, 1, 0);
            break;
        case 4:
            setLane(south, 0, 0, 1);
            break;
        case 5:
            setLane(south, 0, 1, 0);
            break;
        case 6:
            setLane(west, 0, 0, 1);
            break;
        case 7:
            setLane(west, 0, 1, 0);
            break;
        }
    }
}

// ====== API Handlers ======
void handleControl()
{
    if (!server.hasArg("lane") || !server.hasArg("color") || !server.hasArg("state"))
    {
        server.send(400, "application/json", "{\"error\":\"Missing lane/color/state\"}");
        return;
    }

    String lane = server.arg("lane");
    String color = server.arg("color");
    int state = server.arg("state").toInt();

    currentMode = MANUAL;
    smartSetLight(lane, color, state);

    server.send(200, "application/json", "{\"status\":\"OK\",\"mode\":\"MANUAL\"}");
}

void handleMode()
{
    if (!server.hasArg("set"))
    {
        server.send(200, "application/json", currentMode == AUTO ? "{\"mode\":\"AUTO\"}" : "{\"mode\":\"MANUAL\"}");
        return;
    }

    String mode = server.arg("set");
    if (mode == "auto")
        currentMode = AUTO;
    else if (mode == "manual")
        currentMode = MANUAL;
    else
    {
        server.send(400, "application/json", "{\"error\":\"Invalid mode\"}");
        return;
    }

    server.send(200, "application/json", "{\"status\":\"Mode Updated\"}");
}

// ====== Setup ======
void setup()
{
    Serial.begin(115200);
    Wire.begin(D2, D1); // SDA, SCL
    pcf1.begin();
    pcf2.begin();

    // Try connecting to available WiFi networks
    bool connected = false;
    for (int i = 0; i < numNetworks && !connected; i++)
    {
        Serial.print("\nTrying: ");
        Serial.println(wifiNetworks[i].ssid);
        WiFi.begin(wifiNetworks[i].ssid, wifiNetworks[i].password);

        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 20)
        {
            delay(500);
            Serial.print(".");
            attempts++;
        }

        if (WiFi.status() == WL_CONNECTED)
        {
            connected = true;
            Serial.println("\n✅ Connected to: " + String(wifiNetworks[i].ssid));
            Serial.println("IP: " + WiFi.localIP().toString());
        }
        else
        {
            Serial.println("\n❌ Failed");
        }
    }

    if (!connected)
    {
        Serial.println("\n❌ Could not connect to any WiFi network!");
        Serial.println("Device will restart in 10 seconds...");
        delay(10000);
        ESP.restart();
    }

    allStop();

    server.on("/control", handleControl);
    server.on("/mode", handleMode);
    server.begin();
    Serial.println("\n✅ Traffic Light System Ready!");
    Serial.println("Access at: http://" + WiFi.localIP().toString());
}

// ====== Loop ======
void loop()
{
    server.handleClient();
    if (currentMode == AUTO)
        autoTrafficControl();
}
