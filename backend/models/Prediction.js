const mongoose = require('mongoose');

/**
 * Prediction Schema
 * Stores ML predictions for next candle direction
 */
const predictionSchema = new mongoose.Schema({
  // Prediction details
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
  
  // Prediction results
  direction: {
    type: String,
    enum: ['up', 'down'],
    required: true
  },
  confidence: {
    type: Number,
    min: 0,
    max: 100,
    required: true
  },
  
  // Model information
  modelVersion: {
    type: String,
    default: '1.0.0'
  },
  algorithmUsed: {
    type: String,
    enum: ['logistic_regression', 'decision_tree', 'neural_network', 'pattern_matching'],
    default: 'pattern_matching'
  },
  
  // Input data used for prediction
  inputCandles: [{
    type: mongoose.Schema.Types.ObjectId,
    ref: 'CandleData'
  }],
  patternId: String,
  similarPatternsFound: [{
    candleId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'CandleData'
    },
    similarity: Number,
    outcome: String
  }],
  
  // Features used in prediction
  features: {
    last5CandlesPattern: [String], // ['up', 'down', 'up', 'down', 'up']
    trendDirection: {
      type: String,
      enum: ['bullish', 'bearish', 'sideways']
    },
    volatility: Number,
    averageBodySize: Number,
    consecutiveSameDirection: Number,
    lastCandleStrength: Number,
    timeOfDay: String,
    weekDay: String
  },
  
  // Actual result (filled after candle completes)
  actualResult: {
    direction: {
      type: String,
      enum: ['up', 'down']
    },
    actualClose: Number,
    actualHigh: Number,
    actualLow: Number,
    verifiedAt: Date,
    correct: Boolean
  },
  
  // Performance metrics
  accuracy: {
    type: Number,
    min: 0,
    max: 100
  },
  profitability: Number,
  
  // Metadata
  sessionId: String,
  userId: String,
  isBacktest: {
    type: Boolean,
    default: false
  },
  
  // Processing flags
  isProcessed: {
    type: Boolean,
    default: false
  },
  processingErrors: [String]
}, {
  timestamps: true,
  collection: 'predictions'
});

// Indexes for performance
predictionSchema.index({ timestamp: -1, tradingPair: 1 });
predictionSchema.index({ sessionId: 1 });
predictionSchema.index({ patternId: 1 });
predictionSchema.index({ 'actualResult.correct': 1 });
predictionSchema.index({ createdAt: -1 });

// Virtual for prediction success rate
predictionSchema.virtual('successRate').get(function() {
  // This would be calculated based on historical accuracy
  return this.accuracy || 0;
});

// Static method to get accuracy stats
predictionSchema.statics.getAccuracyStats = function(timeRange = 24) {
  const since = new Date(Date.now() - timeRange * 60 * 60 * 1000);
  
  return this.aggregate([
    {
      $match: {
        timestamp: { $gte: since },
        'actualResult.correct': { $exists: true }
      }
    },
    {
      $group: {
        _id: null,
        totalPredictions: { $sum: 1 },
        correctPredictions: {
          $sum: {
            $cond: ['$actualResult.correct', 1, 0]
          }
        },
        averageConfidence: { $avg: '$confidence' }
      }
    },
    {
      $project: {
        _id: 0,
        totalPredictions: 1,
        correctPredictions: 1,
        accuracy: {
          $multiply: [
            { $divide: ['$correctPredictions', '$totalPredictions'] },
            100
          ]
        },
        averageConfidence: 1
      }
    }
  ]);
};

// Static method to get latest predictions
predictionSchema.statics.getLatest = function(limit = 10, tradingPair = 'EUR/USD OTC') {
  return this.find({ tradingPair })
    .sort({ timestamp: -1 })
    .populate('inputCandles')
    .limit(limit)
    .exec();
};

// Instance method to verify prediction
predictionSchema.methods.verifyPrediction = function(actualCandle) {
  this.actualResult = {
    direction: actualCandle.direction,
    actualClose: actualCandle.close,
    actualHigh: actualCandle.high,
    actualLow: actualCandle.low,
    verifiedAt: new Date(),
    correct: this.direction === actualCandle.direction
  };
  
  return this.save();
};

module.exports = mongoose.model('Prediction', predictionSchema); 