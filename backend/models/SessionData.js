const mongoose = require('mongoose');

/**
 * SessionData Model
 * Stores persistent session information for users to avoid repeated logins
 */
const sessionDataSchema = new mongoose.Schema({
  sessionId: {
    type: String,
    required: true,
    unique: true,
    index: true
  },
  
  // User identification
  userEmail: {
    type: String,
    default: 'quotex-user'
  },
  
  // Session validation status
  isValidated: {
    type: Boolean,
    default: false,
    index: true
  },
  
  lastValidationCheck: {
    type: Date,
    default: Date.now
  },
  
  validationAttempts: {
    type: Number,
    default: 0
  },
  
  // Session metadata
  userAgent: {
    type: String,
    required: true
  },
  
  viewport: {
    width: { type: Number, default: 1920 },
    height: { type: Number, default: 1080 }
  },
  
  // Cookie storage (encrypted in production)
  cookies: [{
    name: String,
    value: String,
    domain: String,
    path: String,
    expires: Date,
    httpOnly: Boolean,
    secure: Boolean
  }],
  
  // Session activity tracking
  lastActivity: {
    type: Date,
    default: Date.now,
    index: true
  },
  
  loginTimestamp: {
    type: Date,
    default: Date.now
  },
  
  // Session status
  status: {
    type: String,
    enum: ['active', 'expired', 'invalid', 'pending'],
    default: 'pending',
    index: true
  },
  
  // Validation details
  validationDetails: {
    lastValidationResult: {
      success: Boolean,
      message: String,
      hasChart: Boolean,
      hasUserInfo: Boolean,
      noLoginButtons: Boolean,
      correctUrl: Boolean
    },
    
    validationHistory: [{
      timestamp: Date,
      success: Boolean,
      message: String,
      method: { type: String, enum: ['puppeteer', 'cache', 'manual'] }
    }]
  },
  
  // Auto-expiration (TTL)
  expiresAt: {
    type: Date,
    default: () => new Date(Date.now() + 24 * 60 * 60 * 1000), // 24 hours
    index: { expireAfterSeconds: 0 }
  }
  
}, { 
  timestamps: true,
  collection: 'sessiondata'
});

// Indexes for performance
sessionDataSchema.index({ sessionId: 1, isValidated: 1 });
sessionDataSchema.index({ lastActivity: -1, status: 1 });
sessionDataSchema.index({ expiresAt: 1 });

// Static methods

/**
 * Find active validated session
 */
sessionDataSchema.statics.findValidatedSession = function(sessionId) {
  return this.findOne({
    sessionId,
    isValidated: true,
    status: 'active',
    expiresAt: { $gt: new Date() }
  });
};

/**
 * Store or update session validation
 */
sessionDataSchema.statics.storeValidatedSession = async function(sessionData) {
  const update = {
    ...sessionData,
    isValidated: true,
    status: 'active',
    lastValidationCheck: new Date(),
    lastActivity: new Date(),
    $push: {
      'validationDetails.validationHistory': {
        timestamp: new Date(),
        success: true,
        message: 'Session validated successfully',
        method: 'puppeteer'
      }
    }
  };
  
  const options = { 
    upsert: true, 
    new: true,
    setDefaultsOnInsert: true
  };
  
  return this.findOneAndUpdate(
    { sessionId: sessionData.sessionId },
    update,
    options
  );
};

/**
 * Update session activity
 */
sessionDataSchema.statics.updateActivity = function(sessionId) {
  return this.findOneAndUpdate(
    { sessionId },
    { 
      lastActivity: new Date(),
      $inc: { 'validationAttempts': 1 }
    },
    { new: true }
  );
};

/**
 * Get session statistics
 */
sessionDataSchema.statics.getSessionStats = async function() {
  const stats = await this.aggregate([
    {
      $group: {
        _id: '$status',
        count: { $sum: 1 },
        avgValidationAttempts: { $avg: '$validationAttempts' },
        lastActivity: { $max: '$lastActivity' }
      }
    }
  ]);
  
  const totalSessions = await this.countDocuments();
  const validatedSessions = await this.countDocuments({ 
    isValidated: true, 
    status: 'active' 
  });
  
  return {
    total: totalSessions,
    validated: validatedSessions,
    validationRate: totalSessions > 0 ? (validatedSessions / totalSessions * 100).toFixed(1) : 0,
    statusBreakdown: stats
  };
};

/**
 * Clean up expired sessions
 */
sessionDataSchema.statics.cleanupExpiredSessions = async function() {
  const result = await this.deleteMany({
    $or: [
      { expiresAt: { $lt: new Date() } },
      { 
        lastActivity: { 
          $lt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) // 7 days old
        },
        status: { $ne: 'active' }
      }
    ]
  });
  
  console.log(`🗑️ Cleaned up ${result.deletedCount} expired sessions`);
  return result.deletedCount;
};

// Instance methods

/**
 * Check if session needs revalidation
 */
sessionDataSchema.methods.needsRevalidation = function() {
  const maxAge = 2 * 60 * 60 * 1000; // 2 hours
  const timeSinceValidation = Date.now() - this.lastValidationCheck.getTime();
  
  return (
    !this.isValidated ||
    timeSinceValidation > maxAge ||
    this.status !== 'active'
  );
};

/**
 * Mark session as invalid
 */
sessionDataSchema.methods.invalidate = function(reason = 'Unknown') {
  this.isValidated = false;
  this.status = 'invalid';
  this.validationDetails.validationHistory.push({
    timestamp: new Date(),
    success: false,
    message: `Session invalidated: ${reason}`,
    method: 'system'
  });
  
  return this.save();
};

/**
 * Refresh session expiration
 */
sessionDataSchema.methods.refreshExpiration = function(hours = 24) {
  this.expiresAt = new Date(Date.now() + hours * 60 * 60 * 1000);
  this.lastActivity = new Date();
  return this.save();
};

// Middleware to update lastActivity on save
sessionDataSchema.pre('save', function(next) {
  if (this.isModified() && !this.isModified('lastActivity')) {
    this.lastActivity = new Date();
  }
  next();
});

// Auto-cleanup expired sessions every hour
if (process.env.NODE_ENV !== 'test') {
  setInterval(async () => {
    try {
      await mongoose.model('SessionData').cleanupExpiredSessions();
    } catch (error) {
      console.error('❌ Session cleanup error:', error);
    }
  }, 60 * 60 * 1000); // 1 hour
}

module.exports = mongoose.model('SessionData', sessionDataSchema); 