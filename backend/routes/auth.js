const express = require('express');
const router = express.Router();
const SessionManager = require('../services/sessionManager');

/**
 * Authentication Routes
 * Handles real Quotex session validation and management
 */

/**
 * Validate if a session is actually logged into Quotex
 * This will be called by frontend to verify real login status
 */
router.post('/validate-session', async (req, res) => {
  console.log('==== VALIDATE SESSION ROUTE CALLED ====');
  
  try {
    const { sessionId } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({
        success: false,
        message: 'Session ID is required',
        loggedIn: false
      });
    }

    console.log('🔍 Validating session:', sessionId);

    // Use SessionManager to check if session is actually logged in
    const validationResult = await SessionManager.validateQuotexSession(sessionId);
    
    console.log('Session validation result:', validationResult);

    return res.status(200).json({
      success: true,
      loggedIn: validationResult.isLoggedIn,
      sessionValid: validationResult.sessionValid,
      details: validationResult.details,
      message: validationResult.message
    });

  } catch (error) {
    console.error('❌ Session validation error:', error);
    return res.status(500).json({
      success: false,
      message: 'Session validation failed',
      loggedIn: false,
      error: error.message
    });
  }
});

/**
 * Store session cookies from frontend iframe
 * Called when user successfully logs in via iframe
 */
router.post('/store-session-cookies', async (req, res) => {
  console.log('==== STORE SESSION COOKIES ROUTE CALLED ====');
  
  try {
    const { sessionId, cookies, metadata } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({
        success: false,
        message: 'Session ID is required'
      });
    }

    console.log('💾 Storing cookies for session:', sessionId);
    console.log('Cookies count:', cookies?.length || 0);

    // Store the cookies using SessionManager
    const stored = await SessionManager.storeSessionCookies(sessionId, cookies || [], metadata);
    
    if (stored) {
      return res.status(200).json({
        success: true,
        message: 'Session cookies stored successfully',
        sessionId
      });
    } else {
      throw new Error('Failed to store session cookies');
    }

  } catch (error) {
    console.error('❌ Store cookies error:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to store session cookies',
      error: error.message
    });
  }
});

/**
 * Get session status
 * Returns detailed information about session state
 */
router.get('/session-status/:sessionId', async (req, res) => {
  console.log('==== GET SESSION STATUS ROUTE CALLED ====');
  
  try {
    const { sessionId } = req.params;
    
    console.log('📊 Getting status for session:', sessionId);

    const status = await SessionManager.getSessionStatus(sessionId);
    
    return res.status(200).json({
      success: true,
      sessionId,
      ...status
    });

  } catch (error) {
    console.error('❌ Get session status error:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to get session status',
      error: error.message
    });
  }
});

/**
 * Test Quotex connection
 * Creates a test browser to check if Quotex is accessible
 */
router.post('/test-quotex-connection', async (req, res) => {
  console.log('==== TEST QUOTEX CONNECTION ROUTE CALLED ====');
  
  try {
    const connectionTest = await SessionManager.testQuotexConnection();
    
    return res.status(200).json({
      success: connectionTest.success,
      message: connectionTest.message,
      accessible: connectionTest.accessible,
      details: connectionTest.details
    });

  } catch (error) {
    console.error('❌ Quotex connection test failed:', error);
    return res.status(500).json({
      success: false,
      message: 'Connection test failed',
      accessible: false,
      error: error.message
    });
  }
});

/**
 * Create authenticated session
 * Called when user confirms they are logged in
 */
router.post('/create-session', async (req, res) => {
  console.log('==== CREATE SESSION ROUTE CALLED ====');
  
  try {
    const { sessionData = {} } = req.body;
    
    // Generate unique session ID
    const sessionId = `quotex-session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    console.log('🆕 Creating new session:', sessionId);

    // Prepare session for Puppeteer
    const session = await SessionManager.preparePuppeteerSession(sessionId);
    
    // Return session info
    const response = {
      success: true,
      message: 'Session created successfully',
      session: {
        id: sessionId,
        email: sessionData.email || 'quotex-user',
        timestamp: Date.now(),
        type: 'quotex',
        validated: false // Not validated until we confirm login
      }
    };

    console.log('✅ Session created:', response.session);

    return res.status(200).json(response);

  } catch (error) {
    console.error('❌ Create session error:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to create session',
      error: error.message
    });
  }
});

/**
 * Get all sessions for a user (for management)
 */
router.get('/sessions', async (req, res) => {
  console.log('==== GET USER SESSIONS ROUTE CALLED ====');
  
  try {
    const { userEmail, limit = 10 } = req.query;
    
    const SessionData = require('../models/SessionData');
    
    let query = {};
    if (userEmail) {
      query.userEmail = userEmail;
    }
    
    const sessions = await SessionData.find(query)
      .sort({ lastActivity: -1 })
      .limit(parseInt(limit))
      .select('-cookies -validationDetails.validationHistory') // Exclude sensitive data
      .lean();
    
    const stats = await SessionData.getSessionStats();
    
    return res.status(200).json({
      success: true,
      sessions: sessions.map(session => ({
        id: session.sessionId,
        status: session.status,
        isValidated: session.isValidated,
        lastActivity: session.lastActivity,
        loginTimestamp: session.loginTimestamp,
        expiresAt: session.expiresAt,
        validationAttempts: session.validationAttempts,
        needsRevalidation: session.lastValidationCheck ? 
          (Date.now() - session.lastValidationCheck.getTime()) > (2 * 60 * 60 * 1000) : true
      })),
      stats
    });
    
  } catch (error) {
    console.error('❌ Get sessions error:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to get sessions',
      error: error.message
    });
  }
});

/**
 * Invalidate a specific session
 */
router.post('/invalidate-session', async (req, res) => {
  console.log('==== INVALIDATE SESSION ROUTE CALLED ====');
  
  try {
    const { sessionId, reason } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({
        success: false,
        message: 'Session ID is required'
      });
    }
    
    const SessionData = require('../models/SessionData');
    
    const session = await SessionData.findOne({ sessionId });
    if (!session) {
      return res.status(404).json({
        success: false,
        message: 'Session not found'
      });
    }
    
    await session.invalidate(reason || 'Manual invalidation');
    
    console.log('🗑️ Session invalidated:', sessionId);
    
    return res.status(200).json({
      success: true,
      message: 'Session invalidated successfully',
      sessionId
    });
    
  } catch (error) {
    console.error('❌ Invalidate session error:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to invalidate session',
      error: error.message
    });
  }
});

/**
 * Refresh/extend a session
 */
router.post('/refresh-session', async (req, res) => {
  console.log('==== REFRESH SESSION ROUTE CALLED ====');
  
  try {
    const { sessionId, hours = 24 } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({
        success: false,
        message: 'Session ID is required'
      });
    }
    
    const SessionData = require('../models/SessionData');
    
    const session = await SessionData.findOne({ sessionId });
    if (!session) {
      return res.status(404).json({
        success: false,
        message: 'Session not found'
      });
    }
    
    await session.refreshExpiration(hours);
    
    console.log(`🔄 Session refreshed for ${hours} hours:`, sessionId);
    
    return res.status(200).json({
      success: true,
      message: `Session extended for ${hours} hours`,
      sessionId,
      expiresAt: session.expiresAt
    });
    
  } catch (error) {
    console.error('❌ Refresh session error:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to refresh session',
      error: error.message
    });
  }
});

/**
 * Cleanup expired sessions
 */
router.post('/cleanup-sessions', async (req, res) => {
  console.log('==== CLEANUP SESSIONS ROUTE CALLED ====');
  
  try {
    const SessionData = require('../models/SessionData');
    
    const deletedCount = await SessionData.cleanupExpiredSessions();
    
    return res.status(200).json({
      success: true,
      message: `Cleaned up ${deletedCount} expired sessions`,
      deletedCount
    });
    
  } catch (error) {
    console.error('❌ Cleanup sessions error:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to cleanup sessions',
      error: error.message
    });
  }
});

/**
 * Get session statistics
 */
router.get('/session-stats', async (req, res) => {
  console.log('==== GET SESSION STATS ROUTE CALLED ====');
  
  try {
    const SessionData = require('../models/SessionData');
    
    const stats = await SessionData.getSessionStats();
    
    return res.status(200).json({
      success: true,
      stats
    });
    
  } catch (error) {
    console.error('❌ Get session stats error:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to get session statistics',
      error: error.message
    });
  }
});

/**
 * Health check endpoint
 */
router.get('/health', (req, res) => {
  return res.status(200).json({
    success: true,
    message: 'Authentication service is running',
    timestamp: new Date().toISOString()
  });
});

module.exports = router;