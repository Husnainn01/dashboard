import React, { useState, useEffect } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Container,
  Grid,
  Paper,
  IconButton,
  Drawer,
  CircularProgress,
  Chip,
  Avatar,
  Button,
  useTheme
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';
import SettingsIcon from '@mui/icons-material/Settings';
import HistoryIcon from '@mui/icons-material/History';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';

import CandleChart from './charts/CandleChart';
import PredictionCard from './prediction/PredictionCard';
import BotControls from './controls/BotControls';
import SettingsPanel from './controls/SettingsPanel';
import TradingView from './TradingView';
import HistoryPanel from './HistoryPanel';

import { fetchMockData, startBot, stopBot, getLatestPrediction } from '../services/api';

/**
 * Dashboard Component
 * Main component for the OTC trading predictor dashboard
 * Authentication is now handled internally by TradingView component
 */
const Dashboard = () => {
  console.log('Dashboard rendered');
  
  const theme = useTheme();
  
  // Core state
  const [loading, setLoading] = useState(false); // Start with false to avoid loading loop
  const [error, setError] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  
  // Data state
  const [candleData, setCandleData] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(null);
  
  // UI state
  const [darkMode, setDarkMode] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showLogin, setShowLogin] = useState(false); // Add login dialog state
  
  // Authentication state (derived from localStorage)
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  
  // Check authentication status with backend validation for persistent sessions
  const checkAuthStatus = async () => {
    try {
      const savedSession = localStorage.getItem('quotexSession');
      if (!savedSession) {
        console.log('No saved session found');
        setIsAuthenticated(false);
        return false;
      }

      const sessionData = JSON.parse(savedSession);
      console.log('Checking saved session:', sessionData.id);

      // Validate with backend to check persistent session
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'}/api/auth/validate-session`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ sessionId: sessionData.id })
        });

        const validationResult = await response.json();
        console.log('Session validation result:', validationResult);

        if (validationResult.success && validationResult.loggedIn) {
          console.log('✅ Persistent session valid - user stays logged in!');
          
          // Update session with any new info
          if (validationResult.details?.cached) {
            console.log('⚡ Using cached session - instant login!');
          }
          
          setIsAuthenticated(true);
          return true;
        } else {
          console.log('❌ Session invalid, removing from storage');
          localStorage.removeItem('quotexSession');
          setIsAuthenticated(false);
          return false;
        }

      } catch (validationError) {
        console.warn('Session validation failed, assuming logged out:', validationError.message);
        setIsAuthenticated(false);
        return false;
      }

    } catch (error) {
      console.error('Error checking auth status:', error);
      setIsAuthenticated(false);
      return false;
    }
  };

  // Initialize component on mount
  useEffect(() => {
    console.log('Dashboard useEffect: initializing component');
    
    const initializeApp = async () => {
      setLoading(true);
      
      try {
        // Check authentication status
        const isAuth = await checkAuthStatus();
        console.log('Initial auth status:', isAuth);
        
        // If authenticated, fetch initial data
        if (isAuth) {
          console.log('User authenticated on mount, fetching initial data');
          await fetchInitialData();
        } else {
          console.log('User not authenticated on mount');
          setCandleData([]);
          setPrediction(null);
        }
      } catch (error) {
        console.error('Error during app initialization:', error);
        setError('Failed to initialize application');
      } finally {
        setLoading(false);
        setInitialLoadComplete(true);
      }
    };

    initializeApp();
    
    // Check auth status periodically
    const authCheckInterval = setInterval(checkAuthStatus, 5000);
    
    // Clean up on unmount
    return () => {
      console.log('Dashboard unmounting: cleaning up');
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
      if (authCheckInterval) {
        clearInterval(authCheckInterval);
      }
    };
  }, []);
  
  // Fetch initial data from API
  const fetchInitialData = async () => {
    console.log('Fetching initial data');
    
    try {
      // Only fetch data if user is authenticated
      if (!isAuthenticated) {
        console.log('User not authenticated, skipping data fetch');
        setCandleData([]);
        setPrediction(null);
        return;
      }

      // Fetch data from API
      const data = await fetchMockData();
      console.log('Initial data received:', data);
      
      // Update state
      setCandleData(data.candles);
      setPrediction(data.prediction);
    } catch (err) {
      console.error('Error fetching initial data:', err);
      setError(err.message || 'Failed to fetch data');
    }
  };
  
  // Re-fetch data when authentication status changes (but not on initial load)
  useEffect(() => {
    if (!initialLoadComplete) {
      return; // Skip during initial load
    }
    
    if (isAuthenticated) {
      console.log('User authenticated, fetching initial data');
      setLoading(true);
      fetchInitialData().finally(() => setLoading(false));
    } else {
      console.log('User not authenticated, clearing data');
      setCandleData([]);
      setPrediction(null);
      
      // Stop bot if running
      if (isRunning) {
        console.log('Stopping bot due to authentication loss');
        setIsRunning(false);
        if (refreshInterval) {
          clearInterval(refreshInterval);
          setRefreshInterval(null);
        }
      }
    }
  }, [isAuthenticated, initialLoadComplete]);
  
  // Simulate new data when bot is running
  const setupDataRefresh = () => {
    console.log('Setting up data refresh interval');
    
    // Only set up refresh if authenticated
    if (!isAuthenticated) {
      console.log('User not authenticated, skipping data refresh setup');
      return;
    }
    
    if (refreshInterval) {
      console.log('Clearing existing refresh interval');
      clearInterval(refreshInterval);
    }
    
    const interval = setInterval(async () => {
      try {
        // Double-check authentication before generating data
        if (!checkAuthStatus()) {
          console.log('Authentication lost during refresh, stopping data generation');
          return;
        }

        // Get new candle data
        const newCandle = {
          timestamp: new Date().toISOString(),
          direction: Math.random() > 0.5 ? 'up' : 'down',
          open: 1.2345 + (Math.random() - 0.5) * 0.01,
          close: 1.2345 + (Math.random() - 0.5) * 0.01,
          high: 1.2345 + Math.random() * 0.01,
          low: 1.2345 - Math.random() * 0.01,
          tradingPair: 'EUR/USD OTC',
          timeframe: 60
        };
        newCandle.direction = newCandle.close > newCandle.open ? 'up' : 'down';
        
        console.log('New candle generated:', newCandle);
        
        // Update candle data
        setCandleData(prevData => {
          // Keep only the latest 20 candles
          const newData = [...prevData.slice(1), newCandle];
          return newData;
        });
        
        // Get new prediction
        const newPrediction = await getLatestPrediction();
        console.log('New prediction received:', newPrediction);
        setPrediction(newPrediction);
      } catch (err) {
        console.error('Error refreshing data:', err);
        setError(err.message || 'Failed to refresh data');
      }
    }, 15000);
    
    setRefreshInterval(interval);
    
    // Clean up on unmount
    return () => {
      console.log('Clearing refresh interval');
      clearInterval(interval);
    };
  };
  
  // Toggle bot running state
  const toggleBot = async () => {
    console.log('Toggling bot state. Current state:', isRunning);
    
    // Check authentication before starting bot
    if (!isRunning && !isAuthenticated) {
      console.log('User not authenticated, cannot start bot');
      setError('Please connect to your Quotex account first');
      return;
    }
    
    try {
      setLoading(true);
      
      if (!isRunning) {
        // Start the bot
        console.log('Starting bot...');
        const result = await startBot();
        console.log('Start bot result:', result);
        
        if (result.success) {
          console.log('Bot started successfully');
          setIsRunning(true);
          setupDataRefresh();
        } else {
          console.error('Failed to start bot:', result.message);
          throw new Error(result.message || 'Failed to start bot');
        }
      } else {
        // Stop the bot
        console.log('Stopping bot...');
        const result = await stopBot();
        console.log('Stop bot result:', result);
        
        if (result.success) {
          console.log('Bot stopped successfully');
          setIsRunning(false);
          
          if (refreshInterval) {
            console.log('Clearing refresh interval');
            clearInterval(refreshInterval);
            setRefreshInterval(null);
          }
        } else {
          console.error('Failed to stop bot:', result.message);
          throw new Error(result.message || 'Failed to stop bot');
        }
      }
    } catch (err) {
      console.error('Error toggling bot state:', err);
      setError(err.message || 'Failed to toggle bot state');
    } finally {
      setLoading(false);
    }
  };
  
  // Handle theme toggle
  const toggleDarkMode = () => {
    console.log('Toggling dark mode');
    setDarkMode(prevMode => !prevMode);
  };

  const handleLogout = () => {
    console.log('Logging out...');
    localStorage.removeItem('quotexSession');
    setIsAuthenticated(false);
    setCandleData([]);
    setPrediction(null);
    setIsRunning(false);
    if (refreshInterval) {
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
    setError('Disconnected from Quotex account.');
  };

  const handleLoginSuccess = async () => {
    console.log('Login successful, re-authenticating...');
    
    try {
      const isAuth = await checkAuthStatus(); // Re-check auth status to update UI
      
      if (isAuth) {
        console.log('✅ Login success confirmed by persistent session system');
        setShowLogin(false);
        setError(null);
        
        // Fetch initial data now that user is authenticated
        await fetchInitialData();
      } else {
        console.warn('⚠️ Login success but session validation failed');
        setError('Login verification failed. Please try again.');
      }
      
    } catch (error) {
      console.error('Error during login success handling:', error);
      setError('Login verification encountered an error.');
    }
  };
  
  if (loading && !initialLoadComplete) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          bgcolor: 'background.default'
        }}
      >
        <CircularProgress size={50} sx={{ mb: 2 }} />
        <Typography variant="h6" color="text.secondary">
          Loading OTC Predictor Dashboard...
        </Typography>
      </Box>
    );
  }

  // Calculate if predictions are active (authenticated + bot running)
  const isPredictionActive = isAuthenticated && isRunning;
  console.log('Prediction active status:', { isAuthenticated, isRunning, isPredictionActive });
  
  return (
    <div className="dashboard">
      {/* App Bar */}
      <AppBar position="static" elevation={0} sx={{ 
        bgcolor: 'primary.main',
        borderBottom: 1,
        borderColor: 'divider'
      }}>
        <Toolbar>
          {/* Logo/Title */}
          <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
            <TrendingUpIcon sx={{ mr: 1, fontSize: 28 }} />
            <Typography variant="h6" component="div" fontWeight="600">
              OTC Predictor
            </Typography>
            
            {/* Status Chip */}
            <Chip
              label={isRunning ? 'Active' : 'Inactive'}
              color={isRunning ? 'success' : 'default'}
              size="small"
              sx={{ ml: 2, fontWeight: '500' }}
            />
            
            {/* Authentication Status */}
            {isAuthenticated && (
              <Chip
                label="Connected"
                color="success"
                variant="outlined"
                size="small"
                sx={{ ml: 1, fontWeight: '500' }}
              />
            )}
          </Box>
          
          {/* Action Icons */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {/* Account Connection */}
            {!isAuthenticated ? (
              <Button
                variant="contained"
                color="primary"
                size="small"
                onClick={() => setShowLogin(true)}
                sx={{ mr: 2, fontWeight: '500' }}
              >
                Connect Account
              </Button>
            ) : (
              <Button
                variant="outlined"
                color="inherit"
                size="small"
                onClick={handleLogout}
                sx={{ mr: 2, color: 'white', borderColor: 'rgba(255,255,255,0.5)' }}
              >
                Disconnect
              </Button>
            )}
            
            {/* Bot Status */}
            {isRunning && (
              <Chip 
                label="Collecting Data"
                color="primary"
                size="small"
                icon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
                sx={{ mr: 1 }}
              />
            )}
            
            {/* Dark Mode Toggle */}
            <IconButton 
              color="inherit" 
              onClick={toggleDarkMode}
              title="Toggle theme"
            >
              {darkMode ? <LightModeIcon /> : <DarkModeIcon />}
            </IconButton>
            
            {/* History */}
            <IconButton 
              color="inherit" 
              onClick={() => setShowHistory(true)}
              title="View history"
            >
              <HistoryIcon />
            </IconButton>
            
            {/* Settings */}
            <IconButton 
              color="inherit" 
              onClick={() => setShowSettings(true)}
              title="Settings"
            >
              <SettingsIcon />
            </IconButton>
          </Box>
        </Toolbar>
      </AppBar>
      
      {/* Error Display */}
      {error && (
        <Box sx={{ p: 2, bgcolor: 'error.light', color: 'error.contrastText' }}>
          <Typography variant="body2">
            <strong>Error:</strong> {error}
          </Typography>
          <Button 
            size="small" 
            color="inherit" 
            onClick={() => setError(null)}
            sx={{ ml: 2 }}
          >
            Dismiss
          </Button>
        </Box>
      )}
      
      <Container maxWidth="xl" sx={{ mt: 2, mb: 2 }}>
        <Grid container spacing={3}>
          {/* Left Panel - Charts and Predictions */}
          <Grid item xs={12} md={6} lg={5}>
            <Grid container spacing={2}>
              {/* Candlestick Chart */}
              <Grid item xs={12}>
                <Paper elevation={2} sx={{ p: 2, height: '400px' }}>
                  <Typography variant="h6" gutterBottom>
                    Live Chart - EUR/USD OTC
                    {isAuthenticated && isRunning && (
                      <Typography 
                        component="span" 
                        variant="caption" 
                        sx={{ 
                          ml: 1, 
                          px: 1, 
                          py: 0.5, 
                          bgcolor: 'success.light', 
                          color: 'success.contrastText',
                          borderRadius: 0.5,
                          fontWeight: 'bold'
                        }}
                      >
                        LIVE
                      </Typography>
                    )}
                  </Typography>
                  <CandleChart 
                    data={candleData} 
                    loading={loading}
                    isActive={isPredictionActive}
                  />
                </Paper>
              </Grid>
              
              {/* Prediction Card with Visual Chart */}
              <Grid item xs={12}>
                <PredictionCard 
                  prediction={prediction} 
                  recentCandles={candleData}
                  isActive={isPredictionActive}
                  loading={loading}
                />
              </Grid>
            </Grid>
          </Grid>
          
          {/* Right Panel - Trading View */}
          <Grid item xs={12} md={6} lg={7}>
            <Paper elevation={2} sx={{ height: '600px', overflow: 'hidden' }}>
              <TradingView isRunning={isRunning} />
            </Paper>
          </Grid>
          
          {/* Bot Controls */}
          <Grid item xs={12}>
            <BotControls
              isRunning={isRunning}
              loading={loading}
              onToggle={toggleBot}
            />
          </Grid>
        </Grid>
      </Container>
      
      {/* Settings Panel */}
      <Drawer
        anchor="right"
        open={showSettings}
        onClose={() => setShowSettings(false)}
      >
        <Box sx={{ width: 350 }}>
          <SettingsPanel onClose={() => setShowSettings(false)} />
        </Box>
      </Drawer>
      
      {/* History Panel */}
      <Drawer
        anchor="right"
        open={showHistory}
        onClose={() => setShowHistory(false)}
      >
        <Box sx={{ width: 550 }}>
          <HistoryPanel onClose={() => setShowHistory(false)} data={candleData} />
        </Box>
      </Drawer>
      
      {/* Login Dialog */}
      <Drawer
        anchor="right"
        open={showLogin}
        onClose={() => setShowLogin(false)}
      >
        <Box sx={{ width: 600, height: '100%' }}>
          <TradingView 
            isRunning={false} 
            forceLoginMode={true}
            onLoginSuccess={handleLoginSuccess}
            onClose={() => setShowLogin(false)}
          />
        </Box>
      </Drawer>
    </div>
  );
};

export default Dashboard; 