/**
 * API Service
 * Provides functions to communicate with the OTC Predictor API Gateway
 * Updated for microservices architecture
 *
 * All HTTP requests go through Next.js rewrites (server-side proxy) to
 * avoid CORS issues.  The browser only hits /api/*, /ml-api/*, /data-api/*
 * which Next.js forwards to the actual Railway URLs configured in .env.
 *
 * WebSocket URLs still connect directly (WSS doesn't go through rewrites).
 */

// HTTP proxy paths (matched by next.config.js rewrites)
const API_BASE = '/api';           // → NEXT_PUBLIC_API_URL
const ML_TRAINING_BASE = '/ml-api'; // → NEXT_PUBLIC_ML_TRAINING_URL
const DATA_COLLECTION_BASE = '/data-api'; // → NEXT_PUBLIC_DATA_COLLECTION_URL

const getApiBase = () => API_BASE;

// WebSocket still needs the direct URL (can't proxy through Next.js rewrites)
const getWsBase = () => {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('ws_base_url');
    if (stored) return stored;
  }
  return process.env.NEXT_PUBLIC_WS_URL || '';
};

// Kept for backward compat but no longer used by index.jsx
export const setApiBaseUrl = () => {};
export const setWsBaseUrl = (url) => {
  if (typeof window !== 'undefined') {
    if (url) localStorage.setItem('ws_base_url', url); else localStorage.removeItem('ws_base_url');
  }
};

console.log('🔌 API proxy path:', API_BASE);
console.log('📡 WebSocket base:', getWsBase() || '(unset)');

/**
 * Generic API request handler with error handling
 * @param {string} endpoint - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} API response
 */
const apiRequest = async (endpoint, options = {}) => {
  try {
    // Add cache-busting parameter for GET requests
    const cacheBuster = options.method === 'GET' ? `${endpoint.includes('?') ? '&' : '?'}_t=${Date.now()}` : '';
    
    // Construct full URL
    const url = `${getApiBase()}${endpoint}${cacheBuster}`;
    console.log(`🔌 API Request: ${options.method || 'GET'} ${url}`);
    
    // Set default headers
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    
    // Make request
    const response = await fetch(url, {
      ...options,
      headers,
    });
    
    // Handle non-200 responses
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`❌ API Error (${response.status}): ${errorText}`);
      throw new Error(`API Error: ${response.status} ${errorText}`);
    }
    
    // Parse JSON response
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('❌ API Request failed:', error);
    throw error;
  }
};

/**
 * Make a direct request to the ML Training Service (bypassing API Gateway)
 * @param {string} endpoint - ML Training service endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} Response data
 */
const directMLTrainingRequest = async (endpoint, options = {}) => {
  try {
    // Add cache-busting parameter for GET requests
    const cacheBuster = options.method === 'GET' ? `${endpoint.includes('?') ? '&' : '?'}_t=${Date.now()}` : '';
    const url = `${ML_TRAINING_BASE}${endpoint}${cacheBuster}`;
    console.log(`🔄 Direct ML Training Request: ${options.method || 'GET'} ${url}`);
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        ...options.headers
      },
      ...options
    });
    
    // Handle non-200 responses
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`❌ ML Training API Error (${response.status}): ${errorText}`);
      throw new Error(`ML Training API Error: ${response.status} ${errorText}`);
    }
    
    // Parse JSON response
    const data = await response.json();
    console.log('✅ ML Training API Response:', data);
    return data;
  } catch (error) {
    console.error(`❌ ML Training API Error: ${endpoint}`, error.message);
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
 * @param {string} modelType - Model type to use (optional)
 * @param {string} modelName - Model name to use (optional)
 * @returns {Promise<Object>} Prediction data
 */
export const getLatestPrediction = async (tradingPair = 'USD/BRL(OTC)', modelType = null, modelName = null) => {
  let queryParams = [];
  
  if (modelName) {
    queryParams.push(`model_name=${encodeURIComponent(modelName)}`);
  }
  
  if (modelType) {
    queryParams.push(`model_type=${encodeURIComponent(modelType)}`);
  }
  
  const qp = queryParams.length > 0 ? `?${queryParams.join('&')}` : '';
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
export const getModelsForPair = async (tradingPair) => {
  try {
    console.log(`🔍 Fetching models for pair: ${tradingPair}`);
    const data = await apiRequest(`/ml/models/${encodeURIComponent(tradingPair)}`);
    console.log('✅ Models fetched successfully:', data);
    return data;
  } catch (error) {
    console.error('❌ Error fetching models:', error);
    return { local_models: [], cloud_models: [] };
  }
};

/**
 * Trigger model retraining
 * @param {string} tradingPair - Trading pair to retrain model for
 * @param {string} modelType - Model type to train (xgboost, random_forest, lightgbm)
 * @param {boolean} forceRetrain - Force retraining even if model exists
 * @returns {Promise<Object>} Retraining response
 */
export const retrainModel = async (tradingPair = 'USD/BRL(OTC)', modelType = 'xgboost', forceRetrain = false) => {
  // Special handling for LightGBM model type - direct API call to ML training service
  if (modelType.toLowerCase() === 'lightgbm') {
    console.log('🔄 Using direct API call for LightGBM model training');
    return await directMLTrainingRequest('/train', {
      method: 'POST',
      body: JSON.stringify({
        trading_pair: tradingPair,
        model_type: modelType,
        force_retrain: forceRetrain
      })
    });
  }
  
  // Normal API Gateway call for other model types
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

/**
 * Select a model for a trading pair without starting predictions
 * @param {string} tradingPair - Trading pair
 * @param {string} modelName - Model name
 * @param {string} modelType - Model type (optional)
 * @returns {Promise<Object>} Response
 */
export const selectModel = async (tradingPair, modelName, modelType = null) => {
  const payload = {
    trading_pair: tradingPair,
    model_name: modelName,
    model_type: modelType
  };
  const attempt = async () =>
    await apiRequest('/predictions/select_model', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

  try {
    return await attempt();
  } catch (err) {
    console.warn('⚠️ selectModel failed, retrying in 1s...', err?.message || err);
    await new Promise((r) => setTimeout(r, 1000));
    return await attempt();
  }
};

// =============================================================================
// SERVICE STATUS & PREDICTION ACCURACY
// =============================================================================

/**
 * Get individual service statuses from the health endpoint
 * @returns {Promise<Object>} Service statuses map
 */
export const getServiceStatuses = async () => {
  const health = await getHealthStatus();
  return health.services;
};

/**
 * Get prediction accuracy statistics
 * @returns {Promise<Object>} Accuracy data with overall and per-model breakdown
 */
export const getPredictionAccuracy = async () => {
  return await apiRequest('/api/predictions/accuracy');
};

/**
 * Get data collection service status
 * @returns {Promise<Object>} Data collection status
 */
export const getDataCollectionStatus = async () => {
  const response = await fetch(`${DATA_COLLECTION_BASE}/status`);
  return response.json();
};

// =============================================================================
// WEBSOCKET CONNECTIONS
// =============================================================================

/**
 * Create WebSocket connection for predictions
 * @returns {WebSocket} WebSocket connection
 */
export const createPredictionWebSocket = () => new WebSocket(`${getWsBase()}/ws/predictions`);

/**
 * Create WebSocket connection for market data
 * @returns {WebSocket} WebSocket connection
 */
export const createMarketDataWebSocket = () => new WebSocket(`${getWsBase()}/ws/market-data`);

/**
 * Create unified WebSocket connection
 * @returns {WebSocket} WebSocket connection
 */
export const createUnifiedWebSocket = () => new WebSocket(`${getWsBase()}/ws`);

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
  selectModel,

  // Service Status & Accuracy
  getServiceStatuses,
  getPredictionAccuracy,
  getDataCollectionStatus,

  // WebSocket Connections
  createPredictionWebSocket,
  createMarketDataWebSocket,
  createUnifiedWebSocket,
};