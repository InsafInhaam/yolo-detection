#!/bin/bash

# =========================
# ARDUINO SERIAL TEST SCRIPT (macOS)
# =========================

SERIAL_PORT="/dev/cu.usbmodem1301"
BAUD_RATE=115200

echo "🚦 Arduino Traffic Light Serial Tester"
echo "======================================="
echo ""
echo "Available commands:"
echo "  1) Green - North"
echo "  2) Yellow - North"
echo "  3) Red - North"
echo "  4) Green - South"
echo "  5) Yellow - South"
echo "  6) Red - South"
echo "  7) Green - East"
echo "  8) Yellow - East"
echo "  9) Red - East"
echo "  10) Green - West"
echo "  11) Yellow - West"
echo "  12) Red - West"
echo "  c) Custom command"
echo "  s) Start serial monitor (use screen)"
echo "  q) Quit"
echo ""

# Function to send command using stdbuf
send_command() {
    local cmd="$1"
    echo "📡 Sending: $cmd"
    
    # Use printf with proper line ending
    printf "%s\r\n" "$cmd" > "$SERIAL_PORT" 2>/dev/null
    
    # Give Arduino time to respond
    sleep 0.3
    
    # Try to read response (non-blocking)
    if [ -r "$SERIAL_PORT" ]; then
        timeout 0.5 cat "$SERIAL_PORT" 2>/dev/null | head -10 | while IFS= read -r line; do
            if [ ! -z "$line" ]; then
                echo "   ← $line"
            fi
        done
    fi
}

while true; do
    read -p "Enter command (1-12, c, s, or q): " choice
    
    case $choice in
        1) send_command "north,green,1" ;;
        2) send_command "north,yellow,1" ;;
        3) send_command "north,red,1" ;;
        4) send_command "south,green,1" ;;
        5) send_command "south,yellow,1" ;;
        6) send_command "south,red,1" ;;
        7) send_command "east,green,1" ;;
        8) send_command "east,yellow,1" ;;
        9) send_command "east,red,1" ;;
        10) send_command "west,green,1" ;;
        11) send_command "west,yellow,1" ;;
        12) send_command "west,red,1" ;;
        c)
            read -p "Enter custom command (e.g., north,green,1): " cmd
            if [ ! -z "$cmd" ]; then
                send_command "$cmd"
            fi
            ;;
        s)
            echo "Starting serial monitor..."
            echo "Command: screen $SERIAL_PORT $BAUD_RATE"
            echo "To exit: Press Ctrl+A then Q"
            screen "$SERIAL_PORT" $BAUD_RATE
            ;;
        q)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo "❌ Invalid option. Try again."
            ;;
    esac
    
    echo ""
done

