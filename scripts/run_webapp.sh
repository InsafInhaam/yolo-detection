#!/bin/bash

echo "🚀 Starting Traffic Intersection Web App"
echo "========================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📥 Installing requirements..."
pip install -q -r requirements_flask.txt

# Run Flask app
echo "🌐 Starting Flask server..."
echo "📱 Open http://127.0.0.1:5000 in your browser"
echo ""
python app.py
