/**
 * API Service
 * Provides functions to communicate with the OTC Predictor API Gateway
 * Updated for microservices architecture
 */

// API base URL - Updated to API Gateway port 5001
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://apigatewayfront-end-production.up.railway.app';
console.log('🔌 API Service loaded - API Gateway:', API_BASE_URL);

// WebSocket URL - Updated to API Gateway
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'wss://apigatewayfront-end-production.up.railway.app';
console.log('📡 WebSocket URL:', WS_BASE_URL);

/**
 * Generic API request handler with error handling
 * @param {string} endpoint - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} API response
 */
const apiRequest = async (endpoint, options = {}) => {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    console.log(`🌐 API Request: ${options.method || 'GET'} ${url}`);
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`✅ API Response: ${endpoint}`, data);
    return data;
  } catch (error) {
    console.error(`❌ API Error: ${endpoint}`, error.message);
    throw error;
  }
};

// =============================================================================
// SYSTEM STATUS & HEALTH
// =============================================================================

/**
 * Check API health status
 * @returns {Promise<Object>} Health status
 */
export const getHealthStatus = async () => {
  return await apiRequest('/health');
};

/**
 * Get system status (database, models, etc.)
 * @returns {Promise<Object>} System status
 */
export const getSystemStatus = async () => {
  return await apiRequest('/status');
};

/**
 * Get database statistics
 * @returns {Promise<Object>} Database stats
 */
export const getDatabaseStats = async () => {
  return await apiRequest('/database/stats');
};

// =============================================================================
// CANDLE DATA
// =============================================================================

/**
 * Fetch latest candle data
 * @param {Object} params - Query parameters
 * @param {string} params.trading_pair - Trading pair (e.g., "EURUSD OTC")
 * @param {number} params.limit - Number of candles to fetch (default: 50)
 * @returns {Promise<Array>} Array of candle data
 */
export const fetchLatestCandles = async (params = {}) => {
  const tradingPair = encodeURIComponent(params.trading_pair || 'USD/BRL(OTC)');
  const limit = params.limit || 50;
  
  return await apiRequest(`/data/candles/${tradingPair}?limit=${limit}`);
};

// =============================================================================
// ML PREDICTIONS
// =============================================================================

/**
 * Get latest prediction for a trading pair
 * @param {string} tradingPair - Trading pair to predict
 * @returns {Promise<Object>} Prediction data
 */
export const getLatestPrediction = async (tradingPair = 'USD/BRL(OTC)', modelName = null) => {
  const qp = modelName ? `?model_name=${encodeURIComponent(modelName)}` : '';
  return await apiRequest(`/predict/${encodeURIComponent(tradingPair)}${qp}`);
};

/**
 * Request a new prediction for a trading pair
 * @param {string} tradingPair - Trading pair to predict
 * @param {string} modelType - Model type to use (optional)
 * @returns {Promise<Object>} Prediction data
 */
export const requestPrediction = async (tradingPair = 'USD/BRL(OTC)', modelType = null, modelName = null) => {
  const body = {
    trading_pair: tradingPair
  };
  
  if (modelType) {
    body.model_type = modelType;
  }
  if (modelName) {
    body.model_name = modelName;
  }
  
  return await apiRequest('/predict', {
    method: 'POST',
    body: JSON.stringify(body)
  });
};

// =============================================================================
// ML MODELS MANAGEMENT
// =============================================================================

/**
 * Get available ML models and their status
 * @returns {Promise<Object>} Models information
 */
export const getModelsInfo = async () => {
  return await apiRequest('/ml/models');
};

/**
 * Get models for a specific trading pair
 * @param {string} tradingPair - Trading pair to get models for
 * @returns {Promise<Object>} Models information
 */
export const getModelsForPair = async (tradingPair = 'USD/BRL(OTC)') => {
  return await apiRequest(`/ml/models/${encodeURIComponent(tradingPair)}`);
};

/**
 * Trigger model retraining
 * @param {string} tradingPair - Trading pair to retrain model for
 * @param {string} modelType - Model type to train (xgboost, random_forest, lightgbm)
 * @param {boolean} forceRetrain - Force retraining even if model exists
 * @returns {Promise<Object>} Retraining response
 */
export const retrainModel = async (tradingPair = 'USD/BRL(OTC)', modelType = 'xgboost', forceRetrain = false) => {
  return await apiRequest('/ml/train', {
    method: 'POST',
    body: JSON.stringify({
      trading_pair: tradingPair,
      model_type: modelType,
      force_retrain: forceRetrain
    })
  });
};

/**
 * Get training job status
 * @param {string} jobId - Training job ID
 * @returns {Promise<Object>} Job status
 */
export const getTrainingStatus = async (jobId) => {
  return await apiRequest(`/ml/train/status/${jobId}`);
};

/**
 * Get training queue status
 * @returns {Promise<Object>} Queue status
 */
export const getTrainingQueueStatus = async () => {
  return await apiRequest('/ml/queue/status');
};

/**
 * Get available trading pairs
 * @returns {Promise<Array>} List of trading pairs
 */
export const getTradingPairs = async () => {
  return await apiRequest('/trading-pairs');
};

// =============================================================================
// PREDICTION SERVICE CONTROL
// =============================================================================

/**
 * Start continuous prediction service
 * @returns {Promise<Object>} Response
 */
export const startPredictionService = async () => {
  return await apiRequest('/predictions/start', {
    method: 'POST'
  });
};

/**
 * Stop continuous prediction service
 * @returns {Promise<Object>} Response
 */
export const stopPredictionService = async () => {
  return await apiRequest('/predictions/stop', {
    method: 'POST'
  });
};

// =============================================================================
// WEBSOCKET CONNECTIONS
// =============================================================================

/**
 * Create WebSocket connection for predictions
 * @returns {WebSocket} WebSocket connection
 */
export const createPredictionWebSocket = () => {
  return new WebSocket(`${WS_BASE_URL}/ws/predictions`);
};

/**
 * Create WebSocket connection for market data
 * @returns {WebSocket} WebSocket connection
 */
export const createMarketDataWebSocket = () => {
  return new WebSocket(`${WS_BASE_URL}/ws/market-data`);
};

/**
 * Create unified WebSocket connection
 * @returns {WebSocket} WebSocket connection
 */
export const createUnifiedWebSocket = () => {
  return new WebSocket(`${WS_BASE_URL}/ws`);
};

// =============================================================================
// LEGACY COMPATIBILITY
// =============================================================================

/**
 * Fetch mock data - Updated to use real API data
 * @returns {Promise<Object>} Real candle and prediction data
 */
export const fetchMockData = async () => {
  try {
    const [candles, prediction] = await Promise.all([
      fetchLatestCandles({ limit: 20 }),
      getLatestPrediction().catch(() => null) // Don't fail if no prediction available
    ]);
    
    return {
      candles: candles?.candles || [],
      prediction: prediction
    };
  } catch (error) {
    console.warn('⚠️ Failed to fetch real data, using fallback');
    return {
      candles: [],
      prediction: null
    };
  }
};

/**
 * Start bot - Updated to start prediction service
 * @returns {Promise<Object>} Response
 */
export const startBot = async () => {
  try {
    return await startPredictionService();
  } catch (error) {
    return { 
      success: false, 
      message: error.message
    };
  }
};

/**
 * Stop bot - Updated to stop prediction service
 * @returns {Promise<Object>} Response  
 */
export const stopBot = async () => {
  try {
    return await stopPredictionService();
  } catch (error) {
    return { 
      success: false, 
      message: error.message
    };
  }
};

/**
 * Get bot status - Updated to show system status
 * @returns {Promise<Object>} System status
 */
export const getBotStatus = async () => {
  try {
    const status = await getSystemStatus();
    return {
      running: status.prediction?.status === 'running',
      uptime: status.prediction?.uptime_seconds || 0,
      candlesProcessed: status.data_collection?.stats?.total_collections || 0,
      lastPrediction: status.prediction?.last_prediction || null,
      modelsLoaded: Object.keys(status.prediction?.active_models || {}).length
    };
  } catch (error) {
    return {
      running: false,
      uptime: 0,
      candlesProcessed: 0,
      lastPrediction: null,
      modelsLoaded: 0,
      error: error.message
    };
  }
};

/**
 * Fetch historical data - Updated to use real API
 * @param {Object} params - Query parameters
 * @returns {Promise<Array>} Historical candle data
 */
export const fetchHistoricalData = async (params = {}) => {
  return await fetchLatestCandles({
    trading_pair: params.tradingPair || 'USD/BRL(OTC)',
    limit: params.count || 50
  });
};

/**
 * Save settings - Placeholder for future settings API
 * @param {Object} settings - Settings to save
 * @returns {Promise<Object>} Response
 */
export const saveSettings = async (settings) => {
  console.log('💾 Settings save requested:', settings);
  // For now, just store in localStorage
  localStorage.setItem('otc_predictor_settings', JSON.stringify(settings));
  return { 
    success: true, 
    message: 'Settings saved locally',
    settings
  };
};

// =============================================================================
// EXPORTS
// =============================================================================

export default {
  // System Status
  getHealthStatus,
  getSystemStatus,
  getDatabaseStats,
  
  // Candle Data
  fetchLatestCandles,
  
  // ML Predictions
  getLatestPrediction,
  requestPrediction,
  
  // Model Management
  getModelsInfo,
  getModelsForPair,
  retrainModel,
  getTrainingStatus,
  getTrainingQueueStatus,
  getTradingPairs,
  
  // Prediction Service Control
  startPredictionService,
  stopPredictionService,
  
  // WebSocket Connections
  createPredictionWebSocket,
  createMarketDataWebSocket,
  createUnifiedWebSocket,
  
  // Legacy Compatibility
  fetchMockData,
  startBot,
  stopBot,
  getBotStatus,
  fetchHistoricalData,
  saveSettings
};