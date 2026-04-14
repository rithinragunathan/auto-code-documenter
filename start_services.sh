#!/bin/bash
# Simple startup script for AutoDocx services

echo "🚀 Starting AutoDocx Services..."
echo ""

# Kill any existing services
echo "Stopping existing services..."
pkill -9 -f "api_server\|java.*Spring" 2>/dev/null
sleep 1

# Start Python Flask service
echo "1. Starting Python Flask service on port 5000..."
cd /home/shadowshell/projects/AutoDocx/python-service
nohup python3 -u api_server.py > /tmp/flask.log 2>&1 &
FLASK_PID=$!
echo "   Flask PID: $FLASK_PID"
sleep 3

# Check Flask
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo "   ✅ Flask service is UP"
else
    echo "   ❌ Flask service failed to start"
    exit 1
fi

# Start Spring Boot
echo ""
echo "2. Starting Spring Boot on port 8080..."
cd /home/shadowshell/projects/AutoDocx/server
nohup ./mvnw spring-boot:run -DskipTests > /tmp/springboot.log 2>&1 &
SB_PID=$!
echo "   Spring Boot PID: $SB_PID"
sleep 10

# Check Spring Boot
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "   ✅ Spring Boot is UP"
else
    echo "   ❌ Spring Boot failed to start"
    tail -20 /tmp/springboot.log
    exit 1
fi

echo ""
echo "✨ All services started successfully!"
echo ""
echo "Services running:"
echo "  - Python Flask: http://localhost:5000"
echo "  - Spring Boot: http://localhost:8080"
echo ""
echo "Open Firefox and navigate to:"
echo "  file:///home/shadowshell/projects/AutoDocx/frontend/index.html"
echo ""
echo "To stop services: pkill -f 'api_server\|java.*Spring'"
