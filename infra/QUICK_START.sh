#!/bin/bash

# Quick Start Script for AI-SMM Agency
# Этот скрипт запускает все сервисы и проверяет их статус

set -e

echo "🚀 AI-SMM Agency - Quick Start"
echo "================================"
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found!"
    echo "Please run this script from the infra/ directory"
    exit 1
fi

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Copying .env.example to .env..."
    cp ../.env.example ../.env
    echo "✅ Please edit .env file with your API keys before proceeding"
    echo ""
fi

# Build and start services
echo "📦 Building and starting services..."
echo ""
docker compose up -d --build

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

echo ""
echo "📊 Services Status:"
echo "-------------------"
docker compose ps

echo ""
echo "🔍 Health Check:"
echo "----------------"

# Wait a bit more for API to be fully ready
sleep 5

# Check API health
echo -n "API Health: "
curl -s http://localhost:8000/health | python3 -m json.tool || echo "❌ Not ready yet"

echo ""
echo ""
echo "✅ All services started!"
echo ""
echo "📝 Useful commands:"
echo "  - View logs:           docker compose logs -f"
echo "  - View API logs:       docker compose logs -f api"
echo "  - Stop services:       docker compose down"
echo "  - Restart service:     docker compose restart <service>"
echo ""
echo "🌐 Access points:"
echo "  - API Documentation:   http://localhost:8000/docs"
echo "  - API Health Check:    http://localhost:8000/health"
echo "  - Qdrant Dashboard:    http://localhost:6333/dashboard"
echo ""
echo "📖 See DEPLOYMENT.md for detailed instructions"
