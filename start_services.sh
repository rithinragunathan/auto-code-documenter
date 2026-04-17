#!/bin/bash
# Startup script for AutoDocx with ChromaDB client-server architecture

echo "🚀 Starting AutoDocx Services (with ChromaDB Server)..."
echo ""

# Kill any existing services
echo "Stopping existing services..."
pkill -9 -f "chromadb_server|api_server|java.*Spring" 2>/dev/null
sleep 2

# Set environment variables for ChromaDB client
export CHROMA_SERVER_HOST=localhost
export CHROMA_SERVER_PORT=8000

# Start ChromaDB Server
echo "1. Starting ChromaDB Server on port 8000..."
cd /home/shadowshell/projects/AutoDocx/python-service
nohup python3 -u chromadb_server.py > /tmp/chromadb.log 2>&1 &
CHROMADB_PID=$!
echo "   ChromaDB Server PID: $CHROMADB_PID"
sleep 5

# Check ChromaDB
if timeout 5 python3 -c "import chromadb; client = chromadb.HttpClient(host='localhost', port=8000); client._client.heartbeat()" 2>/dev/null; then
    echo "   ✅ ChromaDB Server is UP"
else
    echo "   ❌ ChromaDB Server failed to start"
    echo "   Log:"
    tail -10 /tmp/chromadb.log
    pkill -9 -f chromadb_server
    exit 1
fi

# Start Python Flask service
echo ""
echo "2. Starting Python Flask service on port 5000..."
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
    echo "   Log:"
    tail -10 /tmp/flask.log
    exit 1
fi

# Start Spring Boot
echo ""
echo "3. Starting Spring Boot on port 8080..."
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
    tail -10 /tmp/springboot.log
    exit 1
fi

echo ""
echo "✨ All services started successfully!"
echo ""
echo "Services running:"
echo "  - ChromaDB Server: http://localhost:8000"
echo "  - Python Flask: http://localhost:5000"
echo "  - Spring Boot: http://localhost:8080"
echo ""
echo "Open Firefox and navigate to:"
echo "  file:///home/shadowshell/projects/AutoDocx/frontend/index.html"
echo ""
echo "Logs:"
echo "  - ChromaDB: tail -f /tmp/chromadb.log"
echo "  - Flask: tail -f /tmp/flask.log"
echo "  - Spring Boot: tail -f /tmp/springboot.log"
echo ""
echo "To stop all services: pkill -9 -f 'chromadb_server|api_server|java.*Spring'"
