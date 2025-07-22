/**
 * API Service
 * Provides functions to communicate with the backend API
 * Updated to use simplified session-based authentication for embedded login
 */
console.log('API Service loaded - using embedded session approach');

// API base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001/api';
console.log('API base URL:', API_BASE_URL);

// Mock candle data generator
const generateMockCandleData = (count = 20) => {
  const candles = [];
  let basePrice = 1.2345;
  const now = new Date();
  
  for (let i = 0; i < count; i++) {
    // Calculate time (starting from the past)
    const timestamp = new Date(now.getTime() - (count - i) * 60000).toISOString();
    
    // Random price movement
    const movement = (Math.random() - 0.5) * 0.01;
    basePrice += movement;
    
    // Create candle data
    const open = basePrice;
    const close = basePrice + (Math.random() - 0.5) * 0.005;
    const high = Math.max(open, close) + Math.random() * 0.003;
    const low = Math.min(open, close) - Math.random() * 0.003;
    const direction = close > open ? 'up' : 'down';
    
    candles.push({
      timestamp,
      open,
      close,
      high,
      low,
      direction,
      tradingPair: 'EUR/USD OTC',
      timeframe: 60
    });
  }
  
  return candles;
};

// Mock prediction generator
const generateMockPrediction = () => {
  const direction = Math.random() > 0.5 ? 'up' : 'down';
  const confidence = Math.floor(Math.random() * 30) + 60;
  
  return {
    direction,
    confidence,
    patternId: 'pattern_' + Date.now().toString(16).slice(-6),
    timestamp: new Date().toISOString(),
    similarPatternsCount: Math.floor(Math.random() * 10) + 1
  };
};

/**
 * Fetch mock data for development
 * @returns {Promise<Object>} Mock data
 */
export const fetchMockData = async () => {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 500));
  
  return {
    candles: generateMockCandleData(20),
    prediction: generateMockPrediction()
  };
};

/**
 * Start the trading bot
 * @returns {Promise<Object>} Response
 */
export const startBot = async () => {
  console.log('startBot called');
  
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 1500));
  
  console.log('Bot started successfully');
  return { success: true, message: 'Bot started successfully' };
};

/**
 * Stop the trading bot
 * @returns {Promise<Object>} Response
 */
export const stopBot = async () => {
  console.log('stopBot called');
  
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 1000));
  
  console.log('Bot stopped successfully');
  return { success: true, message: 'Bot stopped successfully' };
};

/**
 * Create a new session for embedded login
 * @param {Object} sessionData - Session data (email, etc.)
 * @returns {Promise<Object>} Session creation response
 */
export const createSession = async (sessionData = {}) => {
  console.log('createSession called');
  console.log('Session data:', sessionData);
  
  try {
    // Always try the backend first
    console.log(`Creating session at ${API_BASE_URL}/auth/create-session`);
    
    try {
      const response = await fetch(`${API_BASE_URL}/auth/create-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(sessionData),
      });
      
      console.log('Create session response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Session created successfully:', data);
        return data;
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Session creation failed:', errorData);
        throw new Error(errorData.message || `HTTP ${response.status}`);
      }
    } catch (fetchError) {
      console.error('Backend connection failed:', fetchError.message);
      
      // Fallback to mock session creation in development
      if (process.env.NODE_ENV === 'development') {
        console.log('Falling back to mock session creation');
        
        await new Promise(resolve => setTimeout(resolve, 800));
        
        const mockSession = {
          success: true,
          message: 'Session created successfully (mock)',
          session: {
            id: `mock-session-${Date.now()}`,
            email: sessionData.email || 'mock-user@example.com',
            timestamp: Date.now(),
            type: 'embedded'
          }
        };
        
        console.log('Mock session created:', mockSession);
        return mockSession;
      } else {
        throw fetchError;
      }
    }
  } catch (error) {
    console.error('Session creation error:', error);
    return { 
      success: false, 
      message: 'Failed to create session',
      error: error.message
    };
  }
};

/**
 * Validate an existing session
 * @param {string} sessionId - Session ID to validate
 * @param {Object} updateData - Optional data to update (email, etc.)
 * @returns {Promise<Object>} Validation response
 */
export const validateSession = async (sessionId, updateData = {}) => {
  console.log('validateSession called');
  console.log('Session ID:', sessionId);
  console.log('Update data:', updateData);
  
  try {
    // Try the backend first
    console.log(`Validating session at ${API_BASE_URL}/auth/validate-session`);
    
    try {
      const response = await fetch(`${API_BASE_URL}/auth/validate-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sessionId, ...updateData }),
      });
      
      console.log('Validate session response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Session validation successful:', data);
        return data;
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Session validation failed:', errorData);
        throw new Error(errorData.message || `HTTP ${response.status}`);
      }
    } catch (fetchError) {
      console.error('Backend connection failed:', fetchError.message);
      
      // Fallback to mock validation in development
      if (process.env.NODE_ENV === 'development') {
        console.log('Falling back to mock session validation');
        
        await new Promise(resolve => setTimeout(resolve, 300));
        
        const mockValidation = {
          success: true,
          message: 'Session is valid (mock)',
          session: {
            id: sessionId,
            email: updateData.email || 'mock-user@example.com',
            timestamp: Date.now() - 300000, // 5 minutes ago
            type: 'embedded',
            lastActivity: Date.now()
          }
        };
        
        console.log('Mock session validation:', mockValidation);
        return mockValidation;
      } else {
        throw fetchError;
      }
    }
  } catch (error) {
    console.error('Session validation error:', error);
    return { 
      success: false, 
      message: 'Session validation failed',
      error: error.message
    };
  }
};

/**
 * Logout and end session
 * @param {string} sessionId - Session ID to end
 * @returns {Promise<Object>} Logout response
 */
export const logoutSession = async (sessionId) => {
  console.log('logoutSession called');
  console.log('Session ID:', sessionId);
  
  try {
    // Try the backend first
    console.log(`Logging out session at ${API_BASE_URL}/auth/logout`);
    
    try {
      const response = await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sessionId }),
      });
      
      console.log('Logout response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Logout successful:', data);
        return data;
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Logout failed:', errorData);
        throw new Error(errorData.message || `HTTP ${response.status}`);
      }
    } catch (fetchError) {
      console.error('Backend connection failed:', fetchError.message);
      
      // Fallback to mock logout in development
      if (process.env.NODE_ENV === 'development') {
        console.log('Falling back to mock logout');
        
        await new Promise(resolve => setTimeout(resolve, 500));
        
        const mockLogout = {
          success: true,
          message: 'Logged out successfully (mock)'
        };
        
        console.log('Mock logout:', mockLogout);
        return mockLogout;
      } else {
        throw fetchError;
      }
    }
  } catch (error) {
    console.error('Logout error:', error);
    return { 
      success: false, 
      message: 'Logout failed',
      error: error.message
    };
  }
};

/**
 * Check session status
 * @param {string} sessionId - Session ID to check
 * @returns {Promise<Object>} Session status
 */
export const checkSessionStatus = async (sessionId) => {
  console.log('checkSessionStatus called');
  console.log('Session ID:', sessionId);
  
  try {
    // Try the backend first
    console.log(`Checking session status at ${API_BASE_URL}/auth/status/${sessionId}`);
    
    try {
      const response = await fetch(`${API_BASE_URL}/auth/status/${sessionId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      console.log('Session status response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Session status check successful:', data);
        return data;
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Session status check failed:', errorData);
        throw new Error(errorData.message || `HTTP ${response.status}`);
      }
    } catch (fetchError) {
      console.error('Backend connection failed:', fetchError.message);
      
      // Fallback to mock status check in development
      if (process.env.NODE_ENV === 'development') {
        console.log('Falling back to mock session status check');
        
        await new Promise(resolve => setTimeout(resolve, 200));
        
        const mockStatus = {
          success: true,
          message: 'Session is active (mock)',
          session: {
            id: sessionId,
            email: 'mock-user@example.com',
            lastActivity: Date.now(),
            type: 'embedded',
            status: 'active'
          }
        };
        
        console.log('Mock session status:', mockStatus);
        return mockStatus;
      } else {
        throw fetchError;
      }
    }
  } catch (error) {
    console.error('Session status check error:', error);
    return { 
      success: false, 
      message: 'Failed to check session status',
      error: error.message
    };
  }
};

/**
 * Fetch historical candle data
 * @param {Object} params - Query parameters
 * @returns {Promise<Array>} Candle data
 */
export const fetchHistoricalData = async (params = {}) => {
  console.log('fetchHistoricalData called with params:', params);
  
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 800));
  
  const { count = 50, tradingPair = 'EUR/USD OTC' } = params;
  
  const data = generateMockCandleData(count);
  console.log(`Generated ${data.length} mock candles for ${tradingPair}`);
  
  return data;
};

/**
 * Get latest prediction
 * @returns {Promise<Object>} Prediction
 */
export const getLatestPrediction = async () => {
  console.log('getLatestPrediction called');
  
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 300));
  
  const prediction = generateMockPrediction();
  console.log('Generated prediction:', prediction);
  
  return prediction;
};

/**
 * Save settings to backend
 * @param {Object} settings - Settings to save
 * @returns {Promise<Object>} Response
 */
export const saveSettings = async (settings) => {
  console.log('saveSettings called with:', settings);
  
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 1000));
  
  console.log('Settings saved successfully');
  return { 
    success: true, 
    message: 'Settings saved successfully',
    settings
  };
};

/**
 * Get bot status
 * @returns {Promise<Object>} Bot status
 */
export const getBotStatus = async () => {
  console.log('getBotStatus called');
  
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 200));
  
  const status = { 
    running: Math.random() > 0.5,
    uptime: Math.floor(Math.random() * 3600), // seconds
    candlesProcessed: Math.floor(Math.random() * 1000),
    lastPrediction: generateMockPrediction()
  };
  
  console.log('Bot status:', status);
  return status;
};

// Legacy compatibility functions (deprecated - use new session functions instead)
export const authenticateQuotex = async (credentials) => {
  console.warn('authenticateQuotex is deprecated, use createSession instead');
  return createSession({ email: credentials.email });
};

export const verifyOtp = async (pendingSessionId, otpCode) => {
  console.warn('verifyOtp is deprecated, OTP is now handled in embedded iframe');
  return { success: true, message: 'OTP handled in embedded login' };
};

export const logoutQuotex = async (sessionId) => {
  console.warn('logoutQuotex is deprecated, use logoutSession instead');
  return logoutSession(sessionId);
};

// Default export
export default {
  // Core data functions
  fetchMockData,
  startBot,
  stopBot,
  fetchHistoricalData,
  getLatestPrediction,
  saveSettings,
  getBotStatus,
  
  // New session-based authentication functions
  createSession,
  validateSession,
  logoutSession,
  checkSessionStatus,
  
  // Legacy compatibility (deprecated)
  authenticateQuotex,
  verifyOtp,
  logoutQuotex
}; 