# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Paperless-ngx AI Document Automation System** that uses n8n workflows integrated with OpenAI GPT-4 for intelligent document processing. This is NOT a traditional software project - it's a configuration repository containing n8n workflow definitions and implementation guides.

**Core Purpose**: Automatically categorize, tag, and enrich documents uploaded to Paperless-ngx using AI-powered metadata extraction, obligation tracking, risk assessment, entity management, and intelligent storage path generation.

## Architecture

### Entity-Based Processing Pipeline (v14)

**IMPORTANT**: v13.1 identified critical architectural flaws (see CRITICAL_ARCHITECTURE_ISSUES.md). v14 implements entity-based architecture.

The n8n workflow implements a four-stage architecture:

1. **AI Analysis & Classification**: GPT-4 extracts document metadata and classifies content
2. **Enhanced Processing**: Detects categories, obligation types, risk levels, generates storage paths
3. **Entity Management** (NEW in v14): Creates/matches Paperless entities with deduplication and safeguards
4. **Document Update**: PATCH with entity IDs (not strings) to actually organize files

**Critical Principle**: Paperless-ngx is **entity-based**. Use IDs, not strings, for storage paths, correspondents, document types, and tags.

### Key Nodes in Workflow

- **Process AI Results**: Parses OpenAI GPT-4 JSON response, handles markdown code blocks, sanitizes data
- **Consolidated Processor**: Classification logic - detects categories, obligation types, risk levels, generates storage path templates
- **Entity Manager** (NEW in v14): Creates/matches Paperless entities with deduplication, fuzzy matching, and safeguards
- **Check if Updates Needed**: Conditional router - only sends API updates if `has_updates = true`
- **Update Document**: PATCH request with entity IDs to Paperless-ngx API
- **Final Processing Report**: Generates completion status and logs

### Data Flow

```
Paperless-ngx webhook → n8n workflow → OpenAI GPT-4 analysis →
Parse AI results → Consolidated classification →
Entity Management (create/match entities) →
Build update payload with IDs →
Conditional update check → PATCH to Paperless-ngx →
Files organized on disk → Final report
```

## Working with n8n Workflows

### Importing Workflows

```bash
# Method 1: n8n CLI (if available)
n8n import:workflow --file=paperless_workflow-v12-latest.json

# Method 2: Via n8n web interface
# 1. Open n8n UI (typically http://localhost:5678)
# 2. Click "..." menu → "Import from File"
# 3. Select paperless_workflow-v12-latest.json
```

### Exporting Workflows After Changes

```bash
# Method 1: Via n8n web interface (recommended)
# 1. Open workflow in n8n
# 2. Click "..." menu → "Download"
# 3. Save as paperless_workflow-v[version]-[description].json

# Method 2: n8n API (if enabled)
curl -X GET "http://localhost:5678/api/v1/workflows/YOUR_WORKFLOW_ID" \
  -H "Authorization: Bearer YOUR_N8N_API_KEY" > paperless_workflow-v13-new-feature.json
```

### Testing Workflow Changes

There are NO automated tests. Testing is done by:

1. **Backup first**: Always export current working workflow before making changes
2. **Upload test documents**: Create simple test files with known content
3. **Monitor n8n execution logs**: Check console.log output in workflow execution view
4. **Verify in Paperless-ngx**: Confirm document metadata was updated correctly

Example test documents are provided in `AI_Implementation_TODO_Guide.md` (TODO 6).

## Custom Field Configuration

### Required Paperless-ngx Custom Fields

**IMPORTANT**: v14 removed custom field #33 "Storage Path" - we now use Paperless's built-in `storage_path` entity field instead.

The workflow expects these **5 custom fields** to exist in Paperless-ngx (IDs may vary):

| Field ID | Name | Type | Purpose |
|----------|------|------|---------|
| 34 | SLA Deadline | Date | Action deadline for obligations |
| 35 | Obligation Type | Select | hard_obligation, soft_tracking, informational, none |
| 36 | Risk Level | Select | critical, high, medium, low |
| 37 | Correspondent Category | Select | government, insurance, financial, health, commercial, technical |
| 38 | Monitoring Status | Select | active, pending, completed, archived |

**Storage Path**: Managed via Paperless's built-in `storage_path` field (entity ID), NOT a custom field. See ARCHITECTURE_V2_DESIGN.md for details.

### Creating Custom Fields via API

See `AI_Implementation_TODO_Guide.md` TODO 2 for the complete script. Field IDs must be updated in the workflow code after creation.

### Select Field Option IDs

**CRITICAL**: Paperless-ngx select fields require **option IDs**, not label strings. The workflow uses `OPTION_ID_MAPS` to translate labels to IDs:

```javascript
const OPTION_ID_MAPS = {
  OBLIGATION_TYPE: {
    'hard_obligation': 'YumCdzEuieiKcVDI',
    'soft_tracking': '0IWw2uQwjqwdrFXE',
    'informational': 'A9luuKq3diPjVhDg',
    'none': 'Bvz8jz0qPprJ24SR'
  },
  // ... more mappings
};
```

Sending label strings causes API 400 errors (see API_400_FIX_SUMMARY.md).

## JavaScript Node Patterns

### Date Format Handling

The Consolidated Processor node handles multiple date formats and converts them to Paperless-ngx's required `YYYY-MM-DD` format:

```javascript
// European format: DD.MM.YYYY → YYYY-MM-DD
// Partial format: YYYY-MM → YYYY-MM-01
// US format: MM/DD/YYYY → YYYY-MM-DD
```

This is critical because Paperless-ngx strictly validates date fields and rejects incorrect formats.

### Error Resilience Pattern

Each processing branch (document type, custom fields, tags) is wrapped in try-catch blocks with fallback behavior:

```javascript
try {
  // Process branch
  result.update_payload.field = value;
  result.has_updates = true;
} catch (error) {
  result.processing_summary.processing_errors.push(`Branch: ${error.message}`);
  // Continue processing other branches
}
```

This ensures partial updates succeed even if one branch fails.

### Custom Fields Array Format

Paperless-ngx API requires custom fields in array format, NOT object format:

```javascript
// CORRECT:
custom_fields: [
  {field: 35, value: "YumCdzEuieiKcVDI"},  // Option ID, not label
  {field: 36, value: "619ScM1aAKiflS2K"}
]

// INCORRECT:
custom_fields: {
  "35": "hard_obligation",  // Object format + label string
  "36": "high"
}
```

### Entity Management Pattern (v14)

**Critical**: Paperless entities (storage paths, correspondents, document types, tags) must be created before referencing them:

```javascript
// WRONG: Reference non-existent entity
{
  "storage_path": 12  // Fails if ID 12 doesn't exist
}

// CORRECT: Create/match entity first
const storagePathId = await getOrCreateStoragePath(category, correspondent);
{
  "storage_path": storagePathId  // ID guaranteed to exist
}
```

**Entity Management Flow**:
1. Generate entity name/template from classification
2. Check if entity exists (exact or fuzzy match)
3. Create entity if needed
4. Return ID for document update

See ARCHITECTURE_V2_DESIGN.md for complete entity management functions.

### Metadata Safeguards

Prevent redundant/meaningless metadata:

```javascript
// Don't create tags that duplicate document type
if (documentType === "Invoice" && suggestedTag === "invoice") {
  // Skip this tag - it's redundant
}

// Don't create tags that duplicate correspondent
if (correspondent === "Magenta Telekom" && suggestedTag === "magenta") {
  // Skip this tag - it's redundant
}

// Don't create generic tags
if (['document', 'file', 'unknown'].includes(suggestedTag)) {
  // Skip generic tags
}
```

## Common Modifications

### Updating Field IDs

When custom fields are created in Paperless-ngx, their IDs must be updated in the workflow:

1. Create custom fields via API or web interface
2. Note the returned field IDs
3. Update `FIELD_IDS` constants in workflow nodes
4. Re-import workflow to n8n

### Adding New Classification Logic

To enhance document classification (see `AI_Implementation_TODO_Guide.md` TODO 4):

1. Locate the "Consolidated Processor" node in the workflow JSON
2. Add classification functions (e.g., `detectCorrespondentCategory`, `assessRiskLevel`)
3. Insert classification code BEFORE the final `return { json: result }` statement
4. Merge enhanced fields with existing custom_fields array

### Adjusting Confidence Thresholds

Confidence thresholds control when AI suggestions are applied:

```javascript
// Document type: Only apply if confidence > 0.6
if (documentTypeData.confidence > 0.6) { ... }

// Custom fields: Only apply if confidence > 0.5
if (customFieldsData.confidence > 0.5) { ... }

// Tags: Only apply if confidence > 0.5
if (tagsData.confidence > 0.5) { ... }
```

Lower thresholds = more automated updates but potentially lower accuracy.

## Integration Points

### Paperless-ngx API

**Base URL**: `https://paperless.zenmedia.live/api/`
**Authentication**: HTTP Header Auth with Token

Key endpoints used:
- `GET /api/documents/` - List documents
- `PATCH /api/documents/{id}/` - Update document metadata
- `POST /api/custom_fields/` - Create custom fields
- `GET /api/custom_fields/` - List custom fields

### OpenAI API

The workflow uses GPT-4 for document analysis. The AI receives:
- Document content/OCR text
- List of existing correspondents, document types, and tags
- Structured prompt requesting JSON output

Expected JSON response format is defined in "Process AI Results" node.

## Troubleshooting

### Workflow Execution Failures

1. Check n8n execution logs for JavaScript errors
2. Verify Paperless-ngx API credentials are valid
3. Confirm custom field IDs match those in Paperless-ngx
4. Check OpenAI API key and rate limits

### Document Updates Not Applied

1. Verify `has_updates = true` in Consolidated Processor output
2. Check "Check if Updates Needed" conditional is routing to Update Document node
3. Look for HTTP errors in Update Document node execution
4. Confirm date formats are valid YYYY-MM-DD

### AI Analysis Errors

1. Check OpenAI API response in "Process AI Results" node
2. Verify JSON parsing succeeds (handles markdown code blocks)
3. Confirm confidence scores are above thresholds
4. Review AI prompt for clarity and structure

## Workflow Versioning

Workflow versions follow this pattern: `paperless_workflow-v{number}-{description}.json`

- **v5**: Initial three-branch architecture
- **v6**: Enhanced error handling and fallbacks
- **v7**: Optimized AI tool result reuse
- **v8**: Tag name-to-ID mapping
- **v12**: Enhanced date format handling and consolidated processing
- **v13**: Added classification logic (has API 400 bug - DO NOT USE)
- **v13.1**: Fixed API 400 error with option ID mappings (tested, but has architectural flaws)
- **v14** (in development): Entity-based architecture with dynamic entity creation

Always increment version numbers when making significant changes and document the changes in the filename or commit message.

### Critical Issues by Version

- **v13**: ❌ Sends label strings instead of option IDs → API 400 error
- **v13.1**: ⚠️ Fixed option IDs, but uses custom field for storage path (doesn't organize files)
- **v14**: ✅ Uses Paperless entities, creates them dynamically, actually organizes files

## Reference Documentation

### Core Documentation
- [README.md](README.md) - Complete system overview, features, and architecture
- [CLAUDE.md](CLAUDE.md) - This file: Project instructions for Claude Code
- [ARCHITECTURE_V2_DESIGN.md](ARCHITECTURE_V2_DESIGN.md) - **NEW**: Entity-based architecture design for v14

### Implementation Guides
- [AI_Implementation_TODO_Guide.md](AI_Implementation_TODO_Guide.md) - Step-by-step implementation guide
- [DEPLOYMENT_INSTRUCTIONS.md](DEPLOYMENT_INSTRUCTIONS.md) - Workflow deployment guide (currently v13.1)
- [TODO_TRACKER.md](TODO_TRACKER.md) - Progress tracking for 9 implementation tasks

### Issue Documentation
- [CRITICAL_ARCHITECTURE_ISSUES.md](CRITICAL_ARCHITECTURE_ISSUES.md) - **IMPORTANT**: Read this first - documents v13.1 flaws
- [API_400_FIX_SUMMARY.md](API_400_FIX_SUMMARY.md) - How we fixed the option ID bug in v13.1
- [BACKUP_VERIFICATION.md](BACKUP_VERIFICATION.md) - v12 backup verification report

### External References
- Paperless-ngx API docs: Check your Paperless-ngx instance at `/api/schema/`
- n8n workflow docs: https://docs.n8n.io/workflows/

## Important Notes

- This repository contains NO build/compile/test commands - it's pure configuration
- Changes to JavaScript code happen INSIDE the n8n workflow JSON (edit via n8n UI)
- Always backup workflows before modifications
- Test with sample documents before processing production documents
- Monitor OpenAI API costs - each document analysis makes API calls
- Custom field IDs are instance-specific and must be updated after Paperless-ngx setup
