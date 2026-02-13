#!/usr/bin/env python3
"""
Simple Arduino Serial Monitor - Test Traffic Lights Manually
"""
import serial
import time
import sys

SERIAL_PORT = "/dev/cu.usbmodem1301"
BAUD_RATE = 115200

# Quick commands
COMMANDS = {
    "1": ("north,green,1", "🟢 Green - North"),
    "2": ("north,yellow,1", "🟡 Yellow - North"),
    "3": ("north,red,1", "🔴 Red - North"),
    "4": ("south,green,1", "🟢 Green - South"),
    "5": ("south,yellow,1", "🟡 Yellow - South"),
    "6": ("south,red,1", "🔴 Red - South"),
    "7": ("east,green,1", "🟢 Green - East"),
    "8": ("east,yellow,1", "🟡 Yellow - East"),
    "9": ("east,red,1", "🔴 Red - East"),
    "10": ("west,green,1", "🟢 Green - West"),
    "11": ("west,yellow,1", "🟡 Yellow - West"),
    "12": ("west,red,1", "🔴 Red - West"),
}


def print_menu():
    print("\n" + "="*50)
    print("🚦 ARDUINO TRAFFIC LIGHT TESTER")
    print("="*50)
    for key, (cmd, label) in COMMANDS.items():
        print(f"  {key:2}. {label}")
    print(f"  {'s'.rjust(2)}. Start Serial Monitor")
    print(f"  {'c'.rjust(2)}. Custom Command")
    print(f"  {'q'.rjust(2)}. Quit")
    print("="*50)


def send_command(ser, command):
    """Send command to Arduino and read response"""
    try:
        # Clear buffers
        ser.flushInput()
        ser.flushOutput()

        # Send command with \r\n
        cmd_bytes = f"{command}\r\n".encode()
        print(f"\n📡 Sending: {command}")
        ser.write(cmd_bytes)
        ser.flush()

        # Read response
        time.sleep(0.2)
        responses = []
        for i in range(20):
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    responses.append(line)
                    print(f"   ← {line}")
            time.sleep(0.05)

        if not responses:
            print("   ⚠️  No response from Arduino")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def serial_monitor(ser):
    """Interactive serial monitor"""
    print("\n📺 Serial Monitor (Ctrl+C to exit)")
    print("Waiting for data from Arduino...\n")
    try:
        while True:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(line)
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\n✅ Exited serial monitor")


def main():
    # Connect to Arduino
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to {SERIAL_PORT}")

        # Read startup message
        time.sleep(0.5)
        if ser.in_waiting:
            startup = ser.readline().decode('utf-8', errors='ignore').strip()
            print(f"📨 Arduino: {startup}\n")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        print(f"   Make sure Arduino is connected to {SERIAL_PORT}")
        sys.exit(1)

    # Main loop
    while True:
        print_menu()
        choice = input("Select option: ").strip().lower()

        if choice == "q":
            print("👋 Goodbye!")
            ser.close()
            break

        elif choice == "c":
            cmd = input("Enter command (e.g., north,green,1): ").strip()
            if cmd:
                send_command(ser, cmd)

        elif choice == "s":
            serial_monitor(ser)

        elif choice in COMMANDS:
            cmd, label = COMMANDS[choice]
            print(f"\n{label}")
            send_command(ser, cmd)

        else:
            print("❌ Invalid option")


if __name__ == "__main__":
    main()
