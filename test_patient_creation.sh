#!/bin/bash
# Test script to create a patient and verify it can be retrieved
# Usage: ./test_patient_creation.sh <DEVICE_ID>

DEVICE_ID=${1:-"test-device-$(date +%s)"}
API_URL="http://127.0.0.1:8000/api/v1/patients"

echo "Testing patient creation and retrieval..."
echo "Device ID: $DEVICE_ID"
echo ""

# Create patient
echo "1. Creating patient..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "X-Device-ID: $DEVICE_ID" \
  -d '{
    "name": "Test Patient",
    "email": "test@example.com",
    "date_of_birth": "1980-01-01",
    "has_ckd_esrd": true,
    "last_gfr": 45,
    "has_referral": true
  }')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Patient created successfully"
  PATIENT_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
  echo "   Patient ID: $PATIENT_ID"
else
  echo "❌ Failed to create patient (HTTP $HTTP_CODE)"
  echo "$BODY"
  exit 1
fi

echo ""
echo "2. Retrieving patient..."
GET_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$API_URL" \
  -H "X-Device-ID: $DEVICE_ID")

GET_HTTP_CODE=$(echo "$GET_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
GET_BODY=$(echo "$GET_RESPONSE" | sed '/HTTP_CODE/d')

if [ "$GET_HTTP_CODE" = "200" ]; then
  echo "✅ Patient retrieved successfully"
  echo "$GET_BODY" | python3 -m json.tool 2>/dev/null || echo "$GET_BODY"
else
  echo "❌ Failed to retrieve patient (HTTP $GET_HTTP_CODE)"
  echo "$GET_BODY"
  exit 1
fi

echo ""
echo "✅ Test passed! Patient creation and retrieval work correctly."
