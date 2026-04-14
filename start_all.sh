#!/bin/bash
# AutoDocx: Start All Services Script
# This script starts all three services in parallel

echo "🚀 AutoDocx Full Stack Launcher"
echo "================================"
echo ""
echo "This script will start:"
echo "  1. Python LLM Service (Port 5000)"
echo "  2. Spring Boot Backend (Port 8080)"
echo "  3. Firefox Browser UI"
echo ""
echo "Prerequisites:"
echo "  ✓ Python 3.8+ installed"
echo "  ✓ Java 17+ installed"
echo "  ✓ Firefox installed"
echo "  ✓ GOOGLE_API_KEY set in python-service/.env"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if running from correct directory
if [ ! -d "$SCRIPT_DIR/server" ] || [ ! -d "$SCRIPT_DIR/python-service" ] || [ ! -d "$SCRIPT_DIR/frontend" ]; then
    echo -e "${RED}❌ Error: Could not find required directories${NC}"
    echo "Make sure you're running this from the AutoDocx project root"
    exit 1
fi

# Check if .env file exists
if [ ! -f "$SCRIPT_DIR/python-service/.env" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found in python-service${NC}"
    echo "Please create python-service/.env with:"
    echo "  GOOGLE_API_KEY=your-api-key-here"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✓ All checks passed${NC}"
echo ""
echo "Starting services..."
echo ""

# Terminal 1: Python Service
echo -e "${YELLOW}1. Starting Python LLM Service...${NC}"
cd "$SCRIPT_DIR/python-service"
python3 api_server.py &
PYTHON_PID=$!
echo -e "${GREEN}   ✓ Started (PID: $PYTHON_PID)${NC}"
sleep 2

# Terminal 2: Spring Boot
echo -e "${YELLOW}2. Starting Spring Boot Backend...${NC}"
cd "$SCRIPT_DIR/server"
./mvnw spring-boot:run &
SPRING_PID=$!
echo -e "${GREEN}   ✓ Started (PID: $SPRING_PID)${NC}"
sleep 3

# Terminal 3: Firefox
echo -e "${YELLOW}3. Opening Firefox...${NC}"
cd "$SCRIPT_DIR/frontend"
firefox index.html &
FIREFOX_PID=$!
echo -e "${GREEN}   ✓ Started (PID: $FIREFOX_PID)${NC}"

echo ""
echo "================================"
echo -e "${GREEN}✓ All services started${NC}"
echo "================================"
echo ""
echo "Service URLs:"
echo "  • Python LLM:  http://localhost:5000"
echo "  • Spring Boot: http://localhost:8080"
echo "  • Firefox UI:  file://$(pwd)/index.html"
echo ""
echo "To stop all services, press Ctrl+C"
echo ""

# Wait for all background processes
wait
