const brain = require('brain.js');
const { calculateConfidence, generatePatternId } = require('../../shared/utils');
const Candle = require('../db/candleModel');

/**
 * Predictor Module
 * Uses machine learning to predict future candle directions based on historical patterns
 */
class Predictor {
  constructor(config = {}) {
    this.config = {
      patternLength: 5, // Number of candles to consider in a pattern
      trainingIterations: 1000,
      learningRate: 0.05,
      hiddenLayers: [8, 8], // Network architecture
      ...config
    };
    
    this.network = new brain.recurrent.LSTMTimeStep({
      inputSize: 1,
      outputSize: 1,
      hiddenLayers: this.config.hiddenLayers,
      learningRate: this.config.learningRate
    });
    
    this.isTrained = false;
    this.lastTrainingTime = null;
    this.trainingStats = {
      error: null,
      iterations: 0,
      patterns: 0
    };
  }
  
  /**
   * Normalize candle data for neural network input
   * @param {Array} candles - Array of candle data objects
   * @returns {Array} - Normalized data for network input
   */
  normalizeData(candles) {
    return candles.map(candle => {
      // Convert direction to numerical value (up = 1, down = 0)
      return candle.direction === 'up' ? 1 : 0;
    });
  }
  
  /**
   * Train the neural network on historical candle data
   * @param {Array} candleData - Array of candle data objects
   * @returns {Object} - Training statistics
   */
  async train(candleData = []) {
    try {
      console.log('Training prediction model...');
      
      // If no data provided, fetch from database
      let trainingData = candleData;
      if (!trainingData || trainingData.length === 0) {
        trainingData = await Candle.find({})
          .sort({ timestamp: 1 })
          .lean();
      }
      
      if (trainingData.length < this.config.patternLength + 1) {
        console.warn('Insufficient data for training. Need at least', 
          this.config.patternLength + 1, 'candles.');
        return {
          success: false,
          error: 'Insufficient data'
        };
      }
      
      // Prepare training data
      const normalizedData = this.normalizeData(trainingData);
      const trainingPatterns = [];
      
      // Create sliding window patterns
      for (let i = 0; i <= normalizedData.length - this.config.patternLength - 1; i++) {
        const pattern = normalizedData.slice(i, i + this.config.patternLength);
        const nextValue = normalizedData[i + this.config.patternLength];
        trainingPatterns.push({
          input: pattern,
          output: [nextValue]
        });
      }
      
      // Train the network
      const trainingResult = this.network.train(trainingPatterns, {
        iterations: this.config.trainingIterations,
        errorThresh: 0.005,
        log: this.config.debug,
        logPeriod: 100
      });
      
      this.isTrained = true;
      this.lastTrainingTime = new Date();
      this.trainingStats = {
        error: trainingResult.error,
        iterations: trainingResult.iterations,
        patterns: trainingPatterns.length
      };
      
      console.log('Model training complete.', this.trainingStats);
      
      return {
        success: true,
        stats: this.trainingStats
      };
    } catch (error) {
      console.error('Error training model:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  /**
   * Make a prediction for the next candle direction
   * @param {Array} recentCandles - Recent candle data to base prediction on
   * @returns {Object} - Prediction result with direction and confidence
   */
  predict(recentCandles) {
    if (!this.isTrained) {
      throw new Error('Model is not trained. Call train() first.');
    }
    
    if (!recentCandles || recentCandles.length < this.config.patternLength) {
      throw new Error(`Need at least ${this.config.patternLength} recent candles for prediction.`);
    }
    
    try {
      // Use the most recent candles for prediction
      const recentPattern = recentCandles.slice(-this.config.patternLength);
      
      // Generate pattern ID for reference
      const patternId = generatePatternId(recentPattern);
      
      // Normalize data for network input
      const normalizedPattern = this.normalizeData(recentPattern);
      
      // Make prediction
      const prediction = this.network.run(normalizedPattern);
      
      // Convert prediction to direction
      const direction = prediction > 0.5 ? 'up' : 'down';
      
      // Calculate confidence
      // Brain.js doesn't provide confidence directly, so we derive it
      // from how far the prediction is from the 0.5 threshold
      const rawConfidence = Math.abs(prediction - 0.5) * 2; // Scale to 0-1
      const confidence = Math.round(50 + (rawConfidence * 50)); // Scale to 50-100%
      
      return {
        direction,
        confidence,
        rawPrediction: prediction,
        patternId,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      console.error('Error making prediction:', error);
      throw error;
    }
  }
  
  /**
   * Find similar historical patterns and make prediction based on them
   * @param {Array} recentCandles - Recent candles to match against
   * @returns {Promise<Object>} - Prediction based on similar patterns
   */
  async predictFromSimilarPatterns(recentCandles) {
    if (!recentCandles || recentCandles.length < this.config.patternLength) {
      throw new Error(`Need at least ${this.config.patternLength} recent candles for prediction.`);
    }
    
    try {
      // Find similar patterns in history
      const similarPatterns = await Candle.findSimilarPatterns(
        recentCandles.slice(-this.config.patternLength),
        10 // Limit to 10 matches
      );
      
      if (similarPatterns.length === 0) {
        // Fall back to neural network if no similar patterns found
        return this.predict(recentCandles);
      }
      
      // Count directions in next candles
      const nextDirections = {
        up: 0,
        down: 0
      };
      
      similarPatterns.forEach(pattern => {
        nextDirections[pattern.nextCandle.direction]++;
      });
      
      // Determine direction based on majority
      const direction = nextDirections.up > nextDirections.down ? 'up' : 'down';
      const winningCount = Math.max(nextDirections.up, nextDirections.down);
      
      // Calculate confidence based on how many patterns agree
      const confidence = calculateConfidence(
        winningCount,
        similarPatterns.length
      );
      
      // Generate pattern ID for reference
      const patternId = generatePatternId(recentCandles.slice(-this.config.patternLength));
      
      return {
        direction,
        confidence,
        patternId,
        similarPatternsCount: similarPatterns.length,
        timestamp: new Date().toISOString(),
        // Include both prediction methods
        neuralPrediction: this.isTrained ? this.predict(recentCandles) : null
      };
    } catch (error) {
      console.error('Error predicting from similar patterns:', error);
      
      // Fall back to neural network if error occurs
      if (this.isTrained) {
        return this.predict(recentCandles);
      }
      
      throw error;
    }
  }
  
  /**
   * Save the trained model
   * @param {string} filePath - Path to save the model
   * @returns {boolean} - Success status
   */
  saveModel(filePath) {
    if (!this.isTrained) {
      throw new Error('Model is not trained. Call train() first.');
    }
    
    try {
      const modelData = {
        model: this.network.toJSON(),
        stats: this.trainingStats,
        config: this.config,
        lastTrainingTime: this.lastTrainingTime
      };
      
      require('fs').writeFileSync(
        filePath,
        JSON.stringify(modelData, null, 2)
      );
      
      console.log('Model saved successfully:', filePath);
      return true;
    } catch (error) {
      console.error('Error saving model:', error);
      return false;
    }
  }
  
  /**
   * Load a trained model
   * @param {string} filePath - Path to the saved model
   * @returns {boolean} - Success status
   */
  loadModel(filePath) {
    try {
      const modelData = JSON.parse(
        require('fs').readFileSync(filePath, 'utf8')
      );
      
      this.network.fromJSON(modelData.model);
      this.trainingStats = modelData.stats;
      this.config = { ...this.config, ...modelData.config };
      this.lastTrainingTime = new Date(modelData.lastTrainingTime);
      this.isTrained = true;
      
      console.log('Model loaded successfully:', filePath);
      return true;
    } catch (error) {
      console.error('Error loading model:', error);
      return false;
    }
  }
}

module.exports = Predictor; 