const express = require('express');
const router = express.Router();
const CloudStorageService = require('../services/cloudStorageService');
const CandleData = require('../models/CandleData');

const cloudStorage = new CloudStorageService();

/**
 * Get screenshots by session ID or filters
 * GET /api/screenshots?sessionId=xxx&limit=20&tradingPair=EUR/USD OTC
 */
router.get('/', async (req, res) => {
  try {
    const { sessionId, limit = 50, tradingPair, dateFrom } = req.query;
    
    const filters = {
      limit: parseInt(limit),
      ...(sessionId && { sessionId }),
      ...(tradingPair && { tradingPair }),
      ...(dateFrom && { dateFrom })
    };
    
    console.log('📷 Fetching screenshots with filters:', filters);
    
    const screenshots = await cloudStorage.getScreenshots(filters);
    
    res.json({
      success: true,
      count: screenshots.length,
      screenshots,
      filters
    });
    
  } catch (error) {
    console.error('❌ Error fetching screenshots:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * Get screenshot by candle data ID
 * GET /api/screenshots/candle/:candleId
 */
router.get('/candle/:candleId', async (req, res) => {
  try {
    const { candleId } = req.params;
    
    const candleData = await CandleData.findById(candleId).lean();
    
    if (!candleData) {
      return res.status(404).json({
        success: false,
        error: 'Candle data not found'
      });
    }
    
    if (!candleData.captureData?.screenshotPath) {
      return res.status(404).json({
        success: false,
        error: 'No screenshot available for this candle'
      });
    }
    
    res.json({
      success: true,
      screenshot: {
        url: candleData.captureData.screenshotPath,
        publicId: candleData.captureData.screenshotPublicId,
        candleData: {
          id: candleData._id,
          timestamp: candleData.timestamp,
          tradingPair: candleData.tradingPair,
          direction: candleData.direction,
          confidence: candleData.captureData.confidenceScore
        }
      }
    });
    
  } catch (error) {
    console.error('❌ Error fetching candle screenshot:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * Get storage statistics
 * GET /api/screenshots/stats
 */
router.get('/stats', async (req, res) => {
  try {
    console.log('📊 Getting storage statistics...');
    
    const [cloudStats, dbStats] = await Promise.all([
      cloudStorage.getStorageStats(),
      CandleData.countDocuments({
        'captureData.screenshotPath': { $exists: true, $ne: '' }
      })
    ]);
    
    res.json({
      success: true,
      stats: {
        cloudinary: cloudStats,
        database: {
          candleDataWithScreenshots: dbStats
        },
        syncHealth: {
          isHealthy: cloudStats.totalScreenshots >= dbStats * 0.9, // Allow 10% variance
          cloudinaryCount: cloudStats.totalScreenshots,
          databaseCount: dbStats
        }
      }
    });
    
  } catch (error) {
    console.error('❌ Error getting storage stats:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * Delete screenshot by public ID
 * DELETE /api/screenshots/:publicId
 */
router.delete('/:publicId', async (req, res) => {
  try {
    const { publicId } = req.params;
    const fullPublicId = `otc-predictor/screenshots/${publicId}`;
    
    console.log(`🗑️ Deleting screenshot: ${fullPublicId}`);
    
    // Delete from Cloudinary
    const deleteResult = await cloudStorage.deleteScreenshot(fullPublicId);
    
    // Update database records to remove screenshot references
    const updateResult = await CandleData.updateMany(
      { 'captureData.screenshotPublicId': fullPublicId },
      { 
        $unset: { 
          'captureData.screenshotPath': '',
          'captureData.screenshotPublicId': ''
        }
      }
    );
    
    res.json({
      success: true,
      message: 'Screenshot deleted successfully',
      deletedFromCloudinary: deleteResult,
      updatedCandleRecords: updateResult.modifiedCount
    });
    
  } catch (error) {
    console.error('❌ Error deleting screenshot:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * Clean up old screenshots
 * POST /api/screenshots/cleanup
 */
router.post('/cleanup', async (req, res) => {
  try {
    const { daysOld = 7 } = req.body;
    
    console.log(`🧹 Starting cleanup of screenshots older than ${daysOld} days...`);
    
    // Clean up from Cloudinary
    const cleanupResult = await cloudStorage.cleanupOldScreenshots(daysOld);
    
    // Clean up database references
    const dateThreshold = new Date();
    dateThreshold.setDate(dateThreshold.getDate() - daysOld);
    
    const dbCleanupResult = await CandleData.updateMany(
      {
        'captureData.captureTimestamp': { $lt: dateThreshold },
        'captureData.screenshotPath': { $exists: true }
      },
      {
        $unset: {
          'captureData.screenshotPath': '',
          'captureData.screenshotPublicId': ''
        }
      }
    );
    
    res.json({
      success: true,
      message: `Cleanup completed - removed screenshots older than ${daysOld} days`,
      cloudinary: cleanupResult,
      database: {
        updatedRecords: dbCleanupResult.modifiedCount
      }
    });
    
  } catch (error) {
    console.error('❌ Error during cleanup:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * Test Cloudinary connection
 * GET /api/screenshots/test
 */
router.get('/test', async (req, res) => {
  try {
    console.log('🔧 Testing Cloudinary connection...');
    
    const isConnected = await cloudStorage.testConnection();
    
    res.json({
      success: isConnected,
      message: isConnected 
        ? 'Cloudinary connection successful' 
        : 'Cloudinary connection failed',
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('❌ Cloudinary test failed:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

module.exports = router; 