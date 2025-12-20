#!/bin/bash

PAPERLESS_URL="https://your-paperless-domain.com"
# Load token from environment file
if [ -f .env.paperless ]; then
    source .env.paperless
else
    echo "Error: .env.paperless not found"
    echo "Create it from .env.paperless.example"
    exit 1
fi

echo "🚀 Creating Select-Type Custom Fields"
echo "======================================"
echo ""

# Function to generate random ID for select options
generate_id() {
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 16 | head -n 1
}

# Field 1: Obligation Type
echo "Creating: Obligation Type"
curl -s -X POST "${PAPERLESS_URL}/api/custom_fields/" \
  -H "Authorization: Token ${PAPERLESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Obligation Type",
    "data_type": "select",
    "extra_data": {
      "select_options": [
        {"id": "'$(generate_id)'", "label": "hard_obligation"},
        {"id": "'$(generate_id)'", "label": "soft_tracking"},
        {"id": "'$(generate_id)'", "label": "informational"},
        {"id": "'$(generate_id)'", "label": "none"}
      ]
    }
  }' | grep -o '"id":[0-9]*' | head -1
echo ""

# Field 2: Risk Level
echo "Creating: Risk Level"
curl -s -X POST "${PAPERLESS_URL}/api/custom_fields/" \
  -H "Authorization: Token ${PAPERLESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Risk Level",
    "data_type": "select",
    "extra_data": {
      "select_options": [
        {"id": "'$(generate_id)'", "label": "critical"},
        {"id": "'$(generate_id)'", "label": "high"},
        {"id": "'$(generate_id)'", "label": "medium"},
        {"id": "'$(generate_id)'", "label": "low"}
      ]
    }
  }' | grep -o '"id":[0-9]*' | head -1
echo ""

# Field 3: Correspondent Category
echo "Creating: Correspondent Category"
curl -s -X POST "${PAPERLESS_URL}/api/custom_fields/" \
  -H "Authorization: Token ${PAPERLESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Correspondent Category",
    "data_type": "select",
    "extra_data": {
      "select_options": [
        {"id": "'$(generate_id)'", "label": "government"},
        {"id": "'$(generate_id)'", "label": "insurance"},
        {"id": "'$(generate_id)'", "label": "financial"},
        {"id": "'$(generate_id)'", "label": "health"},
        {"id": "'$(generate_id)'", "label": "commercial"},
        {"id": "'$(generate_id)'", "label": "technical"}
      ]
    }
  }' | grep -o '"id":[0-9]*' | head -1
echo ""

# Field 4: Monitoring Status
echo "Creating: Monitoring Status"
curl -s -X POST "${PAPERLESS_URL}/api/custom_fields/" \
  -H "Authorization: Token ${PAPERLESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Monitoring Status",
    "data_type": "select",
    "extra_data": {
      "select_options": [
        {"id": "'$(generate_id)'", "label": "active"},
        {"id": "'$(generate_id)'", "label": "pending"},
        {"id": "'$(generate_id)'", "label": "completed"},
        {"id": "'$(generate_id)'", "label": "archived"}
      ]
    }
  }' | grep -o '"id":[0-9]*' | head -1
echo ""

echo "======================================"
echo "✅ Select fields creation complete!"
