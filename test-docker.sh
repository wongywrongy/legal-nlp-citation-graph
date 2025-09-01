#!/bin/bash

echo "Testing Docker setup for Legal Citation Graph..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✅ Docker is running"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not available"
    exit 1
fi

echo "✅ docker-compose is available"

# Test building images
echo "Building Docker images..."
docker-compose build --no-cache

if [ $? -eq 0 ]; then
    echo "✅ Images built successfully"
else
    echo "❌ Failed to build images"
    exit 1
fi

# Test starting services
echo "Starting services..."
docker-compose up -d

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Check service status
echo "Service status:"
docker-compose ps

# Test health endpoint
echo "Testing health endpoint..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend health check passed"
else
    echo "❌ Backend health check failed"
fi

# Test frontend
echo "Testing frontend..."
if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is accessible"
else
    echo "❌ Frontend is not accessible"
fi

echo ""
echo "🎉 Docker setup test completed!"
echo ""
echo "Services are running at:"
echo "  Frontend: http://localhost:3000"
echo "  Backend: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "To stop services: docker-compose down"
echo "To view logs: docker-compose logs -f"

