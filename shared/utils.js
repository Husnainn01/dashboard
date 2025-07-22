/**
 * Shared utility functions for OTC Predictor
 * These utilities are designed to be used in both backend and frontend
 */

/**
 * Format date for display or data storage
 * @param {Date} date - Date object to format
 * @param {boolean} includeTime - Whether to include time in the formatted string
 * @returns {string} Formatted date string
 */
function formatDate(date, includeTime = true) {
  if (!date) return '';
  const d = new Date(date);
  const dateString = d.toISOString().split('T')[0];
  if (!includeTime) return dateString;
  return `${dateString} ${d.toTimeString().split(' ')[0]}`;
}

/**
 * Calculate confidence score based on historical accuracy
 * @param {number} matches - Number of successful matches
 * @param {number} total - Total number of predictions
 * @returns {number} Confidence score as percentage
 */
function calculateConfidence(matches, total) {
  if (total === 0) return 50; // Default to 50% if no data
  return Math.round((matches / total) * 100);
}

/**
 * Generate a unique pattern ID
 * @param {Array} candleData - Array of candle data points
 * @returns {string} Unique hash representing the pattern
 */
function generatePatternId(candleData) {
  if (!candleData || !Array.isArray(candleData)) return '';
  
  // Create a simple hash of the pattern
  // This is a basic implementation and could be improved
  let hash = 0;
  const pattern = candleData.map(c => c.direction).join('');
  
  for (let i = 0; i < pattern.length; i++) {
    const char = pattern.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  
  return Math.abs(hash).toString(16);
}

/**
 * Validate candle data structure
 * @param {Object} candleData - Candle data object to validate
 * @returns {boolean} Whether the data is valid
 */
function isValidCandleData(candleData) {
  if (!candleData || typeof candleData !== 'object') return false;
  
  const requiredFields = ['timestamp', 'direction', 'open', 'close', 'high', 'low'];
  for (const field of requiredFields) {
    if (!(field in candleData)) return false;
  }
  
  if (typeof candleData.timestamp !== 'string') return false;
  if (typeof candleData.direction !== 'string') return false;
  if (typeof candleData.open !== 'number') return false;
  if (typeof candleData.close !== 'number') return false;
  if (typeof candleData.high !== 'number') return false;
  if (typeof candleData.low !== 'number') return false;
  
  return true;
}

/**
 * Parse direction from raw data
 * @param {string} directionString - Raw direction value from OCR
 * @returns {string} Normalized direction ('up', 'down', or 'unknown')
 */
function parseDirection(directionString) {
  if (!directionString) return 'unknown';
  
  const lower = directionString.toLowerCase().trim();
  
  if (lower.includes('up') || lower.includes('green') || lower.includes('bull')) {
    return 'up';
  } else if (lower.includes('down') || lower.includes('red') || lower.includes('bear')) {
    return 'down';
  }
  
  return 'unknown';
}

// Export all utilities
module.exports = {
  formatDate,
  calculateConfidence,
  generatePatternId,
  isValidCandleData,
  parseDirection
};
