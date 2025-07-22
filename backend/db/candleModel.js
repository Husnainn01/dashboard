const mongoose = require('mongoose');

/**
 * Candle data schema
 * Represents a single candle from the trading chart
 */
const candleSchema = new mongoose.Schema({
  timestamp: {
    type: Date,
    required: true,
    index: true
  },
  tradingPair: {
    type: String,
    required: true,
    index: true,
    default: 'EUR/USD OTC'
  },
  timeframe: {
    type: Number,  // in seconds
    required: true,
    default: 60
  },
  direction: {
    type: String,
    enum: ['up', 'down', 'unknown'],
    required: true
  },
  open: {
    type: Number,
    required: true
  },
  close: {
    type: Number,
    required: true
  },
  high: {
    type: Number,
    required: true
  },
  low: {
    type: Number,
    required: true
  },
  volume: {
    type: Number,
    default: null
  },
  patternId: {
    type: String,
    index: true,
    sparse: true
  },
  metadata: {
    source: {
      type: String,
      default: 'visual'
    },
    confidence: {
      type: Number,
      default: 100
    },
    screenshotRef: String
  }
}, {
  timestamps: true
});

// Compound index for faster queries on common filters
candleSchema.index({ tradingPair: 1, timestamp: -1 });

/**
 * Pre-save hook to ensure data consistency
 */
candleSchema.pre('save', function(next) {
  // Ensure direction is correct based on open/close values
  if (this.close > this.open) {
    this.direction = 'up';
  } else if (this.close < this.open) {
    this.direction = 'down';
  }
  
  // Ensure high/low values are consistent
  this.high = Math.max(this.high, this.open, this.close);
  this.low = Math.min(this.low, this.open, this.close);
  
  next();
});

/**
 * Static method to find similar patterns
 * @param {Array} patternCandles - Array of recent candles to match
 * @param {Number} limit - Maximum number of patterns to return
 * @returns {Promise} - Promise resolving to array of similar patterns
 */
candleSchema.statics.findSimilarPatterns = async function(patternCandles, limit = 10) {
  if (!Array.isArray(patternCandles) || patternCandles.length === 0) {
    throw new Error('Pattern candles must be a non-empty array');
  }
  
  // Extract just the directions for pattern matching
  const patternDirections = patternCandles.map(c => c.direction);
  const patternLength = patternDirections.length;
  
  // Get the trading pair from the first candle
  const tradingPair = patternCandles[0].tradingPair || 'EUR/USD OTC';
  
  // Get all candles for this pair, sorted by timestamp
  const allCandles = await this.find({ tradingPair })
    .sort({ timestamp: 1 })
    .select('timestamp direction open close high low')
    .lean();
  
  // Find all occurrences of similar patterns
  const similarPatterns = [];
  
  for (let i = 0; i <= allCandles.length - patternLength; i++) {
    // Check if this sequence matches our pattern
    const sequenceMatches = patternDirections.every((dir, index) => {
      return allCandles[i + index].direction === dir;
    });
    
    if (sequenceMatches && i + patternLength < allCandles.length) {
      // Found a match, get the next candle (the prediction)
      const nextCandle = allCandles[i + patternLength];
      
      similarPatterns.push({
        patternCandles: allCandles.slice(i, i + patternLength),
        nextCandle,
        timestamp: allCandles[i].timestamp
      });
      
      // If we found enough patterns, stop searching
      if (similarPatterns.length >= limit) break;
    }
  }
  
  return similarPatterns;
};

const Candle = mongoose.model('Candle', candleSchema);

module.exports = Candle; 