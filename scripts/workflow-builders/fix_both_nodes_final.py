#!/usr/bin/env python3
"""
Fix BOTH Process AI Results and Consolidated Processor nodes
Process AI Results: Add correspondent extraction and better JSON parsing
Consolidated Processor: Keep original classification logic, just update correspondent extraction
"""
import json
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("[INFO] Loading workflow...")
with open('paperless_workflow-v14.1-correspondent-fix.json', 'r', encoding='utf-8') as f:
    workflow = json.load(f)

print(f"[OK] Loaded: {len(workflow['nodes'])} nodes")

# === FIX 1: PROCESS AI RESULTS NODE ===
print("\n[STEP 1] Finding Process AI Results node...")

process_ai_node = None
for node in workflow['nodes']:
    if node.get('name') == 'Process AI Results':
        process_ai_node = node
        print(f"[OK] Found Process AI Results node")
        break

if not process_ai_node:
    print("[ERROR] Could not find Process AI Results node!")
    sys.exit(1)

# Fixed Process AI Results code with correspondent extraction
process_ai_code = '''// Consolidated AI Results Processor - Handles all processing in one node
console.log('=== CONSOLIDATED AI RESULTS PROCESSOR ===');
const startTime = Date.now();

let aiResults = {};
let processingErrors = [];

try {
  const input = $input.first();
  if (!input || !input.json) {
    throw new Error('No input data received');
  }

  console.log('Input structure - Keys:', Object.keys(input.json));

  // Capture document_id from input (single extraction)
  const documentId = input.json.document_id || null;
  console.log('Document ID:', documentId);

  // Extract AI response from "output" field
  let aiResponseText = input.json.output || input.json;
  console.log('Content type:', typeof aiResponseText);

  // Parse the AI response
  let parsedResults;

  if (typeof aiResponseText === 'object') {
    parsedResults = aiResponseText;
  } else if (typeof aiResponseText === 'string') {
    console.log('Raw AI response (first 200 chars):', aiResponseText.substring(0, 200));

    // Remove markdown code blocks
    let jsonText = aiResponseText
      .replace(/```json\\n?/g, '')
      .replace(/```\\n?/g, '')
      .trim();

    // Extract JSON from text - find everything between first { and last }
    const firstBrace = jsonText.indexOf('{');
    const lastBrace = jsonText.lastIndexOf('}');

    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      jsonText = jsonText.substring(firstBrace, lastBrace + 1);
      console.log('✅ Extracted JSON from text (first 100 chars):', jsonText.substring(0, 100));
    }

    parsedResults = JSON.parse(jsonText);
    console.log('✅ Parsed successfully');
  }

  aiResults = parsedResults;

} catch (error) {
  console.error('Error:', error.message);
  processingErrors.push(`Parsing error: ${error.message}`);
  aiResults = {
    correspondent: { name: 'Unknown', confidence: 0, note: '' },
    document_analysis: { confidence: 0.1, category: 'unknown', summary: 'Parsing failed' },
    document_type: { recommended_id: null, confidence: 0, create_new: false },
    custom_fields: { field_updates: {}, confidence: 0 },
    tags: { existing_tag_names: [], new_tags_needed: [], confidence: 0 }
  };
}

// Get document_id from input
const input = $input.first();
const documentId = input?.json?.document_id || null;

// Build final sanitized structure
const sanitizedResults = {
  document_id: documentId,

  correspondent: {
    name: String(aiResults.correspondent?.name || 'Unknown'),
    confidence: Number(aiResults.correspondent?.confidence) || 0,
    note: String(aiResults.correspondent?.note || '')
  },

  document_analysis: {
    confidence: Number(aiResults.document_analysis?.confidence) || 0.5,
    category: String(aiResults.document_analysis?.category || 'unknown'),
    summary: String(aiResults.document_analysis?.summary || 'Analysis completed')
  },

  document_type: {
    recommended_id: aiResults.document_type?.recommended_id || null,
    recommended_name: String(aiResults.document_type?.recommended_name || ''),
    confidence: Number(aiResults.document_type?.confidence) || 0,
    create_new: Boolean(aiResults.document_type?.create_new),
    new_type_suggestion: aiResults.document_type?.new_type_suggestion || null
  },

  custom_fields: {
    field_updates: aiResults.custom_fields?.field_updates || {},
    confidence: Number(aiResults.custom_fields?.confidence) || 0,
    new_fields_needed: aiResults.custom_fields?.new_fields_needed || []
  },

  tags: {
    existing_tag_names: aiResults.tags?.existing_tag_names || [],
    new_tags_needed: aiResults.tags?.new_tags_needed || [],
    confidence: Number(aiResults.tags?.confidence) || 0
  },

  processing_notes: String(aiResults.processing_notes || 'Processing completed'),
  processing_errors: processingErrors,
  processing_timestamp: new Date().toISOString(),
  processing_duration_ms: Date.now() - startTime
};

console.log('=== PARSING COMPLETE ===');
console.log(`Document ID: ${documentId}`);
console.log(`Correspondent: ${sanitizedResults.correspondent.name} (confidence: ${sanitizedResults.correspondent.confidence})`);
console.log(`Duration: ${sanitizedResults.processing_duration_ms}ms`);

return { json: sanitizedResults };'''

process_ai_node['parameters']['jsCode'] = process_ai_code
print("[OK] Updated Process AI Results node")

# === FIX 2: CONSOLIDATED PROCESSOR NODE ===
print("\n[STEP 2] Finding Consolidated Processor node...")

consolidated_node = None
for node in workflow['nodes']:
    if node.get('name') == 'Consolidated Processor':
        consolidated_node = node
        print(f"[OK] Found Consolidated Processor node")
        break

if not consolidated_node:
    print("[ERROR] Could not find Consolidated Processor node!")
    sys.exit(1)

# Check if it has the wrong code (parsing code instead of classification code)
current_code = consolidated_node['parameters']['jsCode']
if '=== CONSOLIDATED AI RESULTS PROCESSOR ===' in current_code:
    print("[WARNING] Consolidated Processor has WRONG code (parsing code detected)!")
    print("[INFO] This explains why correspondent_name is undefined")

# We need to use the original v14 Consolidated Processor code
# Load it from the v14 workflow
print("[INFO] Loading original Consolidated Processor code from v14 workflow...")
with open('paperless_workflow-v14-entity-based.json', 'r', encoding='utf-8') as f:
    v14_workflow = json.load(f)

v14_consolidated = None
for node in v14_workflow['nodes']:
    if node.get('name') == 'Consolidated Processor':
        v14_consolidated = node
        break

if not v14_consolidated:
    print("[ERROR] Could not find Consolidated Processor in v14 workflow!")
    sys.exit(1)

# Get the original code and update the correspondent extraction part
original_code = v14_consolidated['parameters']['jsCode']

# Replace the correspondent extraction section
import re

old_pattern = r"const correspondentName = processingData\.document_analysis\?\.category \|\| 'unknown';"

new_correspondent_extraction = '''// ===== UPDATED CORRESPONDENT EXTRACTION =====
  // Priority:
  // 1. Use AI-extracted correspondent.name if available and confidence > 0.6
  // 2. Fall back to document_analysis.category (old behavior)
  // 3. Fall back to "Unknown"
  let correspondentName = 'Unknown';

  if (processingData.correspondent?.name && processingData.correspondent.confidence > 0.6) {
    correspondentName = processingData.correspondent.name;
    console.log(`✅ Using AI-extracted correspondent: "${correspondentName}" (confidence: ${processingData.correspondent.confidence})`);
    if (processingData.correspondent.note) {
      console.log(`   Note: ${processingData.correspondent.note}`);
    }
  } else if (processingData.document_analysis?.category) {
    correspondentName = processingData.document_analysis.category;
    console.warn(`⚠️ Falling back to document category as correspondent: "${correspondentName}"`);
    console.warn('   This may be incorrect - check AI correspondent extraction');
  } else {
    console.warn('⚠️ No correspondent information found, using "Unknown"');
  }

  // Validate correspondent is not a document type
  const commonDocTypes = ['invoice', 'letter', 'contract', 'receipt', 'statement', 'document'];
  if (commonDocTypes.includes(correspondentName.toLowerCase())) {
    console.error(`❌ INVALID CORRESPONDENT: "${correspondentName}" is a document type, not a sender!`);
    console.error('   Setting correspondent to "Unknown" - please fix AI extraction');
    correspondentName = 'Unknown';
  }'''

if re.search(old_pattern, original_code):
    updated_code = re.sub(old_pattern, new_correspondent_extraction, original_code)
    consolidated_node['parameters']['jsCode'] = updated_code
    print("[OK] Updated Consolidated Processor with correspondent extraction fix")
else:
    print("[WARNING] Could not find correspondent extraction pattern to replace")
    print("[INFO] Using original v14 code as-is (will work but with old correspondent logic)")
    consolidated_node['parameters']['jsCode'] = original_code

# === SAVE UPDATED WORKFLOW ===
output_file = 'paperless_workflow-v14.1-both-nodes-fixed.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"\n✅ SUCCESS! Saved to: {output_file}")
print("\n[SUMMARY]")
print("Fixed 2 nodes:")
print("  1. 'Process AI Results' - Added correspondent extraction and better JSON parsing")
print("  2. 'Consolidated Processor' - Restored original classification code with updated correspondent extraction")
print("\n[WHAT WAS WRONG]")
print("  - Consolidated Processor had parsing code instead of classification code")
print("  - This caused correspondent_name to be undefined")
print("  - Create Correspondent had no 'name' field in the body")
print("\n[NEXT STEPS]")
print("1. Re-import the workflow in n8n:")
print("   - Delete old workflow")
print(f"   - Import: {output_file}")
print("2. Test with a document")
print("3. You should now see:")
print("   - 'Check Correspondent Exists' with proper name")
print("   - 'Create Correspondent' with both name and matching_algorithm")
print("   - Proper storage path generation")
