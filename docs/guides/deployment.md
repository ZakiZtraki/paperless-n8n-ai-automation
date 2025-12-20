# Deployment Guide

**Status**: ✅ Ready for Production
**Workflow File**: `workflows/current/paperless-ai-automation.json`
**Deployment Time**: ~15 minutes

---

## Overview

This guide walks you through deploying the Paperless-ngx AI Document Automation workflow to your n8n instance.

## What You're Deploying

The workflow provides:
- ✅ **AI-powered document analysis** using OpenAI GPT-4
- ✅ **Automatic correspondent detection** and entity creation
- ✅ **Smart storage path generation** with correspondent organization
- ✅ **Custom field population** (SLA deadlines, risk levels, obligation types)
- ✅ **Entity-based architecture** for proper file organization

---

## Prerequisites

### Required Software

- **Paperless-ngx** (v1.10.0+)
- **n8n** (v1.0.0+)
- **OpenAI API key** (with GPT-4 access)

### Required Paperless-ngx Setup

1. **Custom Fields Created**: 5 required fields (see [setup.md](setup.md))
2. **API Token Generated**: Admin-level token for entity creation
3. **Webhook Configured**: Points to your n8n instance

---

## Deployment Steps

### Step 1: Import Workflow

1. Open n8n web interface: `http://localhost:5678`
2. Navigate to **Workflows** → **Import from File**
3. Select: `workflows/current/paperless-ai-automation.json`
4. Click **Import**

### Step 2: Configure Credentials

The workflow requires two credential sets:

#### PaperlessAPI Credential

1. In n8n, go to **Credentials** → **Create New**
2. Select **HTTP Header Auth**
3. Configure:
   - **Name**: `PaperlessAPI`
   - **Header Name**: `Authorization`
   - **Header Value**: `Token YOUR_PAPERLESS_API_TOKEN`
   - **Base URL**: `https://your-paperless-domain.com/api`

#### OpenAI Credential

1. Go to **Credentials** → **Create New**
2. Select **OpenAI**
3. Configure:
   - **Name**: `OpenAI account`
   - **API Key**: Your OpenAI API key
   - **Organization ID**: (optional)

### Step 3: Verify Node Configuration

Check these nodes have correct credentials:

**HTTP Nodes** (should use PaperlessAPI):
- Check Correspondent Exists
- Create Correspondent
- Check Storage Paths
- Create Storage Path
- Fetch Document Content
- Update Document

**AI Tool Nodes** (should use PaperlessAPI):
- get_document_types
- get_custom_fields
- get_tags
- get_correspondents

**OpenAI Node** (should use OpenAI account):
- AI Document Analyzer

### Step 4: Update Configuration

In the **Consolidated Processor** node, update these constants if your custom field IDs differ:

```javascript
const FIELD_IDS = {
  SLA_DEADLINE: 34,           // Update if different
  OBLIGATION_TYPE: 35,        // Update if different
  RISK_LEVEL: 36,            // Update if different
  CORRESPONDENT_CATEGORY: 37, // Update if different
  MONITORING_STATUS: 38      // Update if different
};
```

To find your field IDs:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  https://your-paperless-domain.com/api/custom_fields/
```

### Step 5: Activate Workflow

1. Click **Active** toggle (top-right)
2. Verify green "Active" status
3. Check n8n logs for any startup errors

---

## Testing

### Test Document 1: Simple Invoice

**Upload**: Any invoice PDF to Paperless-ngx

**Expected Results**:
- Correspondent auto-detected and created
- Storage path: `financial-tracking/[correspondent]/YYYY-MM-DD-[title].pdf`
- Custom fields populated
- File organized on disk

**Verification**:
```bash
# Check file location (Linux)
ls -lR /path/to/paperless/media/documents/originals/financial-tracking/

# Check file location (Windows)
dir "C:\path\to\paperless\media\documents\originals\financial-tracking" /s

# Check API
curl -H "Authorization: Token YOUR_TOKEN" \
  https://your-paperless-domain.com/api/correspondents/
```

### Test Document 2: Government Letter

**Upload**: Government correspondence (AMS, tax office, etc.)

**Expected Results**:
- Correspondent: Government agency name
- Storage path: `legal-obligations/[agency]/YYYY-MM-DD-[title].pdf`
- Custom fields: Risk Level=High, Obligation Type=Hard Obligation
- SLA deadline calculated

### Test Document 3: Insurance Document

**Upload**: Insurance policy or notice

**Expected Results**:
- Correspondent: Insurance company name
- Storage path: `financial-tracking/insurance/[company]/YYYY-MM-DD-[title].pdf`
- Custom fields populated appropriately

---

## Verification Checklist

After each test document:

### In n8n
- [ ] Workflow executes without errors
- [ ] All nodes show green checkmarks
- [ ] Check "Final Processing Report" output shows success
- [ ] No error nodes triggered

### In Paperless-ngx
- [ ] Document has correct correspondent assigned
- [ ] Document has correct storage path assigned
- [ ] Custom fields populated (view document details)
- [ ] Document type assigned (if confidence > 0.6)

### On Disk (CRITICAL)
- [ ] File actually moved to correct folder
- [ ] Filename follows pattern: `YYYY-MM-DD-[title].pdf`
- [ ] Folder structure: `[category]/[correspondent]/[filename]`

---

## Troubleshooting

### Workflow Shows Error

**Error: "Failed to get correspondent ID"**
- **Cause**: API call to check/create correspondent failed
- **Fix**:
  1. Verify Paperless API token is valid
  2. Check "Check Correspondent Exists" node output
  3. Ensure correspondent name is not empty/invalid

**Error: "Failed to get storage path ID"**
- **Cause**: Storage path creation failed
- **Fix**:
  1. Check "Generate Storage Path" output - is template valid?
  2. Verify template uses Paperless placeholders correctly
  3. Check "Create Storage Path" HTTP response

**Error: "OpenAI API error"**
- **Cause**: OpenAI API key invalid or rate limit exceeded
- **Fix**:
  1. Verify API key in credentials
  2. Check OpenAI account has credits
  3. Review OpenAI usage limits

### Files Not Organized on Disk

**Symptom**: Workflow succeeds but files stay in default location

**Common Causes**:
1. **Document uploaded before storage path created**
   - **Fix**: Re-upload the document (Paperless only organizes new uploads)

2. **Storage path not in update payload**
   - **Fix**: Check "Build Update Payload" node output for `storage_path` field

3. **Paperless permissions issue**
   - **Fix**: Check Paperless logs: `docker logs paperless-ngx | grep storage`

### Correspondent Recognized but Not Assigned

**Symptom**: AI recognizes "Apple" but correspondent field is empty

**Cause**: Entity creation failed
**Fix**:
1. Check "Create Correspondent" node - did HTTP POST succeed?
2. Verify correspondent name is valid (not "Unknown" or empty)
3. Check Paperless API permissions

---

## Performance Expectations

### Processing Time
- **AI Analysis**: 3-5 seconds
- **Entity Creation**: 1-2 seconds (first time)
- **Entity Matching**: < 1 second (subsequent)
- **Document Update**: < 1 second
- **Total**: 5-10 seconds per document

### Entity Reuse
- **First invoice from Magenta**: Creates entities (~2s overhead)
- **Subsequent invoices**: Reuses entities (~0.5s overhead)

---

## Production Deployment

Once testing succeeds:

1. **Monitor for 1 week**
   - Check n8n execution logs daily
   - Verify all documents process correctly
   - Watch for any error patterns

2. **Process existing documents**
   - Re-upload documents from root folder to organize them
   - Process in small batches (10-20 at a time)
   - Verify organization after each batch

3. **Set up monitoring**
   - Configure n8n error notifications
   - Monitor OpenAI API usage/costs
   - Track Paperless storage growth

---

## Architecture

For technical details about how the workflow operates, see:
- [Architecture Overview](../architecture/overview.md)
- [Entity-Based Design](../architecture/entity-based-design.md)

---

## Next Steps

See the [Development Guide](../development/implementation-guide.md) for:
- Adding tag creation
- Adding document type creation
- Implementing fuzzy correspondent matching
- Advanced error handling

---

**Ready to deploy?** Import the workflow, configure credentials, test with 3 documents, then activate for production use.
