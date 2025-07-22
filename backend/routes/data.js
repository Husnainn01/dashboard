const express = require('express');
const router = express.Router();
const ScreenCaptureService = require('../services/screenCaptureService');
const CandleData = require('../models/CandleData');
const Prediction = require('../models/Prediction');
const PredictionService = require('../services/predictionService'); // Add prediction service

console.log('Data routes loaded - handling screen capture and data operations');

// Global screen capture service instance
let captureService = null;

/**
 * @route   POST /api/data/start-capture
 * @desc    Start screen capture and data extraction
 * @access  Private
 */
router.post('/start-capture', async (req, res) => {
  console.log('==== START CAPTURE ROUTE CALLED ====');
  console.log('Request body:', JSON.stringify(req.body, null, 2));
  
  try {
    const { sessionId, intervalMs = 5000 } = req.body;
    
    if (!sessionId) {
      console.log('Start capture failed: Missing session ID');
      return res.status(400).json({ 
        success: false, 
        message: 'Session ID is required' 
      });
    }
    
    // Stop existing capture service if running
    if (captureService) {
      console.log('Stopping existing capture service');
      await captureService.cleanup();
      captureService = null;
    }
    
    // Create new capture service
    console.log('Creating new screen capture service for session:', sessionId);
    captureService = new ScreenCaptureService();
    
    // Initialize the service
    console.log('Initializing browser and navigation...');
    const initialized = await captureService.initialize(sessionId);
    if (!initialized) {
      throw new Error('Failed to initialize screen capture service');
    }
    
    // Navigate to trading page (optional - depends on if user is already logged in)
    const navigated = await captureService.navigateToTradingPage();
    if (!navigated) {
      console.warn('Navigation to trading page failed, but continuing with capture');
    }
    
    // Start continuous capture
    console.log(`Starting continuous capture every ${intervalMs}ms`);
    await captureService.startCapture(intervalMs);
    
    const status = captureService.getStatus();
    console.log('Screen capture started successfully:', status);
    
    return res.status(200).json({
      success: true,
      message: 'Screen capture started successfully',
      status,
      intervalMs
    });
    
  } catch (error) {
    console.error('Start capture error:', error);
    console.log('Stack trace:', error.stack);
    
    // Cleanup on error
    if (captureService) {
      try {
        await captureService.cleanup();
        captureService = null;
      } catch (cleanupError) {
        console.error('Error during cleanup:', cleanupError);
      }
    }
    
    return res.status(500).json({ 
      success: false, 
      message: 'Failed to start screen capture',
      error: error.message
    });
  }
});

/**
 * @route   POST /api/data/stop-capture
 * @desc    Stop screen capture
 * @access  Private
 */
router.post('/stop-capture', async (req, res) => {
  console.log('==== STOP CAPTURE ROUTE CALLED ====');
  
  try {
    if (!captureService) {
      console.log('No active capture service to stop');
      return res.status(200).json({
        success: true,
        message: 'No active capture service running'
      });
    }
    
    console.log('Stopping screen capture service...');
    await captureService.cleanup();
    captureService = null;
    
    console.log('Screen capture stopped successfully');
    return res.status(200).json({
      success: true,
      message: 'Screen capture stopped successfully'
    });
    
  } catch (error) {
    console.error('Stop capture error:', error);
    return res.status(500).json({ 
      success: false, 
      message: 'Failed to stop screen capture',
      error: error.message
    });
  }
});

/**
 * @route   GET /api/data/status
 * @desc    Get screen capture status
 * @access  Private
 */
router.get('/status', (req, res) => {
  console.log('==== CAPTURE STATUS ROUTE CALLED ====');
  
  if (!captureService) {
    return res.status(200).json({
      success: true,
      status: {
        isInitialized: false,
        isCapturing: false,
        sessionId: null,
        screenshotsDirectory: null
      }
    });
  }
  
  const status = captureService.getStatus();
  console.log('Current capture status:', status);
  
  return res.status(200).json({
    success: true,
    status
  });
});

/**
 * @route   GET /api/data/candles
 * @desc    Get recent candle data from MongoDB
 * @access  Private
 */
router.get('/candles', async (req, res) => {
  console.log('==== GET CANDLES ROUTE CALLED ====');
  
  try {
    const { 
      limit = 20, 
      tradingPair = 'EUR/USD OTC',
      sessionId,
      startDate,
      endDate
    } = req.query;
    
    console.log('Query parameters:', { limit, tradingPair, sessionId, startDate, endDate });
    
    // 🚨 CRITICAL: Validate session before returning candle data
    if (!sessionId) {
      console.log('❌ No session ID provided for candle data request');
      return res.status(401).json({
        success: false,
        message: 'Session ID required to view candle data - please connect to Quotex first',
        candles: [],
        requiresAuth: true
      });
    }

    console.log('🔍 Validating session for candle data:', sessionId);
    
    // Use SessionManager to validate the session
    const SessionManager = require('../services/sessionManager');
    const validationResult = await SessionManager.validateQuotexSession(sessionId);
    
    if (!validationResult.isLoggedIn) {
      console.log('❌ Session not logged in, denying candle data access');
      return res.status(401).json({
        success: false,
        message: 'You must be logged into Quotex to view candle data',
        candles: [],
        requiresAuth: true,
        validationDetails: validationResult.message
      });
    }

    console.log('✅ Session validated, fetching candle data for logged in user');
    
    // Build query - ALWAYS filter by sessionId for security
    let query = { tradingPair, sessionId };
    
    if (startDate || endDate) {
      query.timestamp = {};
      if (startDate) query.timestamp.$gte = new Date(startDate);
      if (endDate) query.timestamp.$lte = new Date(endDate);
    }
    
    console.log('MongoDB query:', query);
    
    // Fetch candles from MongoDB
    const candles = await CandleData.find(query)
      .sort({ timestamp: -1 })
      .limit(parseInt(limit))
      .lean(); // Use lean() for better performance
    
    console.log(`✅ Found ${candles.length} authenticated candles in database`);
    
    // Format for frontend
    const formattedCandles = candles.map(candle => ({
      timestamp: candle.timestamp,
      tradingPair: candle.tradingPair,
      timeframe: candle.timeframe,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
      direction: candle.direction,
      change: candle.change,
      changePercent: candle.changePercent,
      confidence: candle.captureData?.confidenceScore || 0,
      extractionMethod: candle.captureData?.extractionMethod || 'unknown',
      sessionValidated: true
    }));
    
    console.log('✅ Authenticated candle data response sent');
    return res.status(200).json({
      success: true,
      authenticated: true,
      count: formattedCandles.length,
      candles: formattedCandles,
      sessionValidated: true
    });
    
  } catch (error) {
    console.error('Get candles error:', error);
    return res.status(500).json({ 
      success: false, 
      message: 'Failed to fetch candles',
      error: error.message,
      authenticated: false
    });
  }
});

/**
 * @route   GET /api/data/predictions
 * @desc    Get recent predictions from MongoDB
 * @access  Private
 */
router.get('/predictions', async (req, res) => {
  console.log('==== GET PREDICTIONS ROUTE CALLED ====');
  
  try {
    const { 
      limit = 10, 
      tradingPair = 'EUR/USD OTC',
      sessionId
    } = req.query;
    
    // Build query
    let query = { tradingPair };
    if (sessionId) {
      query.sessionId = sessionId;
    }
    
    console.log('Fetching predictions with query:', query);
    
    // Fetch predictions from MongoDB
    const predictions = await Prediction.find(query)
      .sort({ timestamp: -1 })
      .limit(parseInt(limit))
      .populate('inputCandles')
      .lean();
    
    console.log(`Found ${predictions.length} predictions in database`);
    
    return res.status(200).json({
      success: true,
      count: predictions.length,
      predictions
    });
    
  } catch (error) {
    console.error('Get predictions error:', error);
    return res.status(500).json({ 
      success: false, 
      message: 'Failed to fetch predictions',
      error: error.message
    });
  }
});

/**
 * @route   GET /api/data/prediction
 * @desc    Get the latest prediction for the trading pair
 * @access  Private
 */
router.get('/prediction', async (req, res) => {
  console.log('==== GET LATEST PREDICTION ROUTE CALLED ====');
  
  try {
    const { 
      tradingPair = 'EUR/USD OTC',
      sessionId
    } = req.query;
    
    console.log('Getting latest prediction for:', { tradingPair, sessionId });
    
    // 🚨 CRITICAL: Validate session before returning predictions
    if (!sessionId) {
      console.log('❌ No session ID provided for prediction request');
      return res.status(401).json({
        success: false,
        message: 'Session ID required for predictions - please connect to Quotex first',
        prediction: null,
        requiresAuth: true
      });
    }

    console.log('🔍 Validating session for predictions:', sessionId);
    
    // Use SessionManager to validate the session
    const SessionManager = require('../services/sessionManager');
    const validationResult = await SessionManager.validateQuotexSession(sessionId);
    
    if (!validationResult.isLoggedIn) {
      console.log('❌ Session not logged in, denying prediction access');
      return res.status(401).json({
        success: false,
        message: 'You must be logged into Quotex to view predictions',
        prediction: null,
        requiresAuth: true,
        validationDetails: validationResult.message
      });
    }

    console.log('✅ Session validated, fetching predictions for logged in user');
    
    // Build query - ALWAYS filter by sessionId for security
    let query = { tradingPair, sessionId };
    
    // Get the most recent prediction
    const latestPrediction = await Prediction.findOne(query)
      .sort({ timestamp: -1 })
      .populate('inputCandles')
      .lean();
    
    if (!latestPrediction) {
      console.log('No predictions found for validated session');
      return res.status(200).json({
        success: true,
        message: 'No predictions available yet - start the bot to generate predictions',
        prediction: null,
        authenticated: true
      });
    }
    
    console.log('✅ Latest prediction found for authenticated user:', {
      direction: latestPrediction.direction,
      confidence: latestPrediction.confidence,
      timestamp: latestPrediction.timestamp
    });
    
    // Get recent predictions for accuracy stats
    const recentPredictions = await PredictionService.getRecentPredictions(sessionId, 10);
    
    // Calculate simple accuracy if we have verified predictions
    const verifiedPredictions = recentPredictions.filter(p => p.actualResult?.correct !== undefined);
    const correctPredictions = verifiedPredictions.filter(p => p.actualResult.correct === true);
    const accuracy = verifiedPredictions.length > 0 
      ? Math.round((correctPredictions.length / verifiedPredictions.length) * 100)
      : null;
    
    const response = {
      success: true,
      authenticated: true,
      prediction: {
        id: latestPrediction._id,
        timestamp: latestPrediction.timestamp,
        direction: latestPrediction.direction,
        confidence: latestPrediction.confidence,
        algorithmUsed: latestPrediction.algorithmUsed,
        patternId: latestPrediction.patternId,
        features: latestPrediction.features,
        createdAt: latestPrediction.createdAt,
        sessionValidated: true
      },
      stats: {
        totalPredictions: recentPredictions.length,
        verifiedPredictions: verifiedPredictions.length,
        accuracy: accuracy,
        recentPerformance: `${correctPredictions.length}/${verifiedPredictions.length}`
      }
    };
    
    console.log('✅ Authenticated prediction response sent');
    return res.status(200).json(response);
    
  } catch (error) {
    console.error('Get prediction error:', error);
    return res.status(500).json({ 
      success: false, 
      message: 'Failed to fetch prediction',
      error: error.message,
      authenticated: false
    });
  }
});

/**
 * @route   GET /api/data/stats
 * @desc    Get database and capture statistics
 * @access  Private
 */
router.get('/stats', async (req, res) => {
  console.log('==== GET STATS ROUTE CALLED ====');
  
  try {
    // Get candle statistics
    const candleStats = await CandleData.aggregate([
      {
        $group: {
          _id: null,
          totalCandles: { $sum: 1 },
          avgConfidence: { $avg: '$captureData.confidenceScore' },
          lastCaptureTime: { $max: '$timestamp' }
        }
      }
    ]);
    
    // Get prediction accuracy
    const predictionStats = await Prediction.getAccuracyStats(24); // Last 24 hours
    
    // Get capture service status
    const captureStatus = captureService ? captureService.getStatus() : {
      isInitialized: false,
      isCapturing: false
    };
    
    const stats = {
      candles: candleStats[0] || {
        totalCandles: 0,
        avgConfidence: 0,
        lastCaptureTime: null
      },
      predictions: predictionStats[0] || {
        totalPredictions: 0,
        correctPredictions: 0,
        accuracy: 0,
        averageConfidence: 0
      },
      capture: captureStatus,
      database: {
        connected: true, // If we get here, DB is connected
        collections: ['candledata', 'predictions']
      }
    };
    
    console.log('Stats generated:', stats);
    
    return res.status(200).json({
      success: true,
      stats
    });
    
  } catch (error) {
    console.error('Get stats error:', error);
    return res.status(500).json({ 
      success: false, 
      message: 'Failed to fetch statistics',
      error: error.message
    });
  }
});

/**
 * @route   POST /api/data/manual-capture
 * @desc    Manually trigger a single screenshot and data extraction
 * @access  Private
 */
router.post('/manual-capture', async (req, res) => {
  console.log('==== MANUAL CAPTURE ROUTE CALLED ====');
  
  try {
    if (!captureService || !captureService.getStatus().isInitialized) {
      return res.status(400).json({
        success: false,
        message: 'Screen capture service not initialized. Please start capture first.'
      });
    }
    
    console.log('Triggering manual capture...');
    const candleData = await captureService.captureAndProcess();
    
    if (candleData) {
      console.log('Manual capture successful');
      return res.status(200).json({
        success: true,
        message: 'Screenshot captured and data extracted',
        data: candleData
      });
    } else {
      console.log('Manual capture failed to extract data');
      return res.status(500).json({
        success: false,
        message: 'Failed to extract data from screenshot'
      });
    }
    
  } catch (error) {
    console.error('Manual capture error:', error);
    return res.status(500).json({ 
      success: false, 
      message: 'Manual capture failed',
      error: error.message
    });
  }
});

// Cleanup on process exit
process.on('SIGINT', async () => {
  console.log('Received SIGINT, cleaning up screen capture service...');
  if (captureService) {
    await captureService.cleanup();
  }
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('Received SIGTERM, cleaning up screen capture service...');
  if (captureService) {
    await captureService.cleanup();
  }
  process.exit(0);
});

module.exports = router; 