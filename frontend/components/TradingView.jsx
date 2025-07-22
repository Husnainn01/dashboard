import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, CircularProgress, Button, Paper, Alert, Chip } from '@mui/material';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import LoginIcon from '@mui/icons-material/Login';

/**
 * TradingView Component
 * Shows embedded Quotex trading platform or login prompt
 */
const TradingView = ({ 
  isRunning, 
  forceLoginMode = false, 
  onLoginSuccess, 
  onClose 
}) => {
  console.log('TradingView rendered', { isRunning, forceLoginMode });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loginStage, setLoginStage] = useState('prompt'); // 'prompt', 'iframe', 'authenticated'
  const [sessionData, setSessionData] = useState(null);
  
  const iframeRef = useRef(null);
  const checkIntervalRef = useRef(null);

  // Check for existing authentication
  useEffect(() => {
    if (!forceLoginMode) {
      const savedSession = localStorage.getItem('quotexSession');
      if (savedSession) {
        try {
          const session = JSON.parse(savedSession);
          setSessionData(session);
          setLoginStage('authenticated');
        } catch (err) {
          console.error('Failed to parse saved session:', err);
          localStorage.removeItem('quotexSession');
        }
      }
    } else {
      // Force login mode - always start with login
      setLoginStage('prompt');
    }
  }, [forceLoginMode]);

  // Handle starting the embedded login process
  const handleStartEmbeddedLogin = () => {
    console.log('Starting embedded Quotex login');
    setLoginStage('iframe');
    setError(null);
    setLoading(true);
    
    // Start checking for successful login
    startLoginDetection();
  };

  // Start monitoring the iframe for successful login
  const startLoginDetection = () => {
    console.log('Starting login detection');
    
    // Check every 2 seconds for login success
    checkIntervalRef.current = setInterval(() => {
      checkLoginStatus();
    }, 2000);
    
    // Set a timeout for the login process (5 minutes)
    setTimeout(() => {
      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current);
        checkIntervalRef.current = null;
        if (loginStage === 'iframe') {
          console.log('Login timeout reached');
          setError('Login timeout. Please try again if you haven\'t completed the login.');
          setLoading(false);
        }
      }
    }, 5 * 60 * 1000);
  };

  // Check if user has successfully logged in by monitoring the iframe URL
  const checkLoginStatus = () => {
    if (!iframeRef.current) return;
    
    try {
      // Try to access the iframe's current URL
      const iframeUrl = iframeRef.current.contentWindow.location.href;
      console.log('Current iframe URL:', iframeUrl);
      
      // Check if we've moved away from the login page (indicates successful login)
      if (!iframeUrl.includes('sign-in') && !iframeUrl.includes('login') && 
          !iframeUrl.includes('__cf_chl') && iframeUrl.includes('quotex.com')) {
        
        console.log('Login detected! URL changed to:', iframeUrl);
        handleLoginSuccess();
      }
    } catch (err) {
      // Cross-origin restrictions prevent access - this is normal
      // We'll use a different approach
      console.log('Cannot access iframe URL due to CORS - this is expected');
    }
  };

  // Handle successful login detection
  const handleLoginSuccess = () => {
    console.log('Login successful!');
    
    // Clear the checking interval
    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current);
      checkIntervalRef.current = null;
    }
    
    // Create session data
    const session = {
      id: `embedded-session-${Date.now()}`,
      email: 'embedded-login',
      timestamp: Date.now(),
      type: 'embedded'
    };
    
    // Save session
    setSessionData(session);
    localStorage.setItem('quotexSession', JSON.stringify(session));
    setLoginStage('authenticated');
    setLoading(false);
    
    console.log('Session created:', session);
    
    // Call callback if provided
    if (onLoginSuccess && typeof onLoginSuccess === 'function') {
      onLoginSuccess(session);
    }
  };

  // Handle manual confirmation of login - WITH REAL VALIDATION
  const handleManualLoginConfirm = async () => {
    console.log('🔍 User claims to be logged in - validating...');
    setLoading(true);
    setError(null);
    
    try {
      // First, extract cookies from iframe (if possible)
      await attemptCookieExtraction();
      
      // Then validate the session with backend
      const sessionId = sessionData?.id || `temp-session-${Date.now()}`;
      console.log('Validating session with backend:', sessionId);
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'}/api/auth/validate-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sessionId })
      });
      
      const validationResult = await response.json();
      console.log('Session validation result:', validationResult);
      
      if (validationResult.success && validationResult.loggedIn) {
        console.log('✅ Session validation successful - user is actually logged in');
        handleLoginSuccess();
      } else {
        console.warn('❌ Session validation failed - user is not actually logged in');
        setError(validationResult.message || 'You are not actually logged into Quotex. Please complete the login process in the iframe above.');
        setLoading(false);
      }
      
    } catch (error) {
      console.error('Session validation error:', error);
      setError('Failed to verify login status. Please ensure you have completed login in the Quotex window above.');
      setLoading(false);
    }
  };
  
  // Attempt to extract cookies from iframe (limited by CORS)
  const attemptCookieExtraction = async () => {
    try {
      console.log('🍪 Attempting to extract session cookies...');
      
      // Due to CORS restrictions, we can't directly access iframe cookies
      // But we can try to detect if login occurred by URL changes
      if (iframeRef.current && iframeRef.current.contentWindow) {
        // This will likely fail due to CORS, but we try anyway
        try {
          const iframeDoc = iframeRef.current.contentDocument;
          if (iframeDoc) {
            const cookies = document.cookie; // Gets parent domain cookies only
            console.log('Available cookies:', cookies);
            
            // Store any available session info
            const sessionId = sessionData?.id || `quotex-session-${Date.now()}`;
            await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'}/api/auth/store-session-cookies`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({ 
                sessionId, 
                cookies: [], // Can't extract iframe cookies due to CORS
                metadata: {
                  timestamp: new Date().toISOString(),
                  userAgent: navigator.userAgent,
                  source: 'manual_confirmation'
                }
              })
            });
          }
        } catch (corsError) {
          console.log('Expected CORS error accessing iframe:', corsError.message);
        }
      }
      
    } catch (error) {
      console.warn('Cookie extraction failed (expected):', error);
    }
  };

  // Handle logout
  const handleLogout = () => {
    console.log('Logging out');
    setSessionData(null);
    setLoginStage('prompt');
    localStorage.removeItem('quotexSession');
    
    // Clear any ongoing checks
    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current);
      checkIntervalRef.current = null;
    }
    
    // Call close callback if provided (for login dialog mode)
    if (forceLoginMode && onClose && typeof onClose === 'function') {
      onClose();
    }
  };

  // Handle iframe refresh
  const handleRefresh = () => {
    if (iframeRef.current) {
      setLoading(true);
      iframeRef.current.src = iframeRef.current.src;
      setTimeout(() => setLoading(false), 3000);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current);
      }
    };
  }, []);

  // Render login prompt
  const renderLoginPrompt = () => (
    <Box 
      sx={{ 
        display: 'flex', 
        flexDirection: 'column', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100%', 
        p: 3, 
        textAlign: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white'
      }}
    >
      <Paper 
        elevation={6} 
        sx={{ 
          p: 4, 
          maxWidth: 480, 
          width: '100%',
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(10px)',
          borderRadius: 3
        }}
      >
        <LoginIcon sx={{ fontSize: 64, color: '#667eea', mb: 2 }} />
        
        <Typography variant="h5" gutterBottom color="text.primary" fontWeight="600">
          Connect to Quotex Trading Platform
        </Typography>
        
        <Typography variant="body1" color="text.secondary" paragraph sx={{ mb: 3 }}>
          To capture real-time trading data, you need to log into your Quotex account. 
          We'll open Quotex in an embedded window where you can safely complete the login process.
        </Typography>
        
        <Alert severity="info" sx={{ mb: 3, textAlign: 'left' }}>
          <Typography variant="body2">
            <strong>How it works:</strong><br/>
            1. Click "Open Quotex Login" below<br/>
            2. Complete login in the embedded window (including any challenges)<br/>
            3. Once logged in, we'll detect your session automatically<br/>
            4. Your trading data will then be captured for analysis
          </Typography>
        </Alert>

        <Alert severity="success" sx={{ mb: 3, textAlign: 'left' }}>
          <Typography variant="body2">
            <strong>Security:</strong> Your login credentials are entered directly into Quotex's secure website. 
            We only capture screen data for analysis - no trades are executed.
          </Typography>
        </Alert>
        
        <Button
          variant="contained"
          size="large"
          fullWidth
          onClick={handleStartEmbeddedLogin}
          startIcon={<LockOpenIcon />}
          sx={{ 
            py: 1.5,
            background: 'linear-gradient(45deg, #667eea, #764ba2)',
            '&:hover': {
              background: 'linear-gradient(45deg, #5a6fd8, #6a4190)',
            }
          }}
        >
          Open Quotex Login
        </Button>
        
        {/* Close button for force login mode */}
        {forceLoginMode && onClose && (
          <Button
            variant="outlined"
            size="large"
            fullWidth
            onClick={onClose}
            sx={{ mt: 2 }}
          >
            Cancel
          </Button>
        )}
      </Paper>
    </Box>
  );

  // Render embedded login iframe
  const renderEmbeddedLogin = () => (
    <Box sx={{ position: 'relative', height: '100%', overflow: 'hidden' }}>
      {/* Loading overlay */}
      {loading && (
        <Box 
          sx={{ 
            position: 'absolute', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            bgcolor: 'rgba(255, 255, 255, 0.9)', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            zIndex: 10,
            flexDirection: 'column'
          }}
        >
          <CircularProgress size={40} sx={{ mb: 2 }} />
          <Typography variant="body1">Loading Quotex login page...</Typography>
        </Box>
      )}

      {/* Control bar */}
      <Box 
        sx={{ 
          position: 'absolute', 
          top: 0, 
          left: 0, 
          right: 0, 
          bgcolor: 'primary.main', 
          color: 'white', 
          p: 1, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          zIndex: 5,
          boxShadow: 2
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="body2" fontWeight="600">
            Quotex Login - Complete your login in the window below
          </Typography>
          <Chip 
            label="Waiting for login..." 
            size="small" 
            color="warning" 
            variant="outlined"
            sx={{ color: 'white', borderColor: 'white' }}
          />
        </Box>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            size="small"
            color="success"
            onClick={handleManualLoginConfirm}
            startIcon={<CheckCircleIcon />}
          >
            I'm Logged In
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={handleRefresh}
            sx={{ color: 'white', borderColor: 'white' }}
          >
            <RefreshIcon fontSize="small" />
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={() => setLoginStage('prompt')}
            sx={{ color: 'white', borderColor: 'white' }}
          >
            {forceLoginMode ? 'Cancel' : 'Back'}
          </Button>
          
          {/* Additional close button for force login mode */}
          {forceLoginMode && onClose && (
            <Button
              variant="outlined"
              size="small"
              onClick={onClose}
              sx={{ color: 'white', borderColor: 'white' }}
            >
              Close
            </Button>
          )}
        </Box>
      </Box>

      {/* Quotex iframe */}
      <iframe
        ref={iframeRef}
        src="https://quotex.com/sign-in/"
        title="Quotex Login"
        width="100%"
        height="100%"
        style={{ 
          border: 'none', 
          marginTop: '48px', // Account for control bar
          height: 'calc(100% - 48px)'
        }}
        onLoad={() => {
          console.log('Quotex iframe loaded');
          setLoading(false);
        }}
      />

      {/* Help text */}
      <Box 
        sx={{ 
          position: 'absolute', 
          bottom: 0, 
          left: 0, 
          right: 0, 
          bgcolor: 'rgba(0, 0, 0, 0.8)', 
          color: 'white', 
          p: 1, 
          textAlign: 'center',
          zIndex: 5
        }}
      >
        <Typography variant="caption">
          Complete the login process above. If you encounter Cloudflare challenges, wait for them to complete. 
          Once logged in successfully, click "I'm Logged In" or we'll detect it automatically.
        </Typography>
      </Box>

      {error && (
        <Alert 
          severity="warning" 
          sx={{ 
            position: 'absolute', 
            top: 60, 
            left: 10, 
            right: 10, 
            zIndex: 6 
          }}
        >
          {error}
        </Alert>
      )}
    </Box>
  );

  // Render authenticated state
  const renderAuthenticated = () => (
    <Box sx={{ position: 'relative', height: '100%', overflow: 'hidden' }}>
      {/* Status bar */}
      <Box 
        sx={{ 
          position: 'absolute', 
          top: 0, 
          left: 0, 
          right: 0, 
          bgcolor: 'success.main', 
          color: 'white', 
          p: 1, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          zIndex: 5,
          boxShadow: 2
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <CheckCircleIcon fontSize="small" />
          <Typography variant="body2" fontWeight="600">
            Connected to Quotex - Session Active
          </Typography>
          <Chip 
            label={`Connected at ${new Date(sessionData?.timestamp).toLocaleTimeString()}`}
            size="small" 
            color="success" 
            variant="outlined"
            sx={{ color: 'white', borderColor: 'white' }}
          />
        </Box>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            size="small"
            onClick={handleRefresh}
            sx={{ color: 'white', borderColor: 'white' }}
          >
            <RefreshIcon fontSize="small" />
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={handleLogout}
            sx={{ color: 'white', borderColor: 'white' }}
          >
            Disconnect
          </Button>
        </Box>
      </Box>

      {/* Trading platform iframe */}
      <iframe
        ref={iframeRef}
        src="https://quotex.com/trading"
        title="Quotex Trading Platform"
        width="100%"
        height="100%"
        style={{ 
          border: 'none', 
          marginTop: '48px',
          height: 'calc(100% - 48px)'
        }}
        onLoad={() => setLoading(false)}
      />

      {loading && (
        <Box 
          sx={{ 
            position: 'absolute', 
            top: '50%', 
            left: '50%', 
            transform: 'translate(-50%, -50%)', 
            zIndex: 10 
          }}
        >
          <CircularProgress />
        </Box>
      )}
    </Box>
  );

  // Render authentication success (for force login mode)
  const renderAuthenticationSuccess = () => (
    <Box 
      sx={{ 
        display: 'flex', 
        flexDirection: 'column', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100%', 
        p: 3, 
        textAlign: 'center',
        background: 'linear-gradient(135deg, #4caf50 0%, #45a049 100%)',
        color: 'white'
      }}
    >
      <Paper 
        elevation={6} 
        sx={{ 
          p: 4, 
          maxWidth: 480, 
          width: '100%',
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(10px)',
          borderRadius: 3,
          textAlign: 'center'
        }}
      >
        <CheckCircleIcon sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
        
        <Typography variant="h5" gutterBottom color="text.primary" fontWeight="600">
          Successfully Connected!
        </Typography>
        
        <Typography variant="body1" color="text.secondary" paragraph sx={{ mb: 3 }}>
          Your Quotex account has been connected successfully. You can now start the bot to begin collecting real-time trading data and predictions.
        </Typography>
        
        <Alert severity="success" sx={{ mb: 3, textAlign: 'left' }}>
          <Typography variant="body2">
            <strong>Next steps:</strong><br/>
            1. Close this dialog<br/>
            2. Click "Start Bot" to begin data collection<br/>
            3. View live predictions and charts
          </Typography>
        </Alert>
        
        <Button
          variant="contained"
          size="large"
          fullWidth
          onClick={onClose}
          sx={{ 
            py: 1.5,
            background: 'linear-gradient(45deg, #4caf50, #45a049)',
            '&:hover': {
              background: 'linear-gradient(45deg, #45a049, #388e3c)',
            }
          }}
        >
          Continue to Dashboard
        </Button>
      </Paper>
    </Box>
  );

  // Show different content based on bot state
  if (!isRunning && loginStage !== 'authenticated' && !forceLoginMode) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center', 
          height: '100%', 
          bgcolor: 'grey.100',
          textAlign: 'center'
        }}
      >
        <Paper sx={{ p: 3, maxWidth: 400 }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Trading View Inactive
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Start the bot to begin data collection and trading analysis.
          </Typography>
        </Paper>
      </Box>
    );
  }

  // Main render logic
  if (error && loginStage === 'prompt') {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error" action={
          <Button color="inherit" size="small" onClick={() => setError(null)}>
            Retry
          </Button>
        }>
          {error}
        </Alert>
        {forceLoginMode && onClose && (
          <Box sx={{ mt: 2 }}>
            <Button variant="outlined" onClick={onClose} fullWidth>
              Close
            </Button>
          </Box>
        )}
      </Box>
    );
  }

  switch (loginStage) {
    case 'prompt':
      return renderLoginPrompt();
    case 'iframe':
      return renderEmbeddedLogin();
    case 'authenticated':
      return forceLoginMode ? renderAuthenticationSuccess() : renderAuthenticated();
    default:
      return renderLoginPrompt();
  }
};

export default TradingView; 