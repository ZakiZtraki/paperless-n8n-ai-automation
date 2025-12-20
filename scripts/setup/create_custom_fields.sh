#!/bin/bash

# Paperless-ngx Enhanced Custom Fields Creation Script
# Creates 6 custom fields for AI-powered obligation tracking

PAPERLESS_URL="https://your-paperless-domain.com"
# Load token from environment file
if [ -f .env.paperless ]; then
    source .env.paperless
else
    echo "Error: .env.paperless not found"
    echo "Create it from .env.paperless.example"
    exit 1
fi

echo "🚀 Creating Enhanced Custom Fields for Paperless-ngx"
echo "====================================================="
echo ""

# Clear previous field IDs file
> field_ids.txt

# Function to create field and capture ID
create_field() {
    local name="$1"
    local data_type="$2"
    local extra_data="$3"

    echo "Creating field: $name (type: $data_type)"

    # Build JSON payload
    if [ -z "$extra_data" ]; then
        payload="{\"name\": \"$name\", \"data_type\": \"$data_type\"}"
    else
        payload="{\"name\": \"$name\", \"data_type\": \"$data_type\", \"extra_data\": $extra_data}"
    fi

    # Make API call
    response=$(curl -s -X POST "${PAPERLESS_URL}/api/custom_fields/" \
      -H "Authorization: Token ${PAPERLESS_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "$payload")

    # Parse ID using Python
    id=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('id', 'error'))" 2>/dev/null)

    if [ "$id" != "error" ] && [ -n "$id" ]; then
        echo "✅ Created '$name' with ID: $id"
        echo "$name|$id" >> field_ids.txt
    else
        echo "❌ Failed to create '$name'"
        echo "Response: $response"
    fi
    echo ""
}

# Create all 6 enhanced custom fields

echo "Creating field 1/6: Obligation Type"
create_field "Obligation Type" "select" '{"select_options": ["hard_obligation", "soft_tracking", "informational", "none"]}'

echo "Creating field 2/6: Risk Level"
create_field "Risk Level" "select" '{"select_options": ["critical", "high", "medium", "low"]}'

echo "Creating field 3/6: Storage Path"
create_field "Storage Path" "string" ''

echo "Creating field 4/6: Correspondent Category"
create_field "Correspondent Category" "select" '{"select_options": ["government", "insurance", "financial", "health", "commercial", "technical"]}'

echo "Creating field 5/6: Monitoring Status"
create_field "Monitoring Status" "select" '{"select_options": ["active", "pending", "completed", "archived"]}'

echo "Creating field 6/6: SLA Deadline"
create_field "SLA Deadline" "date" ''

echo "====================================================="
echo "📋 Field IDs created (saved to field_ids.txt):"
echo ""
cat field_ids.txt

echo ""
echo "====================================================="
echo "📝 For n8n workflow configuration, use these IDs:"
echo ""
echo "const FIELD_IDS = {"

while IFS='|' read -r name id; do
    field_name=$(echo "$name" | sed 's/ /_/g' | tr '[:lower:]' '[:upper:]')
    echo "  $field_name: $id,"
done < field_ids.txt

echo "};"

echo ""
echo "====================================================="
echo "✅ Custom field creation complete!"
echo ""
echo "Next steps:"
echo "1. Copy the field IDs above into your n8n workflow"
echo "2. Update TODO_TRACKER.md with the field IDs"
echo "3. Proceed to TODO 3: Backup n8n workflow"
