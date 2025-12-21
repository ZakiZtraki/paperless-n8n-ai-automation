# Architecture Overview

## System Design

The Paperless-ngx AI Document Automation system uses a **four-stage processing pipeline**:

```text
┌─────────────────────────────────────────────────────────┐
│ Stage 1: AI Analysis & Classification                   │
│ • GPT-4 extracts metadata from document content         │
│ • Identifies correspondents, document types, tags       │
│ • Determines category, risk level, obligation type     │
└─────────────────────────┬───────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Stage 2: Enhanced Processing                            │
│ • Classifies documents by category and risk            │
│ • Generates intelligent storage path templates         │
│ • Calculates SLA deadlines for obligations             │
│ • Populates custom fields with metadata                │
└─────────────────────────┬───────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Stage 3: Entity Management (Critical!)                  │
│ • Creates/matches correspondents (deduplication)        │
│ • Creates/matches storage paths                        │
│ • Creates/matches document types                       │
│ • Validates all entities before creation               │
└─────────────────────────┬───────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Stage 4: Document Update                                │
│ • PATCH request with entity IDs (not strings!)         │
│ • Updates custom fields with analysis results          │
│ • Files automatically organized on disk                │
└─────────────────────────────────────────────────────────┘
```

---

## Core Architecture Principle

**Paperless-ngx is entity-based, not string-based.**

### ❌ Wrong Approach (v13 and earlier)

```json
{
  "storage_path": "financial-tracking/magenta/2025",  // String - doesn't work!
  "correspondent": "Magenta Telekom",                 // String - doesn't work!
  "document_type": "Invoice"                         // String - doesn't work!
}
```

Result: Metadata saved to database, but **files not organized on disk**.

### ✅ Correct Approach (v14+)

```json
{
  "storage_path": 42,      // Entity ID - files actually move!
  "correspondent": 18,     // Entity ID - proper relationship!
  "document_type": 7      // Entity ID - classification works!
}
```

Result: **Files actually organized on disk** at correct paths.

---

## Entity Management

### Why Entity Creation Matters

Paperless entities must exist before you can reference them. The workflow:

1. **Checks if entity exists** (by name/template)
2. **Creates entity if needed** (via HTTP POST)
3. **Returns entity ID** for document update
4. **Deduplicates** to prevent "Magenta" and "Magenta Telekom" as separate entities

### Entity Types

#### 1. Storage Paths

**Purpose**: Control physical file organization

**Template Format**:

```variables
{category}/{correspondent}/{created_year}-{created_month}-{created_day}-{title}
```

**Examples**:

- `financial-tracking/magenta/2025-12-19-Invoice-123.pdf`
- `legal-obligations/ams/2025-12-20-Kontrolltermin.pdf`
- `reference-documents/helvetia/2025-12-18-Policy-Change.pdf`

**Created when**: First document from a correspondent in a category

#### 2. Correspondents

**Purpose**: Track document senders/issuers

**Examples**:

- Magenta Telekom (financial)
- AMS - Arbeitsmarktservice (government)
- Helvetia Versicherungen AG (insurance)

**Created when**: AI identifies a new correspondent name

#### 3. Document Types

**Purpose**: Classify documents by type

**Examples**:

- Invoice
- Contract
- Insurance Policy
- Government Notice

**Created when**: AI suggests a document type that doesn't exist

#### 4. Tags

**Purpose**: Flexible categorization

**Examples**:

- urgent
- action-required
- tax-relevant

**Safeguard**: Don't create tags that duplicate correspondent or document type

---

## Data Flow

### Complete Processing Flow

```schema
1. User uploads PDF to Paperless-ngx
   ↓
2. Paperless webhook triggers n8n workflow
   ↓
3. n8n fetches document content via API
   ↓
4. OpenAI GPT-4 analyzes document:
   - Extracts text content
   - Identifies correspondent (e.g., "Magenta Telekom")
   - Suggests document type (e.g., "Invoice")
   - Recommends tags
   - Determines category (e.g., "financial")
   ↓
5. Consolidated Processor enhances data:
   - Maps correspondent → category (e.g., financial)
   - Assesses risk level (e.g., low)
   - Determines obligation type (e.g., soft_tracking)
   - Generates storage path template
   - Calculates SLA deadline (if applicable)
   ↓
6. Entity Manager creates/matches:
   - Check: Does "Magenta Telekom" correspondent exist?
     → NO: Create it (HTTP POST) → Get ID: 18
   - Check: Does storage path "financial-tracking/magenta/..." exist?
     → NO: Create it (HTTP POST) → Get ID: 42
   ↓
7. Build Update Payload:
   {
     "correspondent": 18,
     "storage_path": 42,
     "document_type": 7,
     "custom_fields": [
       {"field": 35, "value": "0IWw2uQwjqwdrFXE"},  // Obligation Type
       {"field": 36, "value": "MgT3bokwRhrqeMR8"}   // Risk Level
     ]
   }
   ↓
8. Update Document (HTTP PATCH to Paperless API)
   ↓
9. Paperless organizes file on disk:
   /media/documents/originals/financial-tracking/magenta/2025-12-19-Invoice-123.pdf
```

---

## Metadata Safeguards

### Problem: AI May Suggest Redundant Data

**Example**:

- Document Type: "Invoice"
- AI suggests tag: "invoice" ← **REDUNDANT**

**Example**:

- Correspondent: "Magenta Telekom"
- AI suggests tag: "magenta" ← **REDUNDANT**

### Solution: Intelligent Filtering

```javascript
// Don't create tags that duplicate document type
if (documentType === "Invoice" && tag === "invoice") {
  skip(); // Redundant
}

// Don't create tags that duplicate correspondent
if (correspondent === "Magenta" && tag === "magenta") {
  skip(); // Redundant
}

// Don't create generic tags
if (['document', 'file', 'pdf', 'unknown'].includes(tag)) {
  skip(); // Too generic
}
```

---

## Custom Fields

### Purpose

Custom fields store **non-entity metadata** that doesn't fit Paperless's built-in entity system.

### Required Fields

| Field ID | Name | Type | Purpose |
| -------- | ---- | ---- | ------- |
| 34 | SLA Deadline | Date | Action deadline for obligations |
| 35 | Obligation Type | Select | hard_obligation, soft_tracking, informational, none |
| 36 | Risk Level | Select | critical, high, medium, low |
| 37 | Correspondent Category | Select | government, insurance, financial, health, commercial, technical |
| 38 | Monitoring Status | Select | active, pending, completed, archived |

### Select Field Options

Paperless select fields require **option IDs**, not label strings.

**❌ Wrong**:

```json
{"field": 35, "value": "hard_obligation"}  // String - causes API 400 error
```

**✅ Correct**:

```json
{"field": 35, "value": "YumCdzEuieiKcVDI"}  // Option ID - works!
```

The workflow maintains option ID mappings in the Consolidated Processor node.

---

## Classification Logic

### Correspondent Categories

Documents are classified into categories based on content analysis:

- **Government**: AMS, Finanzamt, courts, agencies
- **Insurance**: Helvetia, WGKK, insurance companies
- **Financial**: Banks, invoices, billing
- **Health**: Medical records, e-card, health services
- **Commercial**: General business correspondence
- **Technical**: Software, development, technical docs

### Risk Assessment

Risk level determines SLA deadlines and priority:

- **Critical**: Legal actions, enforcement, court summons (1-day SLA)
- **High**: Payment reminders, urgent notices (3-day SLA)
- **Medium**: Regular obligations (7-day SLA)
- **Low**: Informational documents (14-day SLA)

### Obligation Classification

- **Hard Obligation**: Must respond/act (government notices, payment demands)
- **Soft Tracking**: Track but no immediate action (SEPA notifications, confirmations)
- **Informational**: Reference only (policies, newsletters)
- **None**: No obligation tracking needed

---

## Evolution from v13 to v14

### v13.1 Architectural Flaws

1. **Used custom field for storage path** instead of Paperless entity
   - Result: Path stored in database but files not organized
2. **No entity creation logic** - assumed entities already existed
3. **Sent strings instead of IDs** for storage paths

### v14 Architecture Improvements

1. **Entity-based design** - all entities created dynamically
2. **HTTP Request nodes** instead of Code node API calls
3. **Deduplication logic** - prevents duplicate entities
4. **Metadata safeguards** - no redundant information
5. **Full error handling** - stops on failures, no silent errors

---

## Performance Characteristics

### Processing Time

- **AI Analysis**: 3-5 seconds (GPT-4 API call)
- **First document from correspondent**: +2 seconds (entity creation)
- **Subsequent documents**: +0.5 seconds (entity matching)
- **Total average**: 5-10 seconds per document

### Entity Reuse

- **First Magenta invoice**: Creates correspondent + storage path
- **Second Magenta invoice**: Reuses both entities (fuzzy match)
- **100th Magenta invoice**: Still reuses same entities

---

## Technical Stack

- **n8n**: Workflow automation platform
- **OpenAI GPT-4**: Document analysis and classification
- **Paperless-ngx**: Document management system (v1.10.0+)
- **HTTP REST API**: All Paperless interactions

---

## Next Steps

For implementation details, see:

- [Entity-Based Design](entity-based-design.md) - Deep dive into entity management
- [Deployment Guide](../guides/deployment.md) - How to deploy the workflow
- [Development Guide](../development/implementation-guide.md) - How to extend the workflow
