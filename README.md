# Paperless-ngx AI Document Automation

**AI-powered document processing and organization for Paperless-ngx using n8n and OpenAI GPT-4**

---

## Overview

Automate your document management with intelligent AI analysis. This n8n workflow integrates with Paperless-ngx to:

- ✅ **Analyze documents** with OpenAI GPT-4
- ✅ **Extract metadata** (correspondent, type, tags, custom fields)
- ✅ **Organize files** with intelligent storage paths
- ✅ **Create entities** dynamically (correspondents, storage paths, document types)
- ✅ **Track obligations** with SLA deadlines and risk assessment

---

## Key Features

### Intelligent Document Analysis
- **GPT-4 powered**: Extracts correspondent, document type, tags, and metadata
- **Multi-language**: Processes German and English documents
- **Confidence-based**: Only applies suggestions above configurable thresholds

### Automatic Organization
- **Entity-based architecture**: Files actually organized on disk
- **Smart storage paths**: `category/correspondent/YYYY-MM-DD-title.pdf`
- **Deduplication**: Prevents duplicate correspondents and paths
- **Metadata safeguards**: No redundant tags or information

### Advanced Classification
- **Obligation tracking**: Hard obligations, soft tracking, informational
- **Risk assessment**: Critical, high, medium, low
- **SLA deadlines**: Calculated based on risk level and obligation type
- **Category detection**: Government, insurance, financial, health, commercial, technical

---

## Architecture

```
Document Upload → Paperless Webhook → n8n Workflow
    ↓
AI Analysis (GPT-4)
    ↓
Classification & Enhancement
    ↓
Entity Management (Create/Match)
    ├─ Correspondents
    ├─ Storage Paths
    ├─ Document Types
    └─ Tags
    ↓
Document Update (PATCH with entity IDs)
    ↓
Files Organized on Disk
```

For detailed architecture information, see [docs/architecture/overview.md](docs/architecture/overview.md).

---

## Quick Start

### Prerequisites
- Paperless-ngx v1.10.0+
- n8n v1.0.0+
- OpenAI API key with GPT-4 access

### Installation

1. **Clone repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/paperless-n8n-ai-automation.git
   cd paperless-n8n-ai-automation
   ```

2. **Configure environment**
   ```bash
   cp .env.paperless.example .env.paperless
   # Edit .env.paperless with your Paperless API token and URL
   ```

3. **Set up Paperless custom fields**
   ```bash
   ./scripts/setup/create_custom_fields.sh
   ./scripts/setup/create_select_fields.sh
   ```

4. **Import workflow to n8n**
   - Open n8n: `http://localhost:5678`
   - Import: `workflows/current/paperless-ai-automation.json`
   - Configure credentials (Paperless API + OpenAI)
   - Activate workflow

5. **Test with a document**
   - Upload any PDF to Paperless-ngx
   - Watch n8n execution logs
   - Verify file organized correctly on disk

For detailed setup instructions, see [docs/guides/setup.md](docs/guides/setup.md).

---

## Repository Structure

```
paperless-n8n/
├── README.md                 # This file
├── CLAUDE.md                 # AI assistant instructions
├── .gitignore
├── .env.paperless.example    # Environment template
│
├── docs/                     # Documentation
│   ├── architecture/
│   │   └── overview.md      # System architecture
│   ├── guides/
│   │   ├── setup.md         # Initial setup
│   │   └── deployment.md    # Deployment guide
│   └── development/
│       └── (future)         # Development docs
│
├── workflows/                # n8n workflows
│   ├── current/
│   │   └── paperless-ai-automation.json  # Current version
│   └── archive/             # Previous versions
│
├── scripts/                  # Utility scripts
│   ├── setup/               # Setup scripts
│   └── workflow-builders/   # Workflow generation
│
└── src/                      # Source code
    └── entity_manager_node.js
```

---

## Example Results

### Before (Manual Organization)
```
originals/
└── 2025/
    └── 12/
        └── document_123.pdf  ❌ No structure
```

### After (AI Organization)
```
originals/
├── financial-tracking/
│   ├── magenta/
│   │   └── 2025-12-19-Invoice-907253181225.pdf  ✅
│   └── helvetia/
│       └── 2025-12-18-Insurance-Premium.pdf  ✅
└── legal-obligations/
    └── ams/
        └── 2025-12-20-Kontrolltermin-Letter.pdf  ✅
```

### Metadata Extracted
- **Correspondent**: Magenta Telekom (created automatically)
- **Document Type**: Invoice
- **Storage Path**: `financial-tracking/magenta/{created_year}-{created_month}-{created_day}-{title}`
- **Custom Fields**:
  - Risk Level: Low
  - Obligation Type: Soft Tracking
  - Correspondent Category: Financial
  - Monitoring Status: Active

---

## Supported Document Types

- **Government**: AMS letters, tax office, court documents
- **Insurance**: Policies, premium notices, claims
- **Financial**: Invoices, bank statements, bills
- **Health**: Medical records, e-card documents
- **Commercial**: Business correspondence, contracts
- **Technical**: Software licenses, technical documentation

---

## Custom Fields

The workflow uses 5 custom fields in Paperless-ngx:

| Field | Type | Purpose |
|-------|------|---------|
| SLA Deadline | Date | Action deadline for obligations |
| Obligation Type | Select | hard_obligation, soft_tracking, informational, none |
| Risk Level | Select | critical, high, medium, low |
| Correspondent Category | Select | government, insurance, financial, health, commercial, technical |
| Monitoring Status | Select | active, pending, completed, archived |

---

## Documentation

- **[Setup Guide](docs/guides/setup.md)** - Initial configuration
- **[Deployment Guide](docs/guides/deployment.md)** - Workflow deployment
- **[Architecture Overview](docs/architecture/overview.md)** - Technical details
- **[CLAUDE.md](CLAUDE.md)** - Project instructions for AI assistants

---

## Technology Stack

- **[Paperless-ngx](https://docs.paperless-ngx.com/)** - Document management system
- **[n8n](https://n8n.io/)** - Workflow automation platform
- **[OpenAI GPT-4](https://openai.com/gpt-4)** - AI document analysis
- **Python** - Utility scripts
- **JavaScript** - Workflow logic

---

## Performance

- **Processing time**: 5-10 seconds per document
- **AI analysis**: 3-5 seconds (GPT-4 API)
- **Entity creation**: 1-2 seconds (first time per correspondent)
- **Entity reuse**: <1 second (subsequent documents)

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly
4. Submit a pull request

---

## License

MIT License - see LICENSE file for details

---

## Support

For issues and questions:
- Check [docs/guides/deployment.md](docs/guides/deployment.md) troubleshooting section
- Review [docs/architecture/overview.md](docs/architecture/overview.md) for technical details
- Open an issue on GitHub

---

## Acknowledgments

- **Paperless-ngx team** - Excellent document management system
- **n8n community** - Powerful workflow automation platform
- **OpenAI** - GPT-4 AI capabilities

---

**Ready to automate your documents?** Start with the [Setup Guide](docs/guides/setup.md)!
