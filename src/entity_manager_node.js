/**
 * Entity Manager Node - v14
 * Manages Paperless-ngx entities with deduplication, fuzzy matching, and safeguards
 *
 * This node creates/matches:
 * - Storage paths (with template-based organization)
 * - Correspondents (with fuzzy matching)
 * - Document types (with confidence threshold)
 * - Tags (with redundancy filtering)
 */

// === CONFIGURATION ===
const PAPERLESS_API_URL = 'https://your-paperless-domain.com/api';
const PAPERLESS_TOKEN = 'YOUR_PAPERLESS_API_TOKEN_HERE';

// === INPUT DATA ===
// Expected from previous node (Consolidated Processor):
const classification = $input.first().json;

const {
  correspondent_name,
  correspondent_category,
  document_type_name,
  document_type_confidence,
  suggested_tags,
  obligation_type,
  risk_level,
  storage_category  // e.g., 'legal-obligations', 'financial-tracking'
} = classification;

// === HELPER FUNCTIONS ===

/**
 * Make HTTP request to Paperless API
 */
async function apiRequest(method, endpoint, body = null) {
  const options = {
    method: method,
    url: `${PAPERLESS_API_URL}${endpoint}`,
    headers: {
      'Authorization': `Token ${PAPERLESS_TOKEN}`,
      'Content-Type': 'application/json'
    },
    json: true  // Automatically parse JSON responses
  };

  if (body) {
    options.body = body;
  }

  try {
    const response = await this.helpers.httpRequest(options);
    return response;
  } catch (error) {
    console.error(`[API ERROR] ${method} ${endpoint}:`, error.message);
    throw error;
  }
}

/**
 * Calculate Jaccard similarity between two strings
 */
function calculateSimilarity(str1, str2) {
  if (!str1 || !str2) return 0;

  const words1 = new Set(str1.toLowerCase().split(/\s+/));
  const words2 = new Set(str2.toLowerCase().split(/\s+/));

  const intersection = new Set([...words1].filter(x => words2.has(x)));
  const union = new Set([...words1, ...words2]);

  return intersection.size / union.size;
}

/**
 * Capitalize words in a string
 */
function capitalizeWords(str) {
  return str.split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Generate tag color based on category
 */
function generateTagColor(tagName) {
  const categories = {
    'legal|court|law|regulation|compliance': '#DC2626',
    'government|ams|tax|finanzamt': '#DC2626',
    'invoice|payment|bill|rechnung': '#EA580C',
    'insurance|versicherung': '#D97706',
    'bank|banking|sepa': '#F59E0B',
    'urgent|mahnung|deadline|reminder': '#EF4444',
    'overdue|late': '#DC2626',
    'paid|completed|done': '#10B981',
    'pending|waiting|open': '#3B82F6',
    'cancelled|invalid': '#6B7280',
    'health|medical|doctor': '#06B6D4',
    'utility|energie|strom|gas': '#8B5CF6',
    'communication|telekom|internet': '#EC4899',
    'transport|travel|ticket': '#14B8A6'
  };

  for (const [pattern, color] of Object.entries(categories)) {
    const regex = new RegExp(pattern, 'i');
    if (regex.test(tagName)) {
      return color;
    }
  }

  return '#6B7280'; // Default gray
}

// === ENTITY MANAGEMENT FUNCTIONS ===

/**
 * Get or create storage path entity
 */
async function getOrCreateStoragePath(category, correspondentName) {
  console.log(`[STORAGE PATH] Processing: ${category} / ${correspondentName}`);

  // Validate category
  const validCategories = ['legal-obligations', 'financial-tracking', 'reference-documents'];
  if (!validCategories.includes(category)) {
    console.error(`[STORAGE PATH] Invalid category: ${category}`);
    return null;
  }

  // Generate correspondent slug
  let correspondentSlug = correspondentName
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

  // Safeguard: Check for generic names
  if (['unknown', 'null', 'n-a', ''].includes(correspondentSlug)) {
    console.warn('[STORAGE PATH] Generic correspondent name, using "unknown"');
    correspondentSlug = 'unknown';
  }

  // Build path template
  const pathTemplate = `${category}/${correspondentSlug}/{created_year}/{created_month_name}`;
  const name = `${category} - ${correspondentName}`;

  // Check if storage path exists
  const allPaths = await apiRequest('GET', '/storage_paths/');

  const existing = allPaths.results.find(sp => sp.path === pathTemplate);
  if (existing) {
    console.log(`[STORAGE PATH] Exists: ${existing.name} (ID: ${existing.id})`);
    return existing.id;
  }

  // Create new storage path
  console.log(`[STORAGE PATH] Creating: ${name}`);
  const newPath = await apiRequest('POST', '/storage_paths/', {
    name: name,
    path: pathTemplate,
    matching_algorithm: 0  // Manual assignment only
  });

  console.log(`[STORAGE PATH] Created ID: ${newPath.id}`);
  return newPath.id;
}

/**
 * Get or create correspondent with fuzzy matching
 */
async function getOrCreateCorrespondent(name) {
  if (!name) return null;

  const normalizedName = name.trim();

  // Safeguard: Reject generic names
  const genericNames = ['unknown', 'null', 'n/a', 'n.a.', ''];
  if (genericNames.includes(normalizedName.toLowerCase()) || normalizedName.length < 2) {
    console.log('[CORRESPONDENT] Skipped: Generic or too short');
    return null;
  }

  console.log(`[CORRESPONDENT] Processing: ${normalizedName}`);

  // Get all correspondents for fuzzy matching
  const allCorrespondents = await apiRequest('GET', '/correspondents/?page_size=1000');

  // Fuzzy match (90% threshold)
  for (const corr of allCorrespondents.results) {
    const similarity = calculateSimilarity(normalizedName, corr.name);
    if (similarity > 0.9) {
      console.log(`[CORRESPONDENT] Matched: "${normalizedName}" → "${corr.name}" (${(similarity * 100).toFixed(0)}%)`);
      return corr.id;
    }
  }

  // Create new correspondent
  console.log(`[CORRESPONDENT] Creating: ${normalizedName}`);
  const newCorr = await apiRequest('POST', '/correspondents/', {
    name: normalizedName,
    matching_algorithm: 6  // Automatic
  });

  console.log(`[CORRESPONDENT] Created ID: ${newCorr.id}`);
  return newCorr.id;
}

/**
 * Get or create document type
 */
async function getOrCreateDocumentType(name, confidence) {
  if (!name) return null;

  // Safeguard: Confidence threshold
  if (confidence < 0.7) {
    console.log(`[DOCUMENT TYPE] Skipped: Low confidence (${confidence})`);
    return null;
  }

  const normalizedName = name.trim();

  // Safeguard: Reject generic names
  const genericTypes = ['unknown', 'document', 'file', 'other', 'misc'];
  if (genericTypes.includes(normalizedName.toLowerCase())) {
    console.log('[DOCUMENT TYPE] Skipped: Generic name');
    return null;
  }

  console.log(`[DOCUMENT TYPE] Processing: ${normalizedName}`);

  // Check if exists (case-insensitive)
  const allTypes = await apiRequest('GET', '/document_types/');

  const existing = allTypes.results.find(
    dt => dt.name.toLowerCase() === normalizedName.toLowerCase()
  );

  if (existing) {
    console.log(`[DOCUMENT TYPE] Exists: ${existing.name} (ID: ${existing.id})`);
    return existing.id;
  }

  // Safeguard: Limit total document types
  if (allTypes.count >= 20) {
    console.warn('[DOCUMENT TYPE] Limit reached (20), skipping creation');
    return null;
  }

  // Create new document type
  const capitalizedName = capitalizeWords(normalizedName);
  console.log(`[DOCUMENT TYPE] Creating: ${capitalizedName}`);

  const newType = await apiRequest('POST', '/document_types/', {
    name: capitalizedName,
    matching_algorithm: 6  // Automatic
  });

  console.log(`[DOCUMENT TYPE] Created ID: ${newType.id}`);
  return newType.id;
}

/**
 * Check if tag is redundant with document type
 */
function isRedundantWithDocumentType(tag, docTypeName) {
  if (!docTypeName) return false;

  const tagLower = tag.toLowerCase();
  const docTypeLower = docTypeName.toLowerCase();

  return tagLower.includes(docTypeLower) || docTypeLower.includes(tagLower);
}

/**
 * Check if tag is redundant with correspondent
 */
function isRedundantWithCorrespondent(tag, correspondentName) {
  if (!correspondentName) return false;

  const tagLower = tag.toLowerCase();
  const corrLower = correspondentName.toLowerCase();

  return corrLower.includes(tagLower) || tagLower.includes(corrLower);
}

/**
 * Check if tag is generic/meaningless
 */
function isGenericTag(tag) {
  const genericTags = [
    'document', 'file', 'pdf', 'scan', 'scanned',
    'unknown', 'other', 'misc', 'general'
  ];

  return genericTags.includes(tag.toLowerCase());
}

/**
 * Get or create tags with safeguards
 */
async function getOrCreateTags(suggestedTags, docTypeName, correspondentName) {
  if (!suggestedTags || suggestedTags.length === 0) return [];

  console.log(`[TAGS] Processing: ${suggestedTags.length} suggested tags`);

  const tagIds = [];

  for (const tagName of suggestedTags) {
    const normalizedTag = tagName.trim();

    // Safeguard: Length check
    if (normalizedTag.length < 2 || normalizedTag.length > 50) {
      console.log(`[TAGS] Skipped: Invalid length (${normalizedTag})`);
      continue;
    }

    // Safeguard: Generic tags
    if (isGenericTag(normalizedTag)) {
      console.log(`[TAGS] Skipped: Generic (${normalizedTag})`);
      continue;
    }

    // Safeguard: Redundancy with document type
    if (isRedundantWithDocumentType(normalizedTag, docTypeName)) {
      console.log(`[TAGS] Skipped: Redundant with doc type (${normalizedTag})`);
      continue;
    }

    // Safeguard: Redundancy with correspondent
    if (isRedundantWithCorrespondent(normalizedTag, correspondentName)) {
      console.log(`[TAGS] Skipped: Redundant with correspondent (${normalizedTag})`);
      continue;
    }

    // Check if tag exists
    const allTags = await apiRequest('GET', '/tags/');

    const existing = allTags.results.find(
      t => t.name.toLowerCase() === normalizedTag.toLowerCase()
    );

    if (existing) {
      console.log(`[TAGS] Exists: ${existing.name} (ID: ${existing.id})`);
      tagIds.push(existing.id);
      continue;
    }

    // Create new tag
    const capitalizedTag = capitalizeWords(normalizedTag);
    const tagColor = generateTagColor(normalizedTag);

    console.log(`[TAGS] Creating: ${capitalizedTag} (${tagColor})`);

    const newTag = await apiRequest('POST', '/tags/', {
      name: capitalizedTag,
      color: tagColor,
      matching_algorithm: 6  // Automatic
    });

    console.log(`[TAGS] Created ID: ${newTag.id}`);
    tagIds.push(newTag.id);
  }

  // Safeguard: Maximum 10 tags per document
  if (tagIds.length > 10) {
    console.warn(`[TAGS] Limiting to 10 tags (had ${tagIds.length})`);
    return tagIds.slice(0, 10);
  }

  console.log(`[TAGS] Final count: ${tagIds.length} tags`);
  return tagIds;
}

// === MAIN PROCESSING ===

console.log('=== Entity Manager v14 ===');
console.log(`Processing document with correspondent: ${correspondent_name}`);

// Entity creation log for audit trail
const entityLog = [];

try {
  // 1. Storage Path
  let storagePathId = null;
  if (storage_category && correspondent_name) {
    storagePathId = await getOrCreateStoragePath(storage_category, correspondent_name);
    entityLog.push({
      entity: 'storage_path',
      action: storagePathId ? 'created_or_matched' : 'skipped',
      id: storagePathId,
      template: `${storage_category}/${correspondent_name}`
    });
  }

  // 2. Correspondent
  let correspondentId = null;
  if (correspondent_name) {
    correspondentId = await getOrCreateCorrespondent(correspondent_name);
    entityLog.push({
      entity: 'correspondent',
      action: correspondentId ? 'created_or_matched' : 'skipped',
      id: correspondentId,
      name: correspondent_name
    });
  }

  // 3. Document Type
  let documentTypeId = null;
  if (document_type_name && document_type_confidence) {
    documentTypeId = await getOrCreateDocumentType(document_type_name, document_type_confidence);
    entityLog.push({
      entity: 'document_type',
      action: documentTypeId ? 'created_or_matched' : 'skipped',
      id: documentTypeId,
      name: document_type_name,
      confidence: document_type_confidence
    });
  }

  // 4. Tags
  let tagIds = [];
  if (suggested_tags && suggested_tags.length > 0) {
    tagIds = await getOrCreateTags(suggested_tags, document_type_name, correspondent_name);
    entityLog.push({
      entity: 'tags',
      action: 'processed',
      count: tagIds.length,
      ids: tagIds
    });
  }

  // === OUTPUT ===
  return {
    json: {
      // Entity IDs for document update
      storage_path_id: storagePathId,
      correspondent_id: correspondentId,
      document_type_id: documentTypeId,
      tag_ids: tagIds,

      // Original classification data (pass through)
      classification: classification,

      // Audit trail
      entity_creation_log: entityLog,

      // Timestamp
      processed_at: new Date().toISOString()
    }
  };

} catch (error) {
  console.error('[ENTITY MANAGER ERROR]:', error);
  return {
    json: {
      error: true,
      error_message: error.message,
      entity_creation_log: entityLog,
      processed_at: new Date().toISOString()
    }
  };
}
