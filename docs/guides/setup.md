# Initial Setup Guide

This guide covers the one-time setup required before deploying the workflow.

---

## Prerequisites

### System Requirements

- **Paperless-ngx**: v1.10.0 or higher
- **n8n**: v1.0.0 or higher
- **OpenAI API**: Account with GPT-4 access
- **Bash/curl**: For running setup scripts (Windows: Git Bash or WSL)

### Access Requirements

- Paperless-ngx admin account
- n8n access with workflow creation permissions
- OpenAI API key

---

## Step 1: Create Environment Configuration

Create a `.env.paperless` file in your project root:

```bash
cp .env.paperless.example .env.paperless
```

Edit `.env.paperless` with your actual values:

```bash
# Paperless API Configuration
PAPERLESS_TOKEN="your_admin_api_token_here"
PAPERLESS_URL_PUBLIC="https://your-paperless-domain.com"
PAPERLESS_URL_LAN="http://192.168.1.100"  # Optional: LAN access
```

### Generating the API Token

1. Log into Paperless-ngx web interface
2. Go to **Settings** → **API Tokens**
3. Click **Create Token**
4. **Important**: Use your **admin** account (workflow needs permissions to create entities)
5. Copy the token to `.env.paperless`

**Why admin?** The workflow creates correspondents, storage paths, document types, and tags - operations that require admin permissions.

---

## Step 2: Create Custom Fields

The workflow requires 5 custom fields in Paperless-ngx.

### Option A: Automated Script (Recommended)

```bash
# Make script executable
chmod +x scripts/setup/create_custom_fields.sh
chmod +x scripts/setup/create_select_fields.sh

# Run scripts
./scripts/setup/create_custom_fields.sh
./scripts/setup/create_select_fields.sh
```

### Option B: Manual Creation

#### Field 1: SLA Deadline

1. In Paperless-ngx: **Settings** → **Custom Fields** → **Add Field**
2. Configure:
   - **Name**: SLA Deadline
   - **Data Type**: Date
3. Click **Save**
4. **Note the Field ID** (e.g., 34)

#### Field 2: Obligation Type

1. **Name**: Obligation Type
2. **Data Type**: Select
3. **Options**: Add these options (note the auto-generated IDs):
   - hard_obligation
   - soft_tracking
   - informational
   - none

#### Field 3: Risk Level

1. **Name**: Risk Level
2. **Data Type**: Select
3. **Options**:
   - critical
   - high
   - medium
   - low

#### Field 4: Correspondent Category

1. **Name**: Correspondent Category
2. **Data Type**: Select
3. **Options**:
   - government
   - insurance
   - financial
   - health
   - commercial
   - technical

#### Field 5: Monitoring Status

1. **Name**: Monitoring Status
2. **Data Type**: Select
3. **Options**:
   - active
   - pending
   - completed
   - archived

### Update Field IDs in Workflow

After creating custom fields, you need to update the workflow with your actual field IDs.

1. Get your field IDs:

```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  https://your-paperless-domain.com/api/custom_fields/ | python -m json.tool
```

1. In the workflow file `workflows/current/paperless-ai-automation.json`, find the "Consolidated Processor" node

2. Update the `FIELD_IDS` constant:

```javascript
const FIELD_IDS = {
  SLA_DEADLINE: 34,           // Your ID here
  OBLIGATION_TYPE: 35,        // Your ID here
  RISK_LEVEL: 36,            // Your ID here
  CORRESPONDENT_CATEGORY: 37, // Your ID here
  MONITORING_STATUS: 38      // Your ID here
};
```

1. Update the `OPTION_ID_MAPS` with your option IDs:

```javascript
const OPTION_ID_MAPS = {
  OBLIGATION_TYPE: {
    'hard_obligation': 'YOUR_OPTION_ID',
    'soft_tracking': 'YOUR_OPTION_ID',
    // ...
  },
  // ...
};
```

To get option IDs, check the API response from the custom fields endpoint above.

---

## Step 3: Configure n8n

### Install n8n

If not already installed:

```bash
# Via npm
npm install -g n8n

# Via Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### Access n8n

Open `http://localhost:5678` in your browser.

### Create Credentials

You'll need two credential sets (detailed in [deployment.md](deployment.md)):

1. **PaperlessAPI** - HTTP Header Auth for Paperless
2. **OpenAI account** - OpenAI API key

---

## Step 4: Configure Paperless Webhook

The workflow is triggered when documents are uploaded to Paperless.

### In Paperless-ngx Settings

1. Go to **Settings** → **Webhooks**
2. Click **Add Webhook**
3. Configure:
   - **Webhook URL**: `http://your-n8n-host:5678/webhook/paperless-document-added`
   - **Trigger Events**: Select "Document Added"
   - **Method**: POST
   - **Content Type**: application/json
4. Click **Save**

### Security Considerations

**For Production**:

- Use HTTPS for webhook URL
- Add authentication token validation in n8n
- Restrict network access to n8n instance

**For Testing**:

- HTTP with localhost is fine
- Ensure firewall allows Paperless → n8n communication

---

## Step 5: Verify Setup

### Test API Access

```bash
# Source environment file
source .env.paperless

# Test API connectivity
curl -H "Authorization: Token $PAPERLESS_TOKEN" \
  "$PAPERLESS_URL_PUBLIC/api/documents/" | head -20

# Test custom fields exist
curl -H "Authorization: Token $PAPERLESS_TOKEN" \
  "$PAPERLESS_URL_PUBLIC/api/custom_fields/"
```

Expected: Should return JSON responses without errors.

### Test n8n Access

1. Open `http://localhost:5678`
2. Create a new workflow
3. Add an HTTP Request node
4. Test Paperless API connectivity

---

## Step 6: Deploy Workflow

Once setup is complete, proceed to [deployment.md](deployment.md) for workflow deployment instructions.

---

## Troubleshooting

### "Permission denied" when running scripts

```bash
# Make scripts executable
chmod +x scripts/setup/*.sh
```

### "API token invalid"

1. Verify token in `.env.paperless` is correct
2. Check token hasn't expired (Paperless → Settings → API Tokens)
3. Ensure you're using an **admin** token, not a consumer token

### Custom fields not created

1. Check Paperless logs: `docker logs paperless-ngx`
2. Verify API token has admin permissions
3. Try manual creation via Paperless web interface

### n8n can't connect to Paperless

1. Verify `PAPERLESS_URL_PUBLIC` is accessible from n8n host
2. Check firewall rules
3. For Docker setups, ensure containers are on same network
4. Test with curl from n8n host: `curl https://your-paperless-domain.com/api/`

---

## Security Best Practices

1. **Never commit `.env.paperless`** - Contains sensitive tokens
2. **Use HTTPS** for production Paperless instances
3. **Rotate API tokens** periodically
4. **Restrict n8n access** - Don't expose to public internet
5. **Monitor OpenAI costs** - Set up billing alerts

---

## Next Steps

After completing setup:

1. Review [Architecture Overview](../architecture/overview.md)
2. Deploy the workflow using [Deployment Guide](deployment.md)
3. Test with sample documents
4. Configure monitoring and alerts

---

## Support Files

- [.env.paperless.example](.env.paperless.example) - Template environment file
- [scripts/setup/create_custom_fields.sh](../../scripts/setup/create_custom_fields.sh) - Automated field creation
- [scripts/setup/create_select_fields.sh](../../scripts/setup/create_select_fields.sh) - Select field options
