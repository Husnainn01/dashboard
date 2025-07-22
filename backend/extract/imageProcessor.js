const { createWorker } = require('tesseract.js');
const sharp = require('sharp');
const path = require('path');
const fs = require('fs');
const { parseDirection } = require('../../shared/utils');

/**
 * Image Processor Module
 * Extracts trading data from screenshots using OCR
 */
class ImageProcessor {
  constructor(config = {}) {
    this.config = {
      lang: process.env.OCR_LANG || 'eng',
      tempDir: path.join(__dirname, '../../temp'),
      debug: process.env.NODE_ENV === 'development',
      ...config
    };
    
    this.worker = null;
    
    // Ensure temp directory exists
    if (!fs.existsSync(this.config.tempDir)) {
      fs.mkdirSync(this.config.tempDir, { recursive: true });
    }
  }
  
  /**
   * Initialize the Tesseract worker
   */
  async initialize() {
    try {
      console.log('Initializing Tesseract OCR worker...');
      
      this.worker = await createWorker({
        logger: this.config.debug ? m => console.log(m) : undefined
      });
      
      await this.worker.loadLanguage(this.config.lang);
      await this.worker.initialize(this.config.lang);
      
      console.log('Tesseract OCR worker initialized successfully');
      return true;
    } catch (error) {
      console.error('Error initializing Tesseract OCR worker:', error);
      return false;
    }
  }
  
  /**
   * Terminate the Tesseract worker
   */
  async terminate() {
    if (this.worker) {
      try {
        await this.worker.terminate();
        this.worker = null;
        console.log('Tesseract OCR worker terminated');
      } catch (error) {
        console.error('Error terminating Tesseract OCR worker:', error);
      }
    }
  }
  
  /**
   * Preprocess an image for better OCR results
   * @param {string} imagePath - Path to the image
   * @param {Object} options - Preprocessing options
   * @returns {Promise<string>} - Path to the preprocessed image
   */
  async preprocessImage(imagePath, options = {}) {
    const { region, threshold = 150, resize = false } = options;
    const outputPath = path.join(
      this.config.tempDir, 
      `preprocessed_${path.basename(imagePath)}`
    );
    
    try {
      let image = sharp(imagePath);
      
      // Extract region if specified
      if (region && typeof region === 'object') {
        const { left, top, width, height } = region;
        image = image.extract({ left, top, width, height });
      }
      
      // Resize if specified
      if (resize) {
        const { width, height } = resize;
        image = image.resize(width, height);
      }
      
      // Apply preprocessing for better OCR
      await image
        .grayscale()
        .threshold(threshold)
        .sharpen()
        .toFile(outputPath);
      
      return outputPath;
    } catch (error) {
      console.error('Error preprocessing image:', error);
      throw error;
    }
  }
  
  /**
   * Extract text from a specific region of an image
   * @param {string} imagePath - Path to the image
   * @param {Object} region - Region coordinates
   * @returns {Promise<string>} - Extracted text
   */
  async extractTextFromRegion(imagePath, region) {
    if (!this.worker) {
      throw new Error('Tesseract OCR worker not initialized. Call initialize() first.');
    }
    
    try {
      // Preprocess the image for better OCR results
      const preprocessedImagePath = await this.preprocessImage(imagePath, { region });
      
      // Perform OCR on the preprocessed image
      const { data } = await this.worker.recognize(preprocessedImagePath);
      
      // Clean up temporary file
      if (!this.config.debug) {
        fs.unlinkSync(preprocessedImagePath);
      }
      
      return data.text.trim();
    } catch (error) {
      console.error('Error extracting text from region:', error);
      throw error;
    }
  }
  
  /**
   * Extract candle data from a screenshot
   * @param {string} screenshotPath - Path to the screenshot
   * @param {Object} regions - Regions for different data points
   * @returns {Promise<Object>} - Extracted candle data
   */
  async extractCandleData(screenshotPath, regions = {}) {
    const defaultRegions = {
      price: { left: 100, top: 50, width: 150, height: 30 },
      direction: { left: 100, top: 100, width: 150, height: 30 },
      time: { left: 100, top: 150, width: 150, height: 30 }
    };
    
    const extractRegions = { ...defaultRegions, ...regions };
    
    try {
      // Extract data from each region
      const [priceText, directionText, timeText] = await Promise.all([
        this.extractTextFromRegion(screenshotPath, extractRegions.price),
        this.extractTextFromRegion(screenshotPath, extractRegions.direction),
        this.extractTextFromRegion(screenshotPath, extractRegions.time)
      ]);
      
      // Process the extracted text
      const priceMatch = priceText.match(/(\d+\.\d+)/);
      const price = priceMatch ? parseFloat(priceMatch[1]) : null;
      
      // Parse the direction
      const direction = parseDirection(directionText);
      
      // Generate timestamp
      const timestamp = new Date().toISOString();
      
      // Create candle data object
      // Note: This is a simplified version - in reality we'd need to
      // track multiple readings to determine open, close, high, low values
      const candleData = {
        timestamp,
        direction,
        open: price,
        close: price,
        high: price,
        low: price,
        metadata: {
          source: 'visual',
          confidence: 100,
          screenshotRef: path.basename(screenshotPath)
        }
      };
      
      return candleData;
    } catch (error) {
      console.error('Error extracting candle data:', error);
      throw error;
    }
  }
  
  /**
   * Detect the color of a specific region to determine candle direction
   * @param {string} imagePath - Path to the image
   * @param {Object} region - Region coordinates
   * @returns {Promise<string>} - Detected color ('red', 'green', or 'unknown')
   */
  async detectCandleColor(imagePath, region) {
    try {
      // Extract the region
      const extractedImagePath = path.join(
        this.config.tempDir,
        `color_${path.basename(imagePath)}`
      );
      
      await sharp(imagePath)
        .extract(region)
        .toFile(extractedImagePath);
      
      // Calculate the average color
      const { dominant } = await sharp(extractedImagePath)
        .stats();
      
      // Clean up temporary file
      if (!this.config.debug) {
        fs.unlinkSync(extractedImagePath);
      }
      
      // Determine if the color is more red or green
      if (dominant.r > dominant.g + 50) {
        return 'down'; // Red candle = down
      } else if (dominant.g > dominant.r + 50) {
        return 'up'; // Green candle = up
      }
      
      return 'unknown';
    } catch (error) {
      console.error('Error detecting candle color:', error);
      return 'unknown';
    }
  }
}

module.exports = ImageProcessor; 