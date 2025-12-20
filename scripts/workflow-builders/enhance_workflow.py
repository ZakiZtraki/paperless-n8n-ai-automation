#!/usr/bin/env python3
import json
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("[INFO] Loading v14 workflow...")
with open('paperless_workflow-v14-entity-based.json', 'r', encoding='utf-8') as f:
    workflow = json.load(f)

workflow['name'] = 'Paperless AI Processing v14.1 (HTTP Nodes)'
print(f"[OK] Loaded: {len(workflow['nodes'])} nodes")

# Remove broken nodes
workflow['nodes'] = [n for n in workflow['nodes'] if n['name'] not in ['Entity Manager', 'Build Update Payload', 'Fetch Available Tags', 'Map Tag Names to IDs']]
print(f"[OK] Removed broken nodes: {len(workflow['nodes'])} remaining")

# === ADD NEW NODES ===

print("Adding new entity management nodes...")

# Helper function to create HTTP node
def make_http_node(name, method, url, body=None, pos_x=0, pos_y=192):
    node = {
        "parameters": {
            "method": method,
            "url": url,
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "options": {}
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.3,
        "position": [pos_x, pos_y],
        "id": f"{name.lower().replace(' ', '-').replace('?', '')}-v141",
        "name": name,
        "credentials": {"httpHeaderAuth": {"id": "YOUR_N8N_CREDENTIAL_ID", "name": "PaperlessAPI"}},
        "onError": "continueRegularOutput"
    }
    if method == "POST" and body:
        node["parameters"]["sendBody"] = True
        node["parameters"]["specifyBody"] = "json"
        node["parameters"]["jsonBody"] = body
    return node

# Helper function to create Code node
def make_code_node(name, code, pos_x=0, pos_y=192):
    return {
        "parameters": {"jsCode": code},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [pos_x, pos_y],
        "id": f"{name.lower().replace(' ', '-')}-v141",
        "name": name
    }

# Helper function to create IF node
def make_if_node(name, condition, pos_x=0, pos_y=192):
    # Ensure condition has version field
    if "options" in condition and "version" not in condition["options"]:
        condition["options"]["version"] = 1

    return {
        "parameters": {
            "conditions": condition,
            "options": {}
        },
        "id": f"{name.lower().replace(' ', '-').replace('?', '')}-v141",
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [pos_x, pos_y]
    }

# NODE 1: Check Correspondent Exists
workflow['nodes'].append(make_http_node(
    "Check Correspondent Exists",
    "GET",
    "=https://your-paperless-domain.com/api/correspondents/?name__iexact={{ encodeURIComponent($json.correspondent_name) }}",
    pos_x=-1184, pos_y=192
))

# NODE 2: Correspondent Exists? (IF)
workflow['nodes'].append(make_if_node(
    "Correspondent Exists?",
    {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
        "conditions": [{
            "id": "has-correspondent",
            "leftValue": "={{ $json.count }}",
            "rightValue": "0",
            "operator": {"type": "number", "operation": "gt"}
        }]
    },
    pos_x=-960, pos_y=192
))

# NODE 3: Create Correspondent
workflow['nodes'].append(make_http_node(
    "Create Correspondent",
    "POST",
    "https://your-paperless-domain.com/api/correspondents/",
    '={{ {"name": $("Consolidated Processor").first().json.correspondent_name, "matching_algorithm": 6} }}',
    pos_x=-960, pos_y=384
))

# NODE 4: Get Correspondent ID
get_corr_code = '''const data = $('Consolidated Processor').first().json;
const checkResult = $('Check Correspondent Exists').first().json;
const createResult = $input.first().json;

// CHECK FOR HTTP ERROR from Create Correspondent
if (createResult && (createResult.error || createResult.statusCode >= 400)) {
  console.error('HTTP ERROR from Create Correspondent:');
  console.error('  Status: ' + (createResult.statusCode || 'unknown'));
  console.error('  Error: ' + (createResult.error || 'unknown'));
  console.error('  Message: ' + (createResult.message || 'unknown'));
  console.error('  Response body: ' + JSON.stringify(createResult, null, 2));
  throw new Error('Create Correspondent HTTP request failed: ' + (createResult.message || createResult.error || 'Unknown error'));
}

let correspondentId = null;
let action = 'unknown';

if (checkResult && checkResult.count > 0) {
  correspondentId = checkResult.results[0].id;
  action = 'matched';
  console.log('Matched correspondent ID: ' + correspondentId);
} else if (createResult && createResult.id) {
  correspondentId = createResult.id;
  action = 'created';
  console.log('Created correspondent ID: ' + correspondentId);
}

if (!correspondentId) {
  console.error('ERROR: No correspondent ID found!');
  console.error('Check result count: ' + (checkResult ? checkResult.count : 'null'));
  console.error('Create result has id: ' + !!(createResult && createResult.id));
  console.error('Create result full object: ' + JSON.stringify(createResult, null, 2));
  throw new Error('Failed to get correspondent ID');
}

return {json: {...data, correspondent_id: correspondentId, correspondent_action: action}};'''

workflow['nodes'].append(make_code_node("Get Correspondent ID", get_corr_code, pos_x=-720, pos_y=192))

# NODE 5: Generate Storage Path
gen_path_code = '''const data = $input.first().json;
const category = data.storage_category || 'reference-documents';
const correspondent = data.correspondent_name || 'Unknown';

const correspondentSlug = correspondent.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
const pathTemplate = category + '/' + correspondentSlug + '/{created_year}-{created_month}-{created_day}-{title}';
const pathName = category + ' - ' + correspondent;

console.log('Storage Path: ' + pathTemplate);

return {json: {...data, storage_path_template: pathTemplate, storage_path_name: pathName}};'''

workflow['nodes'].append(make_code_node("Generate Storage Path", gen_path_code, pos_x=-480, pos_y=192))

# NODE 6: Check Storage Paths
workflow['nodes'].append(make_http_node(
    "Check Storage Paths",
    "GET",
    "https://your-paperless-domain.com/api/storage_paths/",
    pos_x=-240, pos_y=192
))

# NODE 7: Match Storage Path
match_path_code = '''const allPaths = $input.first().json;
const data = $('Generate Storage Path').first().json;
const targetTemplate = data.storage_path_template;
const targetName = data.storage_path_name;

console.log('Looking for storage path:');
console.log('  Name: ' + targetName);
console.log('  Template: ' + targetTemplate);

// Check both name and path to avoid unique constraint errors
const existing = allPaths.results.find(function(sp) {
  return sp.name === targetName || sp.path === targetTemplate;
});

if (existing) {
  console.log('Found existing storage path:');
  console.log('  ID: ' + existing.id);
  console.log('  Name: ' + existing.name);
  console.log('  Path: ' + existing.path);
  console.log('  Match type: ' + (existing.name === targetName ? 'by name' : 'by path'));
  return {json: {...data, storage_path_id: existing.id, storage_path_exists: true}};
} else {
  console.log('No matching storage path found, will create new one');
  return {json: {...data, storage_path_id: null, storage_path_exists: false}};
}'''

workflow['nodes'].append(make_code_node("Match Storage Path", match_path_code, pos_x=0, pos_y=192))

# NODE 8: Create Storage Path? (IF)
workflow['nodes'].append(make_if_node(
    "Create Storage Path?",
    {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
        "conditions": [{
            "id": "storage-path-needs-creation",
            "leftValue": "={{ $json.storage_path_exists }}",
            "rightValue": "",
            "operator": {"type": "boolean", "operation": "false", "singleValue": True}
        }]
    },
    pos_x=240, pos_y=192
))

# NODE 9: Create Storage Path
workflow['nodes'].append(make_http_node(
    "Create Storage Path",
    "POST",
    "https://your-paperless-domain.com/api/storage_paths/",
    '={{ {"name": $json.storage_path_name, "path": $json.storage_path_template, "matching_algorithm": 0} }}',
    pos_x=240, pos_y=384
))

# NODE 10: Get Storage Path ID
get_sp_code = '''// Extract Storage Path ID from either existing or newly created
console.log('=== GET STORAGE PATH ID ===');

// Always get base data from Match Storage Path node
const matchResult = $('Match Storage Path').first().json;
const createResult = $input.first().json;

// CHECK FOR HTTP ERROR from Create Storage Path
if (createResult && (createResult.error || createResult.statusCode >= 400)) {
  console.error('HTTP ERROR from Create Storage Path:');
  console.error('  Status: ' + (createResult.statusCode || 'unknown'));
  console.error('  Error: ' + (createResult.error || 'unknown'));
  console.error('  Message: ' + (createResult.message || 'unknown'));
  console.error('  Response body: ' + JSON.stringify(createResult, null, 2));
  throw new Error('Create Storage Path HTTP request failed: ' + (createResult.message || createResult.error || 'Unknown error'));
}

let storagePathId = null;
let source = 'unknown';

// Check if storage path already existed (from Match Storage Path)
if (matchResult.storage_path_id) {
  storagePathId = matchResult.storage_path_id;
  source = 'existing';
  console.log('Using existing storage path ID: ' + storagePathId);
} else {
  // Storage path was just created - get from current input
  if (createResult && createResult.id) {
    storagePathId = createResult.id;
    source = 'created';
    console.log('Created new storage path ID: ' + storagePathId);
    console.log('  Name: ' + createResult.name);
    console.log('  Path: ' + createResult.path);
  }
}

// ERROR HANDLING: Stop if no storage path ID
if (!storagePathId) {
  console.error('ERROR: No storage path ID found!');
  console.error('Match result has storage_path_id: ' + !!matchResult.storage_path_id);
  console.error('Input has id: ' + !!($input.first().json && $input.first().json.id));
  console.error('Create result full object: ' + JSON.stringify(createResult, null, 2));
  throw new Error('Failed to get storage path ID - check Create Storage Path node');
}

console.log('Storage Path ID: ' + storagePathId + ' (source: ' + source + ')');

return {json: {...matchResult, storage_path_id: storagePathId, storage_path_source: source}};'''

workflow['nodes'].append(make_code_node("Get Storage Path ID", get_sp_code, pos_x=480, pos_y=192))

# NODE 11: Build Update Payload
build_payload_code = '''console.log('=== BUILD UPDATE PAYLOAD ===');
const data = $input.first().json;

const payload = {};

if (data.update_payload && data.update_payload.custom_fields) {
  payload.custom_fields = data.update_payload.custom_fields;
  console.log('Custom fields: ' + payload.custom_fields.length);
}

if (data.correspondent_id) {
  payload.correspondent = data.correspondent_id;
  console.log('Correspondent ID: ' + data.correspondent_id);
}

if (data.storage_path_id) {
  payload.storage_path = data.storage_path_id;
  console.log('Storage Path ID: ' + data.storage_path_id);
}

if (data.update_payload && data.update_payload.document_type) {
  payload.document_type = data.update_payload.document_type;
  console.log('Document Type ID: ' + payload.document_type);
}

const hasUpdates = Object.keys(payload).length > 0;
console.log('Has updates: ' + hasUpdates);

return {json: {document_id: data.document_id, update_payload: payload, has_updates: hasUpdates, processing_summary: data.processing_summary || {}}};'''

workflow['nodes'].append(make_code_node("Build Update Payload", build_payload_code, pos_x=720, pos_y=192))

print(f"Added 11 new nodes. Total now: {len(workflow['nodes'])}")

# === UPDATE CONNECTIONS ===
print("Updating connections...")

conn = workflow.get('connections', {})

# Consolidated Processor -> Check Correspondent Exists
conn['Consolidated Processor'] = {"main": [[{"node": "Check Correspondent Exists", "type": "main", "index": 0}]]}

# Check Correspondent Exists -> Correspondent Exists?
conn['Check Correspondent Exists'] = {"main": [[{"node": "Correspondent Exists?", "type": "main", "index": 0}]]}

# Correspondent Exists? -> Get Correspondent ID (TRUE) / Create Correspondent (FALSE)
conn['Correspondent Exists?'] = {"main": [[{"node": "Get Correspondent ID", "type": "main", "index": 0}], [{"node": "Create Correspondent", "type": "main", "index": 0}]]}

# Create Correspondent -> Get Correspondent ID
conn['Create Correspondent'] = {"main": [[{"node": "Get Correspondent ID", "type": "main", "index": 0}]]}

# Get Correspondent ID -> Generate Storage Path
conn['Get Correspondent ID'] = {"main": [[{"node": "Generate Storage Path", "type": "main", "index": 0}]]}

# Generate Storage Path -> Check Storage Paths
conn['Generate Storage Path'] = {"main": [[{"node": "Check Storage Paths", "type": "main", "index": 0}]]}

# Check Storage Paths -> Match Storage Path
conn['Check Storage Paths'] = {"main": [[{"node": "Match Storage Path", "type": "main", "index": 0}]]}

# Match Storage Path -> Create Storage Path?
conn['Match Storage Path'] = {"main": [[{"node": "Create Storage Path?", "type": "main", "index": 0}]]}

# Create Storage Path? -> Create Storage Path (TRUE) / Get Storage Path ID (FALSE)
conn['Create Storage Path?'] = {"main": [[{"node": "Create Storage Path", "type": "main", "index": 0}], [{"node": "Get Storage Path ID", "type": "main", "index": 0}]]}

# Create Storage Path -> Get Storage Path ID
conn['Create Storage Path'] = {"main": [[{"node": "Get Storage Path ID", "type": "main", "index": 0}]]}

# Get Storage Path ID -> Build Update Payload
conn['Get Storage Path ID'] = {"main": [[{"node": "Build Update Payload", "type": "main", "index": 0}]]}

# Build Update Payload -> Check if Updates Needed
conn['Build Update Payload'] = {"main": [[{"node": "Check if Updates Needed", "type": "main", "index": 0}]]}

workflow['connections'] = conn
print("Connections updated")

output_file = 'paperless_workflow-v14.1-http-nodes.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"✅ Saved to: {output_file}")
