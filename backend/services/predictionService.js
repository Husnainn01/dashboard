const Prediction = require('../models/Prediction');
const CandleData = require('../models/CandleData');

/**
 * Prediction Service
 * Handles ML predictions for next candle direction
 */
class PredictionService {
  constructor() {
    this.isReady = false;
    this.minCandlesRequired = 10; // Need at least 10 candles for patterns
  }

  /**
   * Generate prediction based on recent candles
   * @param {Array} recentCandles - Recent candle data (latest first)
   * @param {string} sessionId - Current session ID
   * @returns {Object} - Prediction result
   */
  async generatePrediction(recentCandles, sessionId) {
    try {
      console.log('🔮 Generating prediction from', recentCandles.length, 'recent candles...');

      if (recentCandles.length < this.minCandlesRequired) {
        console.warn(`⚠️ Need at least ${this.minCandlesRequired} candles for prediction`);
        return null;
      }

      // Use the most recent candles for prediction (reverse to get chronological order)
      const chronologicalCandles = recentCandles.reverse();
      const last5Candles = chronologicalCandles.slice(-5);
      
      // Method 1: Pattern Matching
      const patternPrediction = await this.predictFromPatterns(last5Candles, sessionId);
      
      // Method 2: Simple Trend Analysis (fallback if no patterns found)
      const trendPrediction = this.predictFromTrend(last5Candles, sessionId);
      
      // Combine predictions or use the best one
      const finalPrediction = this.combinePredictions(patternPrediction, trendPrediction);
      
      console.log('🎯 Prediction generated:', {
        direction: finalPrediction.direction,
        confidence: finalPrediction.confidence,
        method: finalPrediction.algorithmUsed
      });

      return finalPrediction;

    } catch (error) {
      console.error('❌ Error generating prediction:', error);
      return null;
    }
  }

  /**
   * Pattern-based prediction using similar historical patterns
   */
  async predictFromPatterns(recentCandles, sessionId) {
    try {
      // Create pattern signature from recent candles
      const patternSignature = recentCandles.map(candle => candle.direction).join('-');
      console.log('🔍 Looking for pattern:', patternSignature);

      // Find similar patterns in history
      const similarPatterns = await this.findSimilarPatterns(recentCandles);
      
      if (similarPatterns.length === 0) {
        console.log('⚠️ No similar patterns found');
        return null;
      }

      console.log(`📊 Found ${similarPatterns.length} similar patterns`);

      // Count outcomes of similar patterns
      const outcomes = { up: 0, down: 0 };
      const patternDetails = [];

      similarPatterns.forEach(pattern => {
        if (pattern.nextDirection) {
          outcomes[pattern.nextDirection]++;
          patternDetails.push({
            timestamp: pattern.timestamp,
            nextDirection: pattern.nextDirection,
            similarity: pattern.similarity || 100
          });
        }
      });

      // Determine prediction
      const totalPatterns = outcomes.up + outcomes.down;
      const winningDirection = outcomes.up > outcomes.down ? 'up' : 'down';
      const winningCount = Math.max(outcomes.up, outcomes.down);
      
      // Calculate confidence based on pattern agreement
      const confidence = Math.min(95, Math.round((winningCount / totalPatterns) * 100));

      return {
        direction: winningDirection,
        confidence,
        algorithmUsed: 'pattern_matching',
        patternId: `pattern_${patternSignature}`,
        similarPatternsFound: patternDetails,
        features: {
          last5CandlesPattern: recentCandles.map(c => c.direction),
          totalSimilarPatterns: totalPatterns,
          patternAgreement: `${winningCount}/${totalPatterns}`,
          patternSignature
        }
      };

    } catch (error) {
      console.error('❌ Pattern prediction error:', error);
      return null;
    }
  }

  /**
   * Simple trend-based prediction (fallback method)
   */
  predictFromTrend(recentCandles, sessionId) {
    try {
      console.log('📈 Using trend analysis for prediction...');

      const directions = recentCandles.map(c => c.direction);
      const upCount = directions.filter(d => d === 'up').length;
      const downCount = directions.filter(d => d === 'down').length;
      
      // Check for consecutive patterns
      const lastDirection = directions[directions.length - 1];
      let consecutiveCount = 1;
      
      for (let i = directions.length - 2; i >= 0; i--) {
        if (directions[i] === lastDirection) {
          consecutiveCount++;
        } else {
          break;
        }
      }

      // Simple reversal strategy: if too many consecutive, predict reversal
      let predictedDirection;
      let confidence;

      if (consecutiveCount >= 3) {
        // Reversal likely after 3+ consecutive same direction
        predictedDirection = lastDirection === 'up' ? 'down' : 'up';
        confidence = 60 + (consecutiveCount * 5); // Higher confidence for longer streaks
      } else {
        // Trend continuation
        predictedDirection = upCount > downCount ? 'up' : 'down';
        confidence = 55 + Math.abs(upCount - downCount) * 5;
      }

      confidence = Math.min(95, confidence);

      return {
        direction: predictedDirection,
        confidence: Math.round(confidence),
        algorithmUsed: 'trend_analysis',
        features: {
          last5CandlesPattern: directions,
          upCount,
          downCount,
          consecutiveSameDirection: consecutiveCount,
          lastCandleDirection: lastDirection,
          trendDirection: upCount > downCount ? 'bullish' : 'bearish'
        }
      };

    } catch (error) {
      console.error('❌ Trend prediction error:', error);
      return {
        direction: Math.random() > 0.5 ? 'up' : 'down',
        confidence: 50,
        algorithmUsed: 'random'
      };
    }
  }

  /**
   * Combine multiple prediction methods
   */
  combinePredictions(patternPred, trendPred) {
    if (patternPred && trendPred) {
      // If both methods agree, increase confidence
      if (patternPred.direction === trendPred.direction) {
        return {
          ...patternPred,
          confidence: Math.min(95, patternPred.confidence + 10),
          algorithmUsed: 'pattern_matching_trend_confirmed'
        };
      } else {
        // If they disagree, use pattern matching but reduce confidence
        return {
          ...patternPred,
          confidence: Math.max(50, patternPred.confidence - 15),
          algorithmUsed: 'pattern_matching_trend_conflict'
        };
      }
    }

    // Use whichever prediction is available
    return patternPred || trendPred;
  }

  /**
   * Find similar patterns in historical data
   */
  async findSimilarPatterns(recentCandles) {
    try {
      const patternLength = recentCandles.length;
      const targetPattern = recentCandles.map(c => c.direction);

      // Get historical candles for pattern matching
      const historicalCandles = await CandleData.find({
        tradingPair: recentCandles[0].tradingPair,
        timestamp: { $lt: recentCandles[0].timestamp }
      })
      .sort({ timestamp: 1 })
      .limit(1000) // Limit for performance
      .lean();

      const matches = [];

      // Sliding window to find matching patterns
      for (let i = 0; i <= historicalCandles.length - patternLength - 1; i++) {
        const windowCandles = historicalCandles.slice(i, i + patternLength);
        const windowPattern = windowCandles.map(c => c.direction);

        // Check if pattern matches
        const isMatch = targetPattern.every((dir, index) => dir === windowPattern[index]);

        if (isMatch) {
          // Get the next candle (the outcome)
          const nextCandle = historicalCandles[i + patternLength];
          
          if (nextCandle) {
            matches.push({
              timestamp: windowCandles[0].timestamp,
              pattern: windowPattern,
              nextDirection: nextCandle.direction,
              nextCandle: {
                open: nextCandle.open,
                close: nextCandle.close,
                change: nextCandle.change
              },
              similarity: 100 // Exact match
            });
          }
        }
      }

      return matches.slice(0, 20); // Return up to 20 matches

    } catch (error) {
      console.error('❌ Error finding similar patterns:', error);
      return [];
    }
  }

  /**
   * Store prediction in database
   */
  async storePrediction(predictionData, sessionId, inputCandles = []) {
    try {
      if (!predictionData) {
        console.warn('⚠️ No prediction data to store');
        return null;
      }

      const prediction = new Prediction({
        timestamp: new Date(),
        tradingPair: 'EUR/USD OTC',
        direction: predictionData.direction,
        confidence: predictionData.confidence,
        algorithmUsed: predictionData.algorithmUsed,
        patternId: predictionData.patternId,
        similarPatternsFound: predictionData.similarPatternsFound || [],
        features: predictionData.features || {},
        sessionId,
        inputCandles: inputCandles.map(c => c._id),
        isProcessed: false
      });

      const savedPrediction = await prediction.save();
      console.log('💾 Prediction saved to MongoDB:', savedPrediction._id);
      
      return savedPrediction;

    } catch (error) {
      console.error('❌ Error storing prediction:', error);
      throw error;
    }
  }

  /**
   * Get recent predictions
   */
  async getRecentPredictions(sessionId, limit = 5) {
    try {
      const predictions = await Prediction.find({ sessionId })
        .sort({ timestamp: -1 })
        .limit(limit)
        .lean();

      return predictions;

    } catch (error) {
      console.error('❌ Error getting recent predictions:', error);
      return [];
    }
  }

  /**
   * Verify prediction accuracy when actual result is available
   */
  async verifyPrediction(predictionId, actualCandle) {
    try {
      const prediction = await Prediction.findById(predictionId);
      if (!prediction) {
        console.warn('⚠️ Prediction not found for verification');
        return null;
      }

      const isCorrect = prediction.direction === actualCandle.direction;
      
      prediction.actualResult = {
        direction: actualCandle.direction,
        actualClose: actualCandle.close,
        verifiedAt: new Date(),
        correct: isCorrect
      };

      prediction.accuracy = isCorrect ? 100 : 0;
      prediction.isProcessed = true;

      const updatedPrediction = await prediction.save();
      console.log(`✅ Prediction verified: ${isCorrect ? 'CORRECT' : 'INCORRECT'}`);
      
      return updatedPrediction;

    } catch (error) {
      console.error('❌ Error verifying prediction:', error);
      return null;
    }
  }
}

module.exports = new PredictionService(); 