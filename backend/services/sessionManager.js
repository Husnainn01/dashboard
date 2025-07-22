const fs = require('fs').promises;
const path = require('path');
const SessionData = require('../models/SessionData');

/**
 * Session Manager with MongoDB Persistence
 * Handles sharing authentication sessions between frontend iframe and backend Puppeteer
 * Now with database storage for persistent login sessions
 */
class SessionManager {
  constructor() {
    this.sessionsDir = path.join(__dirname, '../sessions');
    this.ensureSessionsDir();
  }

  async ensureSessionsDir() {
    try {
      await fs.mkdir(this.sessionsDir, { recursive: true });
    } catch (error) {
      console.error('Failed to create sessions directory:', error);
    }
  }

  /**
   * Extract cookies from frontend session and prepare for Puppeteer
   * @param {string} sessionId - Frontend session ID
   * @returns {Object} - Session data for Puppeteer
   */
  async preparePuppeteerSession(sessionId) {
    try {
      console.log('🍪 Preparing Puppeteer session for:', sessionId);
      
      // In a real implementation, this would:
      // 1. Extract cookies from the frontend iframe session
      // 2. Store them securely
      // 3. Prepare them for Puppeteer injection
      
      // For now, we'll create a session template
      const sessionData = {
        sessionId,
        cookies: [], // Will be populated from actual frontend session
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport: { width: 1920, height: 1080 },
        timestamp: new Date().toISOString()
      };

      // Save session data
      const sessionFile = path.join(this.sessionsDir, `${sessionId}.json`);
      await fs.writeFile(sessionFile, JSON.stringify(sessionData, null, 2));
      
      console.log('✅ Session prepared for Puppeteer');
      return sessionData;

    } catch (error) {
      console.error('❌ Failed to prepare Puppeteer session:', error);
      throw error;
    }
  }

  /**
   * Apply session to Puppeteer page
   * @param {Object} page - Puppeteer page instance
   * @param {string} sessionId - Session ID to apply
   * @returns {boolean} - Success status
   */
  async applySessionToPuppeteer(page, sessionId) {
    try {
      console.log('🔗 Applying session to Puppeteer:', sessionId);
      
      const sessionFile = path.join(this.sessionsDir, `${sessionId}.json`);
      const sessionData = JSON.parse(await fs.readFile(sessionFile, 'utf8'));

      // Apply user agent
      await page.setUserAgent(sessionData.userAgent);
      
      // Apply viewport
      await page.setViewport(sessionData.viewport);

      // Apply cookies (when we have them)
      if (sessionData.cookies && sessionData.cookies.length > 0) {
        await page.setCookie(...sessionData.cookies);
        console.log(`🍪 Applied ${sessionData.cookies.length} cookies to Puppeteer`);
      }

      // Navigate to Quotex trading page with session
      console.log('🌐 Navigating to Quotex with session...');
      await page.goto('https://quotex.com/trading', {
        waitUntil: 'networkidle2',
        timeout: 30000
      });

      // Check if we're logged in
      const isLoggedIn = await this.checkIfLoggedIn(page);
      
      if (isLoggedIn) {
        console.log('✅ Successfully applied session - user is logged in');
        return true;
      } else {
        console.warn('⚠️ Session applied but user appears not logged in');
        return false;
      }

    } catch (error) {
      console.error('❌ Failed to apply session to Puppeteer:', error);
      return false;
    }
  }

  /**
   * Check if user is logged in to Quotex
   * @param {Object} page - Puppeteer page instance
   * @returns {boolean} - Login status
   */
  async checkIfLoggedIn(page) {
    try {
      // Wait a bit for page to load
      await page.waitForTimeout(3000);

      // Check for login indicators
      const loginIndicators = await page.evaluate(() => {
        // Look for common logged-in elements
        const indicators = {
          hasChart: !!document.querySelector('.chart-container, #chart, .trading-chart, canvas'),
          hasUserMenu: !!document.querySelector('.user-menu, .profile, .account-info'),
          hasBalanceInfo: !!document.querySelector('.balance, .account-balance'),
          noLoginButton: !document.querySelector('.login-btn, .sign-in-btn'),
          currentUrl: window.location.href
        };
        
        console.log('Login indicators:', indicators);
        return indicators;
      });

      // Determine if logged in based on indicators
      const isLoggedIn = (
        loginIndicators.hasChart && 
        !loginIndicators.currentUrl.includes('sign-in') &&
        !loginIndicators.currentUrl.includes('login')
      );

      console.log('Login status check:', {
        isLoggedIn,
        url: loginIndicators.currentUrl,
        indicators: loginIndicators
      });

      return isLoggedIn;

    } catch (error) {
      console.error('❌ Error checking login status:', error);
      return false;
    }
  }

  /**
   * Store session cookies from frontend (called by API endpoint)
   * Now stores in both file system AND database for persistence
   * @param {string} sessionId - Session ID
   * @param {Array} cookies - Cookies from frontend
   * @param {Object} metadata - Additional session metadata
   * @returns {boolean} - Success status
   */
  async storeSessionCookies(sessionId, cookies, metadata = {}) {
    try {
      console.log('💾 Storing session cookies and metadata for:', sessionId);
      console.log('Cookies count:', cookies?.length || 0);
      
      // STEP 1: Store in file system (for legacy compatibility)
      const sessionFile = path.join(this.sessionsDir, `${sessionId}.json`);
      let sessionData = {};
      
      try {
        sessionData = JSON.parse(await fs.readFile(sessionFile, 'utf8'));
      } catch (error) {
        sessionData = {
          sessionId,
          userAgent: metadata.userAgent || 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
          viewport: { width: 1920, height: 1080 },
          timestamp: new Date().toISOString()
        };
      }

      sessionData.cookies = cookies;
      sessionData.lastUpdated = new Date().toISOString();
      sessionData.metadata = metadata;

      await fs.writeFile(sessionFile, JSON.stringify(sessionData, null, 2));
      
      // STEP 2: Store/Update in MongoDB database
      try {
        const dbSessionData = {
          sessionId,
          userEmail: metadata.email || 'quotex-user',
          userAgent: metadata.userAgent || sessionData.userAgent,
          viewport: { width: 1920, height: 1080 },
          cookies: cookies.map(cookie => ({
            name: cookie.name,
            value: cookie.value,
            domain: cookie.domain,
            path: cookie.path,
            expires: cookie.expires ? new Date(cookie.expires) : undefined,
            httpOnly: cookie.httpOnly,
            secure: cookie.secure
          })),
          status: 'pending', // Will be 'active' after validation
          validationDetails: {
            validationHistory: [{
              timestamp: new Date(),
              success: true,
              message: 'Cookies stored from frontend',
              method: 'manual'
            }]
          }
        };
        
        // Use upsert to create or update
        await SessionData.findOneAndUpdate(
          { sessionId },
          { 
            ...dbSessionData,
            lastActivity: new Date(),
            $push: {
              'validationDetails.validationHistory': {
                timestamp: new Date(),
                success: true,
                message: `Stored ${cookies.length} cookies from frontend`,
                method: 'manual'
              }
            }
          },
          { 
            upsert: true, 
            new: true,
            setDefaultsOnInsert: true
          }
        );
        
        console.log('✅ Session stored in database for persistence');
        
      } catch (dbError) {
        console.warn('⚠️ Failed to store in database, but file storage succeeded:', dbError.message);
      }
      
      console.log(`✅ Stored ${cookies.length} cookies for session ${sessionId} (file + database)`);
      return true;

    } catch (error) {
      console.error('❌ Failed to store session cookies:', error);
      return false;
    }
  }

  /**
   * Validate if a session is actually logged into Quotex
   * Now with MongoDB caching for persistent sessions - users stay logged in!
   * @param {string} sessionId - Session ID to validate
   * @returns {Object} - Validation result with login status
   */
  async validateQuotexSession(sessionId) {
    try {
      console.log('🔍 Validating Quotex session with database cache:', sessionId);

      // STEP 1: Check database cache first (FAST!)
      const cachedSession = await SessionData.findValidatedSession(sessionId);
      
      if (cachedSession && !cachedSession.needsRevalidation()) {
        console.log('✅ Found valid cached session - no need to re-validate!');
        
        // Update activity and extend session
        await SessionData.updateActivity(sessionId);
        await cachedSession.refreshExpiration(24); // Extend 24 hours
        
        return {
          isLoggedIn: true,
          sessionValid: true,
          message: 'User is logged into Quotex (cached)',
          details: {
            source: 'database_cache',
            lastValidation: cachedSession.lastValidationCheck,
            loginAge: Date.now() - cachedSession.loginTimestamp.getTime(),
            cached: true,
            timestamp: new Date().toISOString()
          }
        };
      }

      // STEP 2: Need fresh validation with Puppeteer (slower)
      console.log('🔄 No valid cached session found, running fresh validation...');
      
      const puppeteerResult = await this.runPuppeteerValidation(sessionId);
      
      // STEP 3: If validation successful, store in database for future use
      if (puppeteerResult.isLoggedIn) {
        console.log('💾 Storing validated session in database for future use');
        
        const sessionData = {
          sessionId,
          userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
          viewport: { width: 1920, height: 1080 },
          cookies: [], // Will be populated if we can extract them
          loginTimestamp: new Date(),
          validationDetails: {
            lastValidationResult: {
              success: true,
              message: puppeteerResult.message,
              hasChart: puppeteerResult.details?.hasChart || false,
              hasUserInfo: puppeteerResult.details?.hasUserInfo || false,
              noLoginButtons: puppeteerResult.details?.noLoginButtons || false,
              correctUrl: puppeteerResult.details?.correctUrl || false
            }
          }
        };
        
        await SessionData.storeValidatedSession(sessionData);
        console.log('✅ Session cached in database - future logins will be instant!');
      }
      
      return puppeteerResult;

    } catch (error) {
      console.error('❌ Session validation error:', error);
      return {
        isLoggedIn: false,
        sessionValid: false,
        message: 'Session validation failed',
        details: error.message
      };
    }
  }

  /**
   * Run Puppeteer validation (the slow method)
   * @param {string} sessionId - Session ID to validate
   * @returns {Object} - Validation result
   */
  async runPuppeteerValidation(sessionId) {
    const puppeteer = require('puppeteer');
    let browser = null;
    
    try {
      console.log('🤖 Running Puppeteer validation for:', sessionId);

      // Launch temporary browser for validation
      browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
      });

      const page = await browser.newPage();
      
      // Try to apply the session
      const sessionApplied = await this.applySessionToPuppeteer(page, sessionId);
      
      if (!sessionApplied) {
        return {
          isLoggedIn: false,
          sessionValid: false,
          message: 'Could not apply session to browser',
          details: 'Session file not found or cookies expired'
        };
      }

      // Check if actually logged in by examining the page
      const loginStatus = await this.checkIfLoggedIn(page);
      
      return {
        isLoggedIn: loginStatus,
        sessionValid: true,
        message: loginStatus ? 'User is logged into Quotex' : 'User is not logged into Quotex',
        details: {
          sessionApplied: sessionApplied,
          pageAccessible: true,
          source: 'fresh_puppeteer_validation',
          timestamp: new Date().toISOString()
        }
      };

    } catch (error) {
      console.error('❌ Puppeteer validation error:', error);
      return {
        isLoggedIn: false,
        sessionValid: false,
        message: 'Puppeteer validation failed',
        details: error.message
      };
    } finally {
      if (browser) {
        await browser.close();
      }
    }
  }

  /**
   * Get detailed session status
   * @param {string} sessionId - Session ID
   * @returns {Object} - Session status details
   */
  async getSessionStatus(sessionId) {
    try {
      const sessionFile = path.join(this.sessionsDir, `${sessionId}.json`);
      
      try {
        const sessionData = JSON.parse(await fs.readFile(sessionFile, 'utf8'));
        const stats = await fs.stat(sessionFile);
        
        return {
          exists: true,
          sessionData: {
            sessionId: sessionData.sessionId,
            timestamp: sessionData.timestamp,
            lastUpdated: sessionData.lastUpdated,
            userAgent: sessionData.userAgent
          },
          cookieCount: sessionData.cookies?.length || 0,
          fileSize: stats.size,
          createdAt: stats.birthtime,
          modifiedAt: stats.mtime,
          age: Date.now() - new Date(sessionData.timestamp).getTime()
        };
        
      } catch (readError) {
        return {
          exists: false,
          message: 'Session file not found',
          sessionId
        };
      }

    } catch (error) {
      console.error('❌ Get session status error:', error);
      return {
        exists: false,
        error: error.message,
        sessionId
      };
    }
  }

  /**
   * Test if Quotex is accessible
   * @returns {Object} - Connection test result
   */
  async testQuotexConnection() {
    const puppeteer = require('puppeteer');
    let browser = null;
    
    try {
      console.log('🌐 Testing Quotex connection...');

      browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
      });

      const page = await browser.newPage();
      
      // Set timeout for connection test
      page.setDefaultTimeout(15000);
      
      // Try to navigate to Quotex
      const response = await page.goto('https://quotex.com/sign-in/', {
        waitUntil: 'networkidle2',
        timeout: 15000
      });

      if (!response) {
        throw new Error('No response from Quotex');
      }

      const status = response.status();
      console.log('Quotex response status:', status);

      if (status === 200) {
        // Check if page loaded properly
        const title = await page.title();
        const hasLoginForm = await page.$('.login-form, input[type="email"], input[type="password"]') !== null;
        
        return {
          success: true,
          accessible: true,
          message: 'Quotex is accessible',
          details: {
            status,
            title: title.substring(0, 100), // First 100 chars
            hasLoginForm,
            url: 'https://quotex.com/sign-in/'
          }
        };
      } else {
        return {
          success: false,
          accessible: false,
          message: `Quotex returned status ${status}`,
          details: { status }
        };
      }

    } catch (error) {
      console.error('❌ Quotex connection test failed:', error);
      
      // Check if it's a Cloudflare or network issue
      let errorType = 'unknown';
      if (error.message.includes('timeout')) {
        errorType = 'timeout';
      } else if (error.message.includes('net::')) {
        errorType = 'network';
      } else if (error.message.includes('cloudflare')) {
        errorType = 'cloudflare';
      }

      return {
        success: false,
        accessible: false,
        message: 'Cannot access Quotex',
        details: {
          error: error.message,
          errorType,
          suggestion: errorType === 'timeout' ? 'Network may be slow' : 'Check internet connection'
        }
      };
    } finally {
      if (browser) {
        await browser.close();
      }
    }
  }

  /**
   * Clean up old session files
   * @param {number} maxAgeHours - Maximum age in hours
   */
  async cleanupOldSessions(maxAgeHours = 24) {
    try {
      const files = await fs.readdir(this.sessionsDir);
      const now = new Date().getTime();
      const maxAge = maxAgeHours * 60 * 60 * 1000;

      for (const file of files) {
        if (!file.endsWith('.json')) continue;
        
        const filePath = path.join(this.sessionsDir, file);
        const stats = await fs.stat(filePath);
        const fileAge = now - stats.mtime.getTime();

        if (fileAge > maxAge) {
          await fs.unlink(filePath);
          console.log(`🗑️ Cleaned up old session: ${file}`);
        }
      }

    } catch (error) {
      console.error('❌ Error cleaning up sessions:', error);
    }
  }
}

module.exports = new SessionManager(); 