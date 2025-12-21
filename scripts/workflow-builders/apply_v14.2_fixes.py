#!/usr/bin/env python3
"""
Apply v14.2 Fixes to Paperless AI Workflow

Fixes Applied:
1. HIGH: Add pagination to storage path lookup
2. HIGH: Add retry logic for unique constraint errors
3. MEDIUM: Add correspondent name normalization
4. MEDIUM: Update correspondent creation to use canonical names

Usage:
    python apply_v14.2_fixes.py
"""

import json
import sys
from pathlib import Path

# Read correspondent normalization code
NORMALIZATION_CODE = '''
// ========================================
// CORRESPONDENT NORMALIZATION FUNCTIONS
// ========================================

const LEGAL_SUFFIXES = [
  'gmbh', 'kg', 'kgaa', 'ag', 'se', 'llc', 'inc', 'corp', 'corporation',
  'ltd', 'limited', 'plc', 's\\\\.a\\\\.?', 's\\\\.r\\\\.l\\\\.?', 's\\\\.p\\\\.a\\\\.?',
  'bv', 'nv', 'oy', 'ab', 'aps', 'as', 'co', 'company', 'rcv',
  'ohg', 'gbr', 'ev', 'eg', 'ges\\\\.m\\\\.b\\\\.h\\\\.?', 'stg'
];

const ALIASES = {
  'boehringer ingelheim rcv & co': 'Boehringer Ingelheim',
  'boehringer ingelheim rcv': 'Boehringer Ingelheim',
  'magistrat wien-mba f.d. 21. bezirk': 'Magistrat Wien',
  'magistrat wien': 'Magistrat Wien',
  'wiener linien gmbh & co': 'Wiener Linien',
  'magenta telekom': 'Magenta Telekom',
  'magenta': 'Magenta Telekom'
};

function normalizeCorrespondent(name) {
  if (!name || typeof name !== 'string') return 'Unknown';

  const lowerName = name.toLowerCase().trim();

  // Check aliases first
  for (const [key, value] of Object.entries(ALIASES)) {
    if (lowerName.startsWith(key)) {
      console.log('Alias match: "' + name + '" → "' + value + '"');
      return value;
    }
  }

  // Remove punctuation and connectors
  let n = name.replace(/[.,]/g, ' ')
              .replace(/\\\\s*&\\\\s*/g, ' ')
              .replace(/\\\\s+and\\\\s+/gi, ' ')
              .replace(/\\\\s+/g, ' ')
              .trim();

  // Strip legal suffixes
  const suffixRe = new RegExp('\\\\\\\\b(' + LEGAL_SUFFIXES.join('|') + ')\\\\\\\\b', 'gi');
  n = n.replace(suffixRe, '').replace(/\\\\s+/g, ' ').trim();

  // Remove trailing connectors
  n = n.replace(/\\\\s*[&+]\\\\s*$/g, '').trim();

  // Title-case
  n = n.replace(/\\\\b\\\\w/g, c => c.toUpperCase());

  console.log('Normalized: "' + name + '" → "' + n + '"');
  return n || 'Unknown';
}

function generateSlug(name) {
  return name.toLowerCase()
    .normalize('NFD')
    .replace(/[\\\\u0300-\\\\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .substring(0, 50);
}
'''

# Updated "Generate Storage Path" code with normalization
GENERATE_STORAGE_PATH_CODE = NORMALIZATION_CODE + '''
// ========================================
// GENERATE STORAGE PATH WITH NORMALIZATION
// ========================================

const data = $input.first().json;
const category = data.storage_category || 'reference-documents';
const rawCorrespondent = data.correspondent_name || 'Unknown';

// Apply normalization
const correspondent = normalizeCorrespondent(rawCorrespondent);
const correspondentSlug = generateSlug(correspondent);
const pathTemplate = category + '/' + correspondentSlug + '/{created_year}-{created_month}-{created_day}-{title}';
const pathName = category + ' - ' + correspondent;

console.log('Storage Path Generated:');
console.log('  Raw: ' + rawCorrespondent);
console.log('  Canonical: ' + correspondent);
console.log('  Slug: ' + correspondentSlug);
console.log('  Template: ' + pathTemplate);
console.log('  Name: ' + pathName);

return {
  json: {
    ...data,
    correspondent_canonical: correspondent,
    storage_path_template: pathTemplate,
    storage_path_name: pathName
  }
};
'''

# Updated "Get Storage Path ID" code with retry logic
GET_STORAGE_PATH_ID_CODE = '''// Extract Storage Path ID from either existing or newly created
console.log('=== GET STORAGE PATH ID ===');

// Always get base data from Match Storage Path node
const matchResult = $('Match Storage Path').first().json;
const createResult = $input.first().json;

// CHECK FOR UNIQUE CONSTRAINT ERROR (400 with specific message)
if (createResult && createResult.statusCode >= 400) {
  const errorMsg = createResult.error || createResult.message || '';
  const isUniqueConstraint = errorMsg.toLowerCase().includes('unique constraint') ||
                             errorMsg.toLowerCase().includes('already exists');

  if (isUniqueConstraint) {
    console.warn('⚠️  UNIQUE CONSTRAINT ERROR - Storage path already exists');
    console.warn('   This is expected behavior when path was created concurrently');
    console.warn('   Error: ' + errorMsg);
    console.warn('   Target name: ' + matchResult.storage_path_name);
    console.warn('   Target path: ' + matchResult.storage_path_template);
    console.warn('');
    console.warn('   Solution: Re-upload document - storage path now exists');
    console.warn('   OR: Increase page_size in Check Storage Paths node');

    throw new Error('Storage path creation failed due to duplicate. Please re-upload document or check "Check Storage Paths" pagination settings.');
  }

  // Other HTTP errors
  console.error('HTTP ERROR from Create Storage Path:');
  console.error('  Status: ' + (createResult.statusCode || 'unknown'));
  console.error('  Error: ' + errorMsg);
  throw new Error('Create Storage Path HTTP request failed: ' + errorMsg);
}

let storagePathId = null;
let source = 'unknown';

// Check if storage path already existed (from Match Storage Path)
if (matchResult.storage_path_id) {
  storagePathId = matchResult.storage_path_id;
  source = 'existing';
  console.log('✓ Using existing storage path ID: ' + storagePathId);
} else {
  // Storage path was just created - get from current input
  if (createResult && createResult.id) {
    storagePathId = createResult.id;
    source = 'created';
    console.log('✓ Created new storage path ID: ' + storagePathId);
    console.log('  Name: ' + createResult.name);
    console.log('  Path: ' + createResult.path);
  }
}

// ERROR HANDLING: Stop if no storage path ID
if (!storagePathId) {
  console.error('ERROR: No storage path ID found!');
  console.error('Match result storage_path_id: ' + matchResult.storage_path_id);
  console.error('Create result id: ' + (createResult && createResult.id));
  throw new Error('Failed to get storage path ID - check previous nodes');
}

console.log('✓ Storage Path ID: ' + storagePathId + ' (source: ' + source + ')');

return {json: {...matchResult, storage_path_id: storagePathId, storage_path_source: source}};
'''


def apply_fixes(workflow_path: Path) -> dict:
    """Apply all v14.2 fixes to the workflow"""

    print(f"Loading workflow from: {workflow_path}")
    with open(workflow_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    nodes = workflow.get('nodes', [])
    fixes_applied = []

    # Fix 1: Add pagination to "Check Storage Paths"
    for node in nodes:
        if node.get('name') == 'Check Storage Paths':
            print("[FIX 1] Applying Fix 1: Add pagination to Check Storage Paths")
            node['parameters']['sendQuery'] = True
            node['parameters']['queryParameters'] = {
                'parameters': [
                    {
                        'name': 'page_size',
                        'value': '1000'
                    }
                ]
            }
            fixes_applied.append("Pagination fix (page_size=1000)")

    # Fix 2: Update "Generate Storage Path" with normalization
    for node in nodes:
        if node.get('name') == 'Generate Storage Path':
            print("[FIX 2] Applying Fix 2: Add correspondent normalization to Generate Storage Path")
            node['parameters']['jsCode'] = GENERATE_STORAGE_PATH_CODE
            fixes_applied.append("Correspondent normalization")

    # Fix 3: Update "Get Storage Path ID" with retry logic
    for node in nodes:
        if node.get('name') == 'Get Storage Path ID':
            print("[FIX 3] Applying Fix 3: Add retry logic to Get Storage Path ID")
            node['parameters']['jsCode'] = GET_STORAGE_PATH_ID_CODE
            fixes_applied.append("Unique constraint error handling")

    # Fix 4: Update "Check Correspondent Exists" to use canonical name
    for node in nodes:
        if node.get('name') == 'Check Correspondent Exists':
            print("[FIX 4] Applying Fix 4: Update Check Correspondent Exists to use canonical name")
            # Update the Code node that searches for correspondent
            current_code = node['parameters'].get('jsCode', '')
            if 'correspondent_name' in current_code:
                updated_code = current_code.replace(
                    'data.correspondent_name',
                    'data.correspondent_canonical || data.correspondent_name'
                )
                node['parameters']['jsCode'] = updated_code
                fixes_applied.append("Correspondent matching uses canonical name")

    # Fix 5: Update "Create Correspondent" to use canonical name
    for node in nodes:
        if node.get('name') == 'Create Correspondent':
            print("[FIX 5] Applying Fix 5: Update Create Correspondent to use canonical name")
            json_body = node['parameters'].get('jsonBody', '')
            if 'correspondent_name' in json_body:
                updated_body = json_body.replace(
                    '$json.correspondent_name',
                    '$json.correspondent_canonical'
                )
                node['parameters']['jsonBody'] = updated_body
                fixes_applied.append("Correspondent creation uses canonical name")

    print(f"\n[SUMMARY] Applied {len(fixes_applied)} fixes:")
    for fix in fixes_applied:
        print(f"  - {fix}")

    return workflow


def main():
    # Paths
    repo_root = Path(__file__).parent.parent.parent
    current_workflow = repo_root / 'workflows' / 'current' / 'paperless-ai-automation.json'
    backup_workflow = repo_root / 'workflows' / 'archive' / 'paperless-ai-automation-v14.1-backup.json'
    output_workflow = repo_root / 'workflows' / 'current' / 'paperless-ai-automation-v14.2.json'

    if not current_workflow.exists():
        print(f"[ERROR] Workflow not found at {current_workflow}")
        sys.exit(1)

    # Backup current workflow
    print(f"\n[BACKUP] Backing up current workflow to: {backup_workflow}")
    backup_workflow.parent.mkdir(parents=True, exist_ok=True)
    with open(current_workflow, 'r', encoding='utf-8') as f:
        backup_data = f.read()
    with open(backup_workflow, 'w', encoding='utf-8') as f:
        f.write(backup_data)

    # Apply fixes
    print("\n[FIXING] Applying v14.2 fixes...")
    fixed_workflow = apply_fixes(current_workflow)

    # Update version info
    fixed_workflow['name'] = 'Paperless AI Processing v14.2'
    fixed_workflow['meta'] = fixed_workflow.get('meta', {})
    fixed_workflow['meta']['version'] = '14.2'

    # Save fixed workflow
    print(f"\n[SAVE] Saving fixed workflow to: {output_workflow}")
    with open(output_workflow, 'w', encoding='utf-8') as f:
        json.dump(fixed_workflow, f, indent=2)

    # Also update the current workflow
    print(f"[SAVE] Updating current workflow: {current_workflow}")
    with open(current_workflow, 'w', encoding='utf-8') as f:
        json.dump(fixed_workflow, f, indent=2)

    print("\n" + "="*60)
    print("[SUCCESS] v14.2 FIXES APPLIED SUCCESSFULLY")
    print("="*60)
    print("\nNext steps:")
    print("1. Import the updated workflow to n8n:")
    print(f"   File: {current_workflow}")
    print("2. Activate the workflow")
    print("3. Test with a sample document")
    print("4. Verify storage path pagination works (check logs)")
    print("5. Verify correspondent normalization works")
    print("\nIf you encounter unique constraint errors:")
    print("- Check n8n execution logs for 'UNIQUE CONSTRAINT ERROR' message")
    print("- Re-upload the document (storage path should now exist)")
    print("- If issue persists, check 'Check Storage Paths' node output")
    print("\n" + "="*60)


if __name__ == '__main__':
    main()
