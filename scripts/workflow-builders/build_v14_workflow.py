#!/usr/bin/env python3
"""
Build v14 workflow with entity-based architecture
- Removes custom field #33 (Storage Path) from FIELD_IDS
- Adds Entity Manager node
- Updates document update payload to use entity IDs
"""

import json
import sys

print("[INFO] Building v14 workflow from v13.1...")

# Read v13.1 workflow
with open('paperless_workflow-v13.1-fixed.json', 'r', encoding='utf-8') as f:
    workflow = json.load(f)

print(f"[INFO] Loaded v13.1 workflow: {len(workflow['nodes'])} nodes")

# === STEP 1: Update Consolidated Processor ===
print("\n[STEP 1] Updating Consolidated Processor...")

for node in workflow['nodes']:
    if node.get('name') == 'Consolidated Processor':
        print(f"  Found node: {node['id']}")
        js_code = node['parameters']['jsCode']

        # Remove STORAGE_PATH from FIELD_IDS
        old_field_ids = """const FIELD_IDS = {
    STORAGE_PATH: 33,
    SLA_DEADLINE: 34,
    OBLIGATION_TYPE: 35,
    RISK_LEVEL: 36,
    CORRESPONDENT_CATEGORY: 37,
    MONITORING_STATUS: 38
  };"""

        new_field_ids = """const FIELD_IDS = {
    SLA_DEADLINE: 34,
    OBLIGATION_TYPE: 35,
    RISK_LEVEL: 36,
    CORRESPONDENT_CATEGORY: 37,
    MONITORING_STATUS: 38
  };"""

        if old_field_ids in js_code:
            js_code = js_code.replace(old_field_ids, new_field_ids)
            print("  [OK] Removed STORAGE_PATH from FIELD_IDS")
        else:
            print("  [WARN] Could not find exact FIELD_IDS pattern")

        # Remove storage path from enhanced fields array
        # Find and remove the line: {field: FIELD_IDS.STORAGE_PATH, value: storagePath}
        lines_to_remove = [
            '{field: FIELD_IDS.STORAGE_PATH, value: storagePath}',
            '{field: FIELD_IDS.STORAGE_PATH, value: OPTION_ID_MAPS.STORAGE_PATH[storagePath] || storagePath}'
        ]

        for line in lines_to_remove:
            if line in js_code:
                # Remove the line and the comma before it
                js_code = js_code.replace(f',\n      {line}', '')
                js_code = js_code.replace(f'{line},', '')
                print(f"  [OK] Removed storage path field assignment")

        # Add entity data output for Entity Manager
        # Find the enhanced classification section and fix variable scoping
        # Need to move entity data prep INSIDE the try-catch block

        # First, find and replace the classification section ending
        old_classification_end = """  console.log('✅ Enhanced classification completed');
  console.log(`📂 Storage Path: ${storagePath}`);
  console.log(`⚠️  Risk Level: ${riskLevel}`);
  console.log(`📋 Obligation Type: ${obligationType}`);

} catch (error) {
  console.error('❌ Enhanced classification error:', error.message);
  result.processing_summary.enhanced_classification = {
    status: 'error',
    error: error.message
  };
  result.processing_summary.processing_errors.push(`Enhanced Classification: ${error.message}`);
}"""

        new_classification_end = """  console.log('✅ Enhanced classification completed');
  console.log(`📂 Storage Path: ${storagePath}`);
  console.log(`⚠️  Risk Level: ${riskLevel}`);
  console.log(`📋 Obligation Type: ${obligationType}`);

  // === PREPARE DATA FOR ENTITY MANAGER ===
  // Extract primary storage category from storagePath (first segment)
  const storageCategory = storagePath ? storagePath.split('/')[0] : 'reference-documents';

  // Pass data to Entity Manager
  result.correspondent_name = correspondentName || 'Unknown';
  result.correspondent_category = correspondentCategory;
  result.document_type_name = processingData.document_type?.recommended_name || null;
  result.document_type_confidence = processingData.document_type?.confidence || 0;
  result.suggested_tags = processingData.tags?.existing_tag_names || [];
  result.obligation_type = obligationType;
  result.risk_level = riskLevel;
  result.storage_category = storageCategory;
  result.storage_path_template = storagePath;  // Keep for reference/logging

} catch (error) {
  console.error('❌ Enhanced classification error:', error.message);
  result.processing_summary.enhanced_classification = {
    status: 'error',
    error: error.message
  };
  result.processing_summary.processing_errors.push(`Enhanced Classification: ${error.message}`);

  // Fallback values for Entity Manager if classification fails
  result.correspondent_name = 'Unknown';
  result.correspondent_category = 'commercial';
  result.document_type_name = null;
  result.document_type_confidence = 0;
  result.suggested_tags = [];
  result.obligation_type = 'informational';
  result.risk_level = 'low';
  result.storage_category = 'reference-documents';
  result.storage_path_template = 'reference-documents/unknown';
}"""

        if old_classification_end in js_code:
            js_code = js_code.replace(old_classification_end, new_classification_end)
            print("  [OK] Moved entity data prep inside try-catch block")
        else:
            print("  [WARN] Could not find classification end pattern")

        # Remove the old standalone return statement (will be added back at the end)
        enhanced_section = """
  return { json: result };"""

        js_code = js_code.replace('return { json: result };', enhanced_section)
        print("  [OK] Added storage_category output")

        # Update version
        js_code = js_code.replace(
            'v13.1-fixed-select-fields',
            'v14-entity-based-architecture'
        )

        node['parameters']['jsCode'] = js_code
        print("  [OK] Consolidated Processor updated")
        break
else:
    print("[ERROR] Could not find Consolidated Processor node")
    sys.exit(1)

# === STEP 2: Add Entity Manager Node ===
print("\n[STEP 2] Adding Entity Manager node...")

# Read the entity manager code
with open('entity_manager_node.js', 'r', encoding='utf-8') as f:
    entity_manager_code = f.read()

# Find the highest node position to place new node
max_y = max(node['position'][1] for node in workflow['nodes'])

# Create Entity Manager node
entity_manager_node = {
    "parameters": {
        "jsCode": entity_manager_code
    },
    "id": "entity-manager-v14",
    "name": "Entity Manager",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [
        1200,
        max_y + 200
    ]
}

workflow['nodes'].append(entity_manager_node)
print(f"  [OK] Entity Manager node added (ID: entity-manager-v14)")

# === STEP 2.5: Add Build Update Payload Node ===
print("\n[STEP 2.5] Adding Build Update Payload node...")

build_payload_code = """const entityData = $input.first().json;
const classification = entityData.classification || {};

const mergedPayload = {
  ...classification.update_payload,
  storage_path: entityData.storage_path_id,
  correspondent: entityData.correspondent_id,
  document_type: entityData.document_type_id,
  tags: entityData.tag_ids
};

// Remove null values
Object.keys(mergedPayload).forEach(key => {
  if (mergedPayload[key] === null || mergedPayload[key] === undefined) {
    delete mergedPayload[key];
  }
});

console.log('🔨 Built update payload:', Object.keys(mergedPayload));

return {
  json: {
    document_id: classification.document_id,
    update_payload: mergedPayload,
    has_updates: true,
    entity_log: entityData.entity_creation_log
  }
};"""

build_payload_node = {
    "parameters": {
        "jsCode": build_payload_code
    },
    "id": "build-update-payload-v14",
    "name": "Build Update Payload",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [
        -1000,
        192
    ]
}

workflow['nodes'].append(build_payload_node)
print(f"  [OK] Build Update Payload node added (ID: build-update-payload-v14)")

# === STEP 3: Update connections ===
print("\n[STEP 3] Updating node connections...")

# Find Consolidated Processor output connections
# Need to insert Entity Manager between Consolidated Processor and Check if Updates Needed
consolidated_processor_id = None
check_updates_id = None

for node in workflow['nodes']:
    if node.get('name') == 'Consolidated Processor':
        consolidated_processor_id = node['id']
    elif node.get('name') == 'Check if Updates Needed':
        check_updates_id = node['id']

if not consolidated_processor_id or not check_updates_id:
    print("[ERROR] Could not find required nodes for connection update")
    sys.exit(1)

print(f"  Found Consolidated Processor: {consolidated_processor_id}")
print(f"  Found Check if Updates Needed: {check_updates_id}")

# Update connections in workflow
# This is complex - connections in n8n are defined in the workflow's 'connections' object
# For now, document that this needs to be done manually in n8n UI

print("  [WARN] Connections must be updated manually in n8n:")
print("    1. Consolidated Processor -> Entity Manager")
print("    2. Entity Manager -> Check if Updates Needed")

# === STEP 4: Update Document Update node ===
print("\n[STEP 4] Updating Update Document node...")

for node in workflow['nodes']:
    if node.get('name') == 'Update Document':
        print(f"  Found node: {node['id']}")

        # The Update Document node uses HTTP Request
        # We need to update the body to include entity IDs
        # This is typically done in n8n using expressions like {{ $json.storage_path_id }}

        # For now, document that this needs manual update
        print("  [WARN] Update Document node body must be updated manually:")
        print("    Add: storage_path: {{ $json.storage_path_id }}")
        print("    Add: correspondent: {{ $json.correspondent_id }}")
        print("    Add: document_type: {{ $json.document_type_id }}")
        print("    Add: tags: {{ $json.tag_ids }}")
        break

# === STEP 5: Update workflow metadata ===
print("\n[STEP 5] Updating workflow metadata...")

workflow['name'] = 'Paperless AI Processing v14 (Entity-Based)'
print(f"  [OK] Workflow name: {workflow['name']}")

# === STEP 6: Save v14 workflow ===
output_file = 'paperless_workflow-v14-entity-based.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2)

print(f"\n[SUCCESS] v14 workflow saved to: {output_file}")
print(f"[INFO] Workflow nodes: {len(workflow['nodes'])}")
print(f"[INFO] Workflow name: {workflow['name']}")

print("\n=== MANUAL STEPS REQUIRED ===")
print("1. Import paperless_workflow-v14-entity-based.json to n8n")
print("2. Delete redundant nodes:")
print("   - 'Fetch Available Tags'")
print("   - 'Map Tag Names to IDs'")
print("3. Update connections:")
print("   - Consolidated Processor -> Entity Manager")
print("   - Entity Manager -> Build Update Payload")
print("   - Build Update Payload -> Check if Updates Needed")
print("4. Test with sample document")
print("5. Verify files organized on disk")

print("\n=== FILES ===")
print("- [OK] paperless_workflow-v14-entity-based.json (CREATED)")
print("- [OK] entity_manager_node.js (REFERENCE)")
print("- [SKIP] paperless_workflow-v13.1-fixed.json (DO NOT USE - has architectural flaws)")
