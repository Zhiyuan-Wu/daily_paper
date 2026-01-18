#!/bin/bash
# Daily Paper Backend Server Startup Script

echo "Starting Daily Paper Backend Server..."
echo "API will be available at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"
echo "Frontend at: http://localhost:8000/static/index.html"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Change to project directory
cd "$(dirname "$0")"

# Start the server
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
