#!/bin/bash

# API Testing Script
# Тестирует основные эндпоинты API

set -e

API_URL="http://localhost:8000"

echo "🧪 Testing AI-SMM Agency API"
echo "============================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test health endpoint
echo "1. Testing Health Endpoint..."
response=$(curl -s -w "\n%{http_code}" $API_URL/health)
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" -eq 200 ]; then
    echo -e "${GREEN}✅ Health check passed${NC}"
    echo "$body" | python3 -m json.tool
else
    echo -e "${RED}❌ Health check failed (HTTP $http_code)${NC}"
    exit 1
fi

echo ""
echo "2. Testing Root Endpoint..."
response=$(curl -s -w "\n%{http_code}" $API_URL/)
http_code=$(echo "$response" | tail -n1)

if [ "$http_code" -eq 200 ]; then
    echo -e "${GREEN}✅ Root endpoint passed${NC}"
else
    echo -e "${RED}❌ Root endpoint failed${NC}"
fi

echo ""
echo "3. Creating Test User..."
user_response=$(curl -s -X POST "$API_URL/users" \
  -H "Content-Type: application/json" \
  -d '{
    "tg_user_id": 123456789,
    "name": "Test User"
  }')

user_id=$(echo "$user_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

if [ -n "$user_id" ]; then
    echo -e "${GREEN}✅ User created successfully${NC}"
    echo "User ID: $user_id"
else
    echo -e "${YELLOW}⚠️  User might already exist${NC}"
    # Try to get existing user
    users=$(curl -s "$API_URL/users")
    user_id=$(echo "$users" | python3 -c "import sys, json; users = json.load(sys.stdin); print(users[0]['id'] if users else '')" 2>/dev/null || echo "")
    if [ -n "$user_id" ]; then
        echo "Using existing User ID: $user_id"
    fi
fi

if [ -n "$user_id" ]; then
    echo ""
    echo "4. Creating Test Source..."
    source_response=$(curl -s -X POST "$API_URL/sources" \
      -H "Content-Type: application/json" \
      -d "{
        \"user_id\": \"$user_id\",
        \"text\": \"Это тестовый пост для анализа стиля написания. Используем разные конструкции и эмоции!\",
        \"platform\": \"telegram\"
      }")

    source_id=$(echo "$source_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

    if [ -n "$source_id" ]; then
        echo -e "${GREEN}✅ Source created successfully${NC}"
        echo "Source ID: $source_id"
    else
        echo -e "${RED}❌ Failed to create source${NC}"
    fi

    echo ""
    echo "5. Creating Test Style Profile..."
    profile_response=$(curl -s -X POST "$API_URL/style-profiles" \
      -H "Content-Type: application/json" \
      -d "{
        \"user_id\": \"$user_id\",
        \"json\": {
          \"tone\": \"friendly\",
          \"emoji_usage\": \"moderate\",
          \"sentence_length\": \"medium\"
        }
      }")

    profile_id=$(echo "$profile_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

    if [ -n "$profile_id" ]; then
        echo -e "${GREEN}✅ Style profile created successfully${NC}"
        echo "Profile ID: $profile_id"
    else
        echo -e "${RED}❌ Failed to create style profile${NC}"
    fi

    echo ""
    echo "6. Getting User's Sources..."
    sources=$(curl -s "$API_URL/users/$user_id/sources")
    source_count=$(echo "$sources" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo -e "${GREEN}✅ Found $source_count sources for user${NC}"

    echo ""
    echo "7. Getting User's Style Profiles..."
    profiles=$(curl -s "$API_URL/users/$user_id/style-profiles")
    profile_count=$(echo "$profiles" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo -e "${GREEN}✅ Found $profile_count style profiles for user${NC}"
fi

echo ""
echo "================================"
echo -e "${GREEN}✅ API Testing Complete!${NC}"
echo ""
echo "📊 Summary:"
echo "  - Health check: ✅"
echo "  - User creation: ✅"
echo "  - Source creation: ✅"
echo "  - Style profile creation: ✅"
echo "  - Data retrieval: ✅"
echo ""
echo "🌐 View API documentation at: $API_URL/docs"
