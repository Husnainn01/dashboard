/**
 * API Service
 * Provides functions to communicate with the OTC Predictor API Gateway
 * Updated for microservices architecture
 */

// Dynamic base URLs with runtime override via localStorage
const getApiBase = () => {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('api_base_url');
    if (stored) return stored;
  }
  return process.env.NEXT_PUBLIC_API_URL || '';
};

const getWsBase = () => {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('ws_base_url');
    if (stored) return stored;
  }
  return process.env.NEXT_PUBLIC_WS_URL || '';
};

export const setApiBaseUrl = (url) => {
  if (typeof window !== 'undefined') {
    if (url) localStorage.setItem('api_base_url', url); else localStorage.removeItem('api_base_url');
  }
};

export const setWsBaseUrl = (url) => {
  if (typeof window !== 'undefined') {
    if (url) localStorage.setItem('ws_base_url', url); else localStorage.removeItem('ws_base_url');
  }
};

console.log('🔌 API Service base:', getApiBase() || '(unset)');
console.log('📡 WebSocket base:', getWsBase() || '(unset)');

// ML Training Service URL (direct access)
const ML_TRAINING_URL = process.env.NEXT_PUBLIC_ML_TRAINING_URL || '';

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
    const url = `${ML_TRAINING_URL}${endpoint}${cacheBuster}`;
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
    const base = getApiBase();
    console.log(`🔗 API URL: ${base}/ml/models/${encodeURIComponent(tradingPair)}`);
    
    const response = await fetch(`${base}/ml/models/${encodeURIComponent(tradingPair)}`);
    console.log(`📊 Response status: ${response.status}`);
    
    if (!response.ok) {
      console.error(`❌ Error response: ${response.status} ${response.statusText}`);
      throw new Error(`Error fetching models: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('✅ Models fetched successfully:', data);
    console.log(`📊 Found ${data.local_count} local models and ${data.cloud_count} cloud models`);
    
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
  selectModel,
  
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