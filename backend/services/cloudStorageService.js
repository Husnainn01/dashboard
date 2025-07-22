const cloudinary = require('cloudinary').v2;
const fs = require('fs').promises;
const path = require('path');

class CloudStorageService {
  constructor() {
    // Configure Cloudinary using environment variable
    if (!process.env.CLOUDINARY_URL) {
      throw new Error('CLOUDINARY_URL environment variable is required');
    }
    
    // Cloudinary auto-configures from CLOUDINARY_URL
    console.log('✅ Cloudinary configured successfully');
    
    this.folder = 'otc-predictor/screenshots'; // Organize screenshots in folder
  }

  /**
   * Upload screenshot buffer to Cloudinary
   * @param {Buffer} imageBuffer - Screenshot buffer from Puppeteer
   * @param {string} filename - Original filename for reference
   * @param {Object} metadata - Additional metadata to store
   * @returns {Object} - Upload result with public_id, url, secure_url
   */
  async uploadScreenshot(imageBuffer, filename, metadata = {}) {
    try {
      console.log(`📤 Uploading screenshot: ${filename}`);
      
      // Convert buffer to base64 data URI
      const base64Image = `data:image/png;base64,${imageBuffer.toString('base64')}`;
      
      // Generate unique public_id using timestamp and session
      const timestamp = Date.now();
      const publicId = `${this.folder}/${timestamp}_${filename.replace('.png', '')}`;
      
      // Upload options
      const uploadOptions = {
        public_id: publicId,
        folder: this.folder,
        resource_type: 'image',
        format: 'png',
        overwrite: false,
        // Add custom metadata
        context: {
          sessionId: metadata.sessionId || 'unknown',
          tradingPair: metadata.tradingPair || 'EUR/USD OTC',
          timestamp: metadata.timestamp || new Date().toISOString(),
          extractionMethod: metadata.extractionMethod || 'puppeteer',
          ...metadata
        },
        // Add tags for easy searching
        tags: ['otc-predictor', 'screenshot', 'quotex', metadata.sessionId || 'session'].filter(Boolean)
      };
      
      // Upload to Cloudinary
      const result = await cloudinary.uploader.upload(base64Image, uploadOptions);
      
      console.log(`✅ Screenshot uploaded successfully: ${result.secure_url}`);
      
      return {
        success: true,
        publicId: result.public_id,
        url: result.secure_url,
        width: result.width,
        height: result.height,
        bytes: result.bytes,
        format: result.format,
        uploadedAt: new Date().toISOString(),
        metadata: result.context || {}
      };
      
    } catch (error) {
      console.error('❌ Failed to upload screenshot to Cloudinary:', error);
      throw new Error(`Cloudinary upload failed: ${error.message}`);
    }
  }

  /**
   * Upload temporary file to Cloudinary and delete local file
   * @param {string} filePath - Path to temporary screenshot file
   * @param {Object} metadata - Additional metadata
   * @returns {Object} - Upload result
   */
  async uploadFile(filePath, metadata = {}) {
    try {
      // Read file as buffer
      const imageBuffer = await fs.readFile(filePath);
      const filename = path.basename(filePath);
      
      // Upload buffer
      const result = await this.uploadScreenshot(imageBuffer, filename, metadata);
      
      // Clean up temporary file
      try {
        await fs.unlink(filePath);
        console.log(`🗑️ Temporary file deleted: ${filePath}`);
      } catch (unlinkError) {
        console.warn(`⚠️ Could not delete temporary file: ${filePath}`, unlinkError.message);
      }
      
      return result;
      
    } catch (error) {
      console.error('❌ Failed to upload file to Cloudinary:', error);
      throw error;
    }
  }

  /**
   * Get screenshots by session ID or trading pair
   * @param {Object} filters - Search filters
   * @returns {Array} - Array of screenshot resources
   */
  async getScreenshots(filters = {}) {
    try {
      let searchQuery = `folder:${this.folder}`;
      
      if (filters.sessionId) {
        searchQuery += ` AND context.sessionId:${filters.sessionId}`;
      }
      
      if (filters.tradingPair) {
        searchQuery += ` AND context.tradingPair:"${filters.tradingPair}"`;
      }
      
      if (filters.dateFrom) {
        searchQuery += ` AND created_at>=${filters.dateFrom}`;
      }
      
      const result = await cloudinary.search
        .expression(searchQuery)
        .sort_by([['created_at', 'desc']])
        .max_results(filters.limit || 50)
        .with_field('context')
        .with_field('tags')
        .execute();
      
      return result.resources.map(resource => ({
        publicId: resource.public_id,
        url: resource.secure_url,
        createdAt: resource.created_at,
        metadata: resource.context || {},
        tags: resource.tags || [],
        width: resource.width,
        height: resource.height,
        bytes: resource.bytes
      }));
      
    } catch (error) {
      console.error('❌ Failed to get screenshots from Cloudinary:', error);
      throw error;
    }
  }

  /**
   * Delete screenshot from Cloudinary
   * @param {string} publicId - Public ID of the image to delete
   * @returns {Object} - Deletion result
   */
  async deleteScreenshot(publicId) {
    try {
      const result = await cloudinary.uploader.destroy(publicId);
      console.log(`🗑️ Screenshot deleted: ${publicId}`);
      return result;
    } catch (error) {
      console.error('❌ Failed to delete screenshot:', error);
      throw error;
    }
  }

  /**
   * Clean up old screenshots (older than specified days)
   * @param {number} daysOld - Delete screenshots older than this many days
   * @returns {Object} - Cleanup result
   */
  async cleanupOldScreenshots(daysOld = 7) {
    try {
      const dateThreshold = new Date();
      dateThreshold.setDate(dateThreshold.getDate() - daysOld);
      const formattedDate = dateThreshold.toISOString().split('T')[0];
      
      const searchQuery = `folder:${this.folder} AND created_at<${formattedDate}`;
      
      const result = await cloudinary.search
        .expression(searchQuery)
        .max_results(500)
        .execute();
      
      if (result.resources.length === 0) {
        console.log(`✅ No old screenshots to cleanup (older than ${daysOld} days)`);
        return { deleted: 0, resources: [] };
      }
      
      const publicIds = result.resources.map(resource => resource.public_id);
      const deleteResult = await cloudinary.api.delete_resources(publicIds);
      
      console.log(`🗑️ Cleaned up ${Object.keys(deleteResult.deleted).length} old screenshots`);
      
      return {
        deleted: Object.keys(deleteResult.deleted).length,
        resources: result.resources
      };
      
    } catch (error) {
      console.error('❌ Failed to cleanup old screenshots:', error);
      throw error;
    }
  }

  /**
   * Get storage statistics
   * @returns {Object} - Storage usage stats
   */
  async getStorageStats() {
    try {
      const searchQuery = `folder:${this.folder}`;
      
      const result = await cloudinary.search
        .expression(searchQuery)
        .aggregate('resource_type')
        .execute();
      
      const stats = {
        totalScreenshots: result.total_count || 0,
        folder: this.folder,
        searchQuery,
        aggregates: result.aggregations || {}
      };
      
      console.log(`📊 Storage stats:`, stats);
      return stats;
      
    } catch (error) {
      console.error('❌ Failed to get storage stats:', error);
      throw error;
    }
  }

  /**
   * Test Cloudinary connection
   * @returns {boolean} - True if connection successful
   */
  async testConnection() {
    try {
      // Test with a simple API call
      const result = await cloudinary.api.ping();
      console.log('✅ Cloudinary connection test successful:', result);
      return true;
    } catch (error) {
      console.error('❌ Cloudinary connection test failed:', error);
      return false;
    }
  }
}

module.exports = CloudStorageService; 