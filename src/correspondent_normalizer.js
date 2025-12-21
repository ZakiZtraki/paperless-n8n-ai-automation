/**
 * Correspondent Name Normalization for Paperless-ngx
 *
 * Purpose: Normalize company names to prevent duplicate entities
 * Example: "Boehringer Ingelheim RCV & Co KG" → "Boehringer Ingelheim"
 *
 * Usage in n8n Code node:
 * - Input: items[0].json.correspondent_name (raw from AI)
 * - Output: items[0].json.company_canonical (normalized)
 */

// Common legal suffixes (extend as needed)
const LEGAL_SUFFIXES = [
  'gmbh', 'kg', 'kgaa', 'ag', 'se',
  'llc', 'inc', 'corp', 'corporation',
  'ltd', 'limited', 'plc',
  's\\.a\\.?', 's\\.r\\.l\\.?', 's\\.p\\.a\\.?',
  'bv', 'nv', 'oy', 'ab', 'aps', 'as',
  'co', 'company', 'rcv',
  // German specific
  'ohg', 'gbr', 'ev', 'eg',
  // Austrian specific
  'ges\\.m\\.b\\.h\\.?', 'stg',
  // Government/Municipality markers
  'magistrat', 'stadt', 'gemeinde', 'bezirk'
];

// Known aliases / exceptions (highest priority)
// Use this to handle special cases that don't follow standard rules
const ALIASES = {
  'boehringer ingelheim rcv & co': 'Boehringer Ingelheim',
  'boehringer ingelheim rcv': 'Boehringer Ingelheim',
  'magistrat wien-mba f.d. 21. bezirk': 'Magistrat Wien',
  'magistrat wien': 'Magistrat Wien',
  'wiener linien gmbh & co': 'Wiener Linien',
  'magenta telekom': 'Magenta Telekom',
  'magenta': 'Magenta Telekom'  // Expand abbreviations
};

/**
 * Normalize correspondent name to canonical form
 * @param {string} name - Raw correspondent name from AI
 * @returns {string} Normalized canonical name
 */
function normalizeCorrespondent(name) {
  if (!name || typeof name !== 'string') {
    return 'Unknown';
  }

  // Trim whitespace
  let n = name.trim();

  // Convert to lowercase for processing
  const lowerName = n.toLowerCase();

  // Apply alias override first (highest priority)
  for (const [key, value] of Object.entries(ALIASES)) {
    if (lowerName.startsWith(key)) {
      console.log(`Correspondent normalization: "${name}" → "${value}" (alias match)`);
      return value;
    }
  }

  // Remove punctuation and connectors
  n = n.replace(/[.,]/g, ' ')                    // Remove periods and commas
       .replace(/\s*&\s*/g, ' ')                 // Remove ampersands
       .replace(/\s+and\s+/gi, ' ')              // Remove "and"
       .replace(/\s+/g, ' ')                     // Collapse whitespace
       .trim();

  // Strip legal suffixes
  const suffixRe = new RegExp(
    '\\b(' + LEGAL_SUFFIXES.join('|') + ')\\b',
    'gi'
  );
  n = n.replace(suffixRe, '')
       .replace(/\s+/g, ' ')
       .trim();

  // Remove trailing connectors left behind
  n = n.replace(/\s*[&+]\s*$/g, '').trim();

  // Title-case for proper presentation
  n = n.replace(/\b\w/g, c => c.toUpperCase());

  console.log(`Correspondent normalization: "${name}" → "${n}"`);

  return n || 'Unknown';
}

/**
 * Generate slug from canonical name for storage paths
 * @param {string} name - Canonical correspondent name
 * @returns {string} URL-safe slug
 */
function generateCorrespondentSlug(name) {
  return name
    .toLowerCase()
    .normalize('NFD')                             // Decompose accented characters
    .replace(/[\u0300-\u036f]/g, '')              // Remove diacritics
    .replace(/[^a-z0-9]+/g, '-')                  // Replace non-alphanumeric with hyphens
    .replace(/^-+|-+$/g, '')                      // Remove leading/trailing hyphens
    .substring(0, 50);                            // Limit length
}

// Export for use in n8n Code node
module.exports = {
  normalizeCorrespondent,
  generateCorrespondentSlug,
  ALIASES,
  LEGAL_SUFFIXES
};

/**
 * Example n8n Code Node Usage:
 *
 * // Copy the normalizeCorrespondent and generateCorrespondentSlug functions above
 *
 * const data = $input.first().json;
 * const rawName = data.correspondent_name || 'Unknown';
 *
 * const canonical = normalizeCorrespondent(rawName);
 * const slug = generateCorrespondentSlug(canonical);
 *
 * return {
 *   json: {
 *     ...data,
 *     correspondent_canonical: canonical,
 *     correspondent_slug: slug
 *   }
 * };
 */
