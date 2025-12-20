#!/usr/bin/env python3
"""
Fix Correspondent Extraction in v14.1 Workflow
Updates AI prompt and Consolidated Processor to properly extract correspondent
"""
import json
import sys
import re

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("[INFO] Loading v14.1 workflow...")
with open('paperless_workflow-v14.1-http-nodes.json', 'r', encoding='utf-8') as f:
    workflow = json.load(f)

print(f"[OK] Loaded: {len(workflow['nodes'])} nodes")

# === FIND AND UPDATE AI PROMPT PREPARATION NODE ===
print("\n[STEP 1] Finding AI Prompt Preparation node...")

ai_prompt_node = None
for node in workflow['nodes']:
    # Look for node that builds ai_prompt
    if node.get('type') == 'n8n-nodes-base.code':
        code = node.get('parameters', {}).get('jsCode', '')
        if 'ai_prompt' in code and 'OUTPUT REQUIREMENTS' in code:
            ai_prompt_node = node
            print(f"[OK] Found AI Prompt Preparation node: '{node['name']}'")
            break

if not ai_prompt_node:
    print("[ERROR] Could not find AI Prompt Preparation node!")
    print("Looking for a Code node with 'ai_prompt' and 'OUTPUT REQUIREMENTS' in the code")
    sys.exit(1)

# Updated AI Prompt Preparation code
new_ai_prompt_code = '''// Enhanced AI Prompt with Error Handling + CORRESPONDENT EXTRACTION
const inputItems = $input.all();
let documentData = null;
let customFieldsData = [];

// Find document data with fallbacks
try {
  documentData = inputItems.find(item => item.json && (item.json.content || item.json.title));
  if (!documentData) {
    throw new Error('No document data found in inputs');
  }
} catch (error) {
  console.error('Document data error:', error.message);
  // Create minimal fallback structure
  documentData = {
    json: {
      id: 'unknown',
      title: 'Unknown Document',
      content: '',
      correspondent: 'Unknown',
      document_type: 'Unknown'
    }
  };
}

// Find custom fields data with fallbacks
try {
  const customFieldsItem = inputItems.find(item => item.json && (Array.isArray(item.json.results) || Array.isArray(item.json)));
  if (customFieldsItem) {
    customFieldsData = customFieldsItem.json.results || customFieldsItem.json || [];
  }
} catch (error) {
  console.warn('Custom fields data not found, continuing with empty array');
  customFieldsData = [];
}

// Safely extract document properties
const documentText = (documentData.json.content || '').substring(0, 2000); // Limit content length
const documentTitle = documentData.json.title || 'Untitled Document';
const correspondent = documentData.json.correspondent || 'Unknown';
const documentType = documentData.json.document_type || 'Unknown';
const documentId = documentData.json.id;

if (!documentId || documentId === 'unknown') {
  console.warn('Document ID is missing or invalid, workflow may have limited functionality');
}

// Build comprehensive prompt
const prompt = `
AI document analyzer for Paperless-ngx. IMPORTANT: Return valid JSON ONLY.

Document Information:
- Title: ${documentTitle}
- Current Type: ${documentType}
- Current Correspondent: ${correspondent}
- Content Preview: ${documentText}
- Available Custom Fields: ${customFieldsData.length} fields

INSTRUCTIONS:
1. Analyze the document content thoroughly
2. **CRITICAL**: Identify the CORRESPONDENT (sender/company/organization) - this is WHO sent or created the document
   - Examples: "Amazon", "Magenta Telekom", "AMS", "Helvetia Insurance", "Microsoft"
   - The correspondent is NOT the document type (Invoice, Letter, etc.)
   - If you cannot determine the sender, use "Unknown" as correspondent name
3. Identify the DOCUMENT TYPE (what kind of document it is)
   - Examples: "Invoice", "Letter", "Contract", "Receipt", "Statement"
4. Use available tools to get existing entities (document_types, custom_fields, tags)
5. Prioritize using existing entities over creating new ones
6. Return structured JSON with confidence scores
7. Handle missing data gracefully

OUTPUT REQUIREMENTS:
Return a JSON object with this exact structure:
{
  "correspondent": {
    "name": "Company or Organization Name",
    "confidence": 0.85,
    "note": "Explain how you identified the correspondent"
  },
  "document_analysis": {
    "confidence": 0.85,
    "category": "detected_category",
    "summary": "brief_analysis_summary"
  },
  "document_type": {
    "recommended_id": 123,
    "recommended_name": "existing_type_name",
    "confidence": 0.90,
    "create_new": false,
    "new_type_suggestion": null
  },
  "custom_fields": {
    "field_updates": {
      "123": "extracted_value_1",
      "456": "extracted_value_2"
    },
    "confidence": 0.85,
    "new_fields_needed": []
  },
  "tags": {
    "existing_tag_names": ["tag1", "tag2"],
    "new_tags_needed": [],
    "confidence": 0.80
  },
  "processing_notes": "Explain decisions and any limitations"
}

EXAMPLES OF CORRECT CORRESPONDENT EXTRACTION:
- Document from Amazon about a purchase → correspondent.name: "Amazon"
- Invoice from Magenta Telekom → correspondent.name: "Magenta Telekom"
- Letter from AMS (Arbeitsmarktservice) → correspondent.name: "AMS"
- Insurance statement from Helvetia → correspondent.name: "Helvetia"
- Receipt from a local shop "Tech Store" → correspondent.name: "Tech Store"

IMPORTANT:
- Use get_document_types, get_custom_fields, get_tags tools first
- Prefer existing entities over creating new ones
- Include confidence scores for all recommendations
- Handle errors gracefully in your analysis
- If you cannot analyze something, explain why in processing_notes
- **Do NOT use document type as correspondent** (e.g., don't use "Invoice" as correspondent.name)
- Return valid JSON only
`;

const result = {
  ...(documentData.json || {}),
  ai_prompt: prompt,
  document_id: documentId,
  custom_fields_available: customFieldsData.length,
  processing_context: {
    has_content: !!(documentData.json.content),
    has_custom_fields: customFieldsData.length > 0,
    document_valid: !!(documentId && documentId !== 'unknown')
  }
};

console.log(`Prepared AI prompt for document ${documentId} with ${customFieldsData.length} custom fields available`);
console.log('✅ Prompt includes correspondent extraction instructions');
return { json: result };'''

ai_prompt_node['parameters']['jsCode'] = new_ai_prompt_code
print("[OK] Updated AI Prompt Preparation node code")

# === FIND AND UPDATE CONSOLIDATED PROCESSOR NODE ===
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

old_code = consolidated_node['parameters']['jsCode']

# Find and replace the correspondent extraction section
# Look for the line: const correspondentName = processingData.document_analysis?.category || 'unknown';
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

if re.search(old_pattern, old_code):
    new_code = re.sub(old_pattern, new_correspondent_extraction, old_code)
    consolidated_node['parameters']['jsCode'] = new_code
    print("[OK] Updated Consolidated Processor correspondent extraction")
else:
    print("[WARNING] Could not find exact correspondent extraction pattern")
    print("Searching for alternative patterns...")

    # Alternative pattern
    if 'const correspondentName' in old_code:
        # Find the section and replace it manually
        lines = old_code.split('\n')
        new_lines = []
        skip_next = False

        for i, line in enumerate(lines):
            if 'const correspondentName = processingData.document_analysis' in line:
                # Replace this line with new extraction code
                new_lines.append(new_correspondent_extraction)
                skip_next = False
            elif skip_next:
                skip_next = False
            else:
                new_lines.append(line)

        new_code = '\n'.join(new_lines)
        consolidated_node['parameters']['jsCode'] = new_code
        print("[OK] Updated using alternative method")
    else:
        print("[ERROR] Could not find correspondent extraction code to replace!")
        sys.exit(1)

# === SAVE UPDATED WORKFLOW ===
output_file = 'paperless_workflow-v14.1-correspondent-fix.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"\n✅ SUCCESS! Saved to: {output_file}")
print("\n[SUMMARY]")
print("Updated 2 nodes:")
print(f"  1. '{ai_prompt_node['name']}' - Added correspondent extraction to AI prompt")
print(f"  2. '{consolidated_node['name']}' - Updated correspondent extraction logic")
print("\n[NEXT STEPS]")
print("1. Re-import the workflow in n8n:")
print("   - Delete old 'Paperless AI Processing v14.1' workflow")
print(f"   - Import: {output_file}")
print("2. Test with a document that has a clear sender (e.g., Amazon invoice)")
print("3. Check console logs for:")
print("   ✅ 'Using AI-extracted correspondent: \"Amazon\"'")
print("   ❌ NOT 'Falling back to document category as correspondent: \"Invoice\"'")
print("4. Verify storage path includes company name, not document type")
