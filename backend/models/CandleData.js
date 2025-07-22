const mongoose = require('mongoose');

/**
 * CandleData Schema
 * Stores extracted candle data from Quotex screen captures
 */
const candleDataSchema = new mongoose.Schema({
  // Basic candle information
  timestamp: {
    type: Date,
    required: true,
    index: true
  },
  tradingPair: {
    type: String,
    required: true,
    default: 'EUR/USD OTC'
  },
  timeframe: {
    type: Number,
    required: true,
    default: 60 // seconds
  },
  
  // OHLC data extracted from screen
  open: {
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
  close: {
    type: Number,
    required: true
  },
  
  // Derived data
  direction: {
    type: String,
    enum: ['up', 'down'],
    required: true
  },
  change: {
    type: Number,
    required: true
  },
  changePercent: {
    type: Number,
    required: true
  },
  
  // Screen capture metadata
  captureData: {
    screenshotPath: String, // Cloudinary URL or local path
    screenshotPublicId: String, // Cloudinary public ID for management
    captureTimestamp: Date,
    extractionMethod: {
      type: String,
      enum: ['tesseract', 'opencv', 'mock'],
      default: 'mock'
    },
    confidenceScore: {
      type: Number,
      min: 0,
      max: 100,
      default: 0
    }
  },
  
  // Technical indicators (if visible on screen)
  indicators: {
    rsi: Number,
    ema: Number,
    sma: Number,
    macd: Number
  },
  
  // Pattern matching
  patternId: String,
  similarPatterns: [{
    type: mongoose.Schema.Types.ObjectId,
    ref: 'CandleData'
  }],
  
  // Data quality flags
  isValidated: {
    type: Boolean,
    default: false
  },
  extractionErrors: [String],
  
  // Metadata
  sessionId: String,
  botVersion: {
    type: String,
    default: '1.0.0'
  }
}, {
  timestamps: true,
  collection: 'candledata'
});

// Indexes for performance
candleDataSchema.index({ timestamp: -1, tradingPair: 1 });
candleDataSchema.index({ sessionId: 1 });
candleDataSchema.index({ patternId: 1 });
candleDataSchema.index({ createdAt: -1 });

// Virtual for candle body size
candleDataSchema.virtual('bodySize').get(function() {
  return Math.abs(this.close - this.open);
});

// Virtual for wick sizes
candleDataSchema.virtual('upperWick').get(function() {
  return this.high - Math.max(this.open, this.close);
});

candleDataSchema.virtual('lowerWick').get(function() {
  return Math.min(this.open, this.close) - this.low;
});

// Static method to get latest candles
candleDataSchema.statics.getLatest = function(limit = 20, tradingPair = 'EUR/USD OTC') {
  return this.find({ tradingPair })
    .sort({ timestamp: -1 })
    .limit(limit)
    .exec();
};

// Instance method to find similar patterns
candleDataSchema.methods.findSimilarPatterns = function(lookback = 5) {
  // Implementation for pattern matching would go here
  return this.constructor.find({
    tradingPair: this.tradingPair,
    _id: { $ne: this._id },
    timestamp: { $lt: this.timestamp }
  }).limit(10);
};

module.exports = mongoose.model('CandleData', candleDataSchema); 