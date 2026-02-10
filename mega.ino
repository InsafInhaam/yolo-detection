// =========================
// ARDUINO MEGA TRAFFIC LIGHT
// =========================

// ====== Modes ======
enum Mode
{
    AUTO,
    MANUAL
};
Mode currentMode = MANUAL;

// ====== Lane Structure ======
struct Lane
{
    uint8_t red;
    uint8_t yellow;
    uint8_t green;
};

// ====== Lane Pin Mapping ======
Lane north = {8, 9, 10};
Lane east = {11, 12, 13};
Lane south = {14, 15, 16};
Lane west = {17, 18, 19};

// ====== Timing ======
const unsigned long GREEN_TIME = 5000;
const unsigned long YELLOW_TIME = 2000;

// ====== Helpers ======
void setLane(const Lane &lane, bool r, bool y, bool g)
{
    digitalWrite(lane.red, r ? HIGH : LOW);
    digitalWrite(lane.yellow, y ? HIGH : LOW);
    digitalWrite(lane.green, g ? HIGH : LOW);
}

void allStop()
{
    setLane(north, 1, 0, 0);
    setLane(east, 1, 0, 0);
    setLane(south, 1, 0, 0);
    setLane(west, 1, 0, 0);
}

// ====== Smart Manual Control ======
void smartSetLight(const String &laneName, const String &color, bool state)
{
    Lane *lane = nullptr;

    if (laneName == "north")
    {
        lane = &north;
        Serial.println("-> Lane NORTH");
    }
    else if (laneName == "east")
    {
        lane = &east;
        Serial.println("-> Lane EAST");
    }
    else if (laneName == "south")
    {
        lane = &south;
        Serial.println("-> Lane SOUTH");
    }
    else if (laneName == "west")
    {
        lane = &west;
        Serial.println("-> Lane WEST");
    }
    else
    {
        Serial.print("ERROR: Unknown lane: ");
        Serial.println(laneName);
        return;
    }

    if (color == "green" && state)
    {
        allStop();
        setLane(*lane, 0, 0, 1);
        Serial.println("-> LED: GREEN");
    }
    else if (color == "yellow" && state)
    {
        allStop();
        setLane(*lane, 0, 1, 0);
        Serial.println("-> LED: YELLOW");
    }
    else if (color == "red" && state)
    {
        allStop();
        setLane(*lane, 1, 0, 0);
        Serial.println("-> LED: RED");
    }
    else
    {
        Serial.print("Warning: color='");
        Serial.print(color);
        Serial.print("' state=");
        Serial.println(state);
    }
}

// ====== Auto Mode ======
void autoTrafficControl()
{
    static unsigned long lastChange = 0;
    static int phase = 0;
    unsigned long now = millis();

    unsigned long interval = (phase % 2 == 0) ? GREEN_TIME : YELLOW_TIME;

    if (now - lastChange >= interval)
    {
        lastChange = now;
        phase = (phase + 1) % 8;

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

// ====== Setup ======
void setup()
{
    Serial.begin(115200);

    for (int pin = 8; pin <= 19; pin++)
    {
        pinMode(pin, OUTPUT);
        digitalWrite(pin, LOW);
    }

    allStop();
    Serial.println("✅ Arduino Mega Traffic Light Ready");
}

// ====== Serial Command Handler ======
void handleSerialCommand()
{
    if (Serial.available() > 0)
    {
        String command = Serial.readStringUntil('\n');
        command.trim();

        // Remove any carriage return
        if (command.endsWith("\r"))
        {
            command = command.substring(0, command.length() - 1);
        }

        if (command.length() == 0)
            return;

        // DEBUG: Show raw command received
        Serial.print("RX: [");
        Serial.print(command);
        Serial.println("]");

        // Parse format: "lane,color,state"
        // Example: "north,green,1"
        int commaIndex1 = command.indexOf(',');
        int commaIndex2 = command.lastIndexOf(',');

        if (commaIndex1 == -1 || commaIndex2 == -1 || commaIndex1 >= commaIndex2)
        {
            Serial.println("ERROR: Invalid format");
            return;
        }

        String lane = command.substring(0, commaIndex1);
        String color = command.substring(commaIndex1 + 1, commaIndex2);
        String stateStr = command.substring(commaIndex2 + 1);
        int state = stateStr.toInt();

        // DEBUG: Show parsed values
        Serial.print("PARSED: Lane=");
        Serial.print(lane);
        Serial.print(" Color=");
        Serial.print(color);
        Serial.print(" State=");
        Serial.println(state);

        smartSetLight(lane, color, state);
        Serial.println("OK");
    }
}

// ====== Loop ======
void loop()
{
    // Handle incoming serial commands
    handleSerialCommand();

    if (currentMode == AUTO)
    {
        autoTrafficControl();
    }
}
