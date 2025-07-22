const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

/**
 * Browser Automation Module using Puppeteer
 * This module handles the browser automation for capturing screenshots from trading platforms
 */
class BrowserAutomation {
  constructor(config = {}) {
    this.config = {
      headless: process.env.HEADLESS === 'true',
      targetUrl: process.env.TARGET_URL || 'https://quotex.com',
      screenshotInterval: parseInt(process.env.SCREENSHOT_INTERVAL) || 1000,
      screenshotDir: path.join(__dirname, '../../screenshots'),
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      viewportWidth: 1920,
      viewportHeight: 1080,
      ...config
    };
    
    this.browser = null;
    this.page = null;
    this.isRunning = false;
    this.screenshotInterval = null;
    
    // Ensure screenshot directory exists
    if (!fs.existsSync(this.config.screenshotDir)) {
      fs.mkdirSync(this.config.screenshotDir, { recursive: true });
    }
  }
  
  /**
   * Initialize the browser and navigate to the target URL
   */
  async initialize() {
    try {
      console.log('Launching browser...');
      
      this.browser = await puppeteer.launch({
        headless: this.config.headless,
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-accelerated-2d-canvas',
          '--disable-gpu',
          '--window-size=1920,1080'
        ]
      });
      
      this.page = await this.browser.newPage();
      
      // Set user agent to avoid bot detection
      await this.page.setUserAgent(this.config.userAgent);
      
      // Set viewport size
      await this.page.setViewport({
        width: this.config.viewportWidth,
        height: this.config.viewportHeight
      });
      
      // Set extra headers
      await this.page.setExtraHTTPHeaders({
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Connection': 'keep-alive'
      });
      
      // Navigate to the target URL
      console.log(`Navigating to ${this.config.targetUrl}...`);
      await this.page.goto(this.config.targetUrl, {
        waitUntil: 'networkidle2',
        timeout: 60000
      });
      
      console.log('Browser initialized successfully');
      return true;
    } catch (error) {
      console.error('Error initializing browser:', error);
      await this.shutdown();
      return false;
    }
  }
  
  /**
   * Start taking screenshots at the specified interval
   * @param {Object} options - Screenshot options
   * @param {Function} callback - Callback function to execute after each screenshot
   */
  async startCapturing(options = {}, callback = null) {
    if (!this.browser || !this.page) {
      console.error('Browser not initialized. Call initialize() first.');
      return false;
    }
    
    try {
      this.isRunning = true;
      console.log(`Starting screenshot capture at ${this.config.screenshotInterval}ms intervals`);
      
      // Default screenshot options
      const screenshotOptions = {
        type: 'png',
        fullPage: false,
        ...options
      };
      
      // Start screenshot interval
      this.screenshotInterval = setInterval(async () => {
        if (!this.isRunning) return;
        
        try {
          // Generate filename with timestamp
          const timestamp = new Date().toISOString().replace(/:/g, '-');
          const filename = `screenshot_${timestamp}.png`;
          const filepath = path.join(this.config.screenshotDir, filename);
          
          // Take screenshot
          await this.page.screenshot({
            ...screenshotOptions,
            path: filepath
          });
          
          console.log(`Screenshot saved: ${filename}`);
          
          // Execute callback if provided
          if (callback && typeof callback === 'function') {
            callback(filepath, timestamp);
          }
        } catch (error) {
          console.error('Error taking screenshot:', error);
        }
      }, this.config.screenshotInterval);
      
      return true;
    } catch (error) {
      console.error('Error starting capture:', error);
      this.isRunning = false;
      return false;
    }
  }
  
  /**
   * Stop taking screenshots
   */
  stopCapturing() {
    if (this.screenshotInterval) {
      clearInterval(this.screenshotInterval);
      this.screenshotInterval = null;
    }
    this.isRunning = false;
    console.log('Screenshot capture stopped');
    return true;
  }
  
  /**
   * Shut down the browser
   */
  async shutdown() {
    this.stopCapturing();
    
    if (this.browser) {
      try {
        await this.browser.close();
        console.log('Browser closed successfully');
      } catch (error) {
        console.error('Error closing browser:', error);
      }
      
      this.browser = null;
      this.page = null;
    }
    
    return true;
  }
  
  /**
   * Take a single screenshot
   * @param {Object} options - Screenshot options
   * @returns {Promise<string>} - Path to the saved screenshot
   */
  async takeScreenshot(options = {}) {
    if (!this.browser || !this.page) {
      throw new Error('Browser not initialized. Call initialize() first.');
    }
    
    // Generate filename with timestamp
    const timestamp = new Date().toISOString().replace(/:/g, '-');
    const filename = `screenshot_${timestamp}.png`;
    const filepath = path.join(this.config.screenshotDir, filename);
    
    // Take screenshot
    await this.page.screenshot({
      path: filepath,
      type: 'png',
      fullPage: false,
      ...options
    });
    
    console.log(`Single screenshot saved: ${filename}`);
    return filepath;
  }
}

module.exports = BrowserAutomation; 