import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  CircularProgress,
  Alert,
  Divider,
  FormControlLabel,
  Checkbox
} from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';

// Import API service and OTP verification component
import { authenticateQuotex, verifyOtp } from '../services/api';
import OtpVerification from './OtpVerification';

/**
 * QuotexLogin Component
 * Handles authentication with Quotex trading platform
 */
const QuotexLogin = ({ open, onClose, onLogin }) => {
  console.log('QuotexLogin rendered', { open });
  
  const [credentials, setCredentials] = useState({
    email: '',
    password: '',
    rememberMe: true
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // OTP verification state
  const [showOtpVerification, setShowOtpVerification] = useState(false);
  const [pendingSessionId, setPendingSessionId] = useState(null);
  
  // Handle input change
  const handleChange = (e) => {
    const { name, value, checked, type } = e.target;
    const newValue = type === 'checkbox' ? checked : value;
    console.log(`Input changed: ${name} = ${newValue}`);
    
    setCredentials(prev => ({
      ...prev,
      [name]: newValue
    }));
  };
  
  // Handle login form submission
  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    
    console.log('Login form submitted');
    console.log('Credentials:', { email: credentials.email, passwordLength: credentials.password?.length });
    
    setError(null);
    setLoading(true);
    
    try {
      console.log('Calling authenticateQuotex API...');
      // Call the authentication API
      const result = await authenticateQuotex({
        email: credentials.email,
        password: credentials.password
      });
      
      console.log('Authentication API response:', result);
      
      if (!result.success) {
        console.error('Authentication failed:', result.message);
        throw new Error(result.message || 'Authentication failed');
      }
      
      // Check if OTP verification is required
      if (result.requiresOtp) {
        console.log('OTP verification required, showing OTP dialog');
        console.log('Pending session ID:', result.pendingSessionId);
        
        setLoading(false);
        setPendingSessionId(result.pendingSessionId);
        setShowOtpVerification(true);
        return;
      }
      
      // If OTP not required, proceed with login
      console.log('Authentication successful, no OTP required');
      console.log('Session data:', result.session);
      
      // Reset loading state before calling onLogin
      setLoading(false);
      
      // Call onLogin callback with session data
      if (onLogin && typeof onLogin === 'function') {
        onLogin(result.session);
      } else {
        console.error('onLogin is not a valid function', onLogin);
      }
      
      // Close dialog
      onClose();
    } catch (err) {
      console.error('Authentication error:', err);
      setError(err.message || 'Authentication failed');
      setLoading(false);
    }
  };
  
  // Handle OTP verification
  const handleOtpVerify = async (otpCode) => {
    console.log('OTP verification requested');
    console.log('OTP Code:', otpCode);
    console.log('Pending session ID:', pendingSessionId);
    
    try {
      console.log('Calling verifyOtp API...');
      // Call the OTP verification API
      const result = await verifyOtp(pendingSessionId, otpCode);
      
      console.log('OTP verification API response:', result);
      
      if (!result.success) {
        console.error('OTP verification failed:', result.message);
        throw new Error(result.message || 'Verification failed');
      }
      
      // Verification successful, call the login callback
      console.log('OTP verification successful');
      console.log('Session data:', result.session);
      
      // Reset OTP loading state
      setLoading(false);
      
      // Call onLogin callback with session data
      if (onLogin && typeof onLogin === 'function') {
        onLogin(result.session);
      } else {
        console.error('onLogin is not a valid function', onLogin);
      }
      
      // Close both dialogs
      setShowOtpVerification(false);
      onClose();
      
      return true;
    } catch (error) {
      console.error('OTP verification error:', error);
      // Rethrow the error to be handled by the OTP component
      throw error;
    }
  };
  
  // Handle closing OTP verification dialog
  const handleOtpClose = () => {
    console.log('OTP verification dialog closed by user');
    setShowOtpVerification(false);
  };
  
  return (
    <>
      <Dialog 
        open={open && !showOtpVerification} 
        onClose={loading ? undefined : onClose}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center' }}>
          <LockIcon sx={{ mr: 1 }} />
          Connect to Quotex Account
        </DialogTitle>
        
        <Divider />
        
        <DialogContent>
          <Box component="form" onSubmit={handleSubmit} noValidate sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary" paragraph>
              Enter your Quotex credentials to connect securely. Your credentials are only used to establish a connection and are not stored.
            </Typography>
            
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            
            <TextField
              margin="normal"
              required
              fullWidth
              id="email"
              label="Email Address"
              name="email"
              autoComplete="email"
              autoFocus
              value={credentials.email}
              onChange={handleChange}
              disabled={loading}
            />
            
            <TextField
              margin="normal"
              required
              fullWidth
              name="password"
              label="Password"
              type="password"
              id="password"
              autoComplete="current-password"
              value={credentials.password}
              onChange={handleChange}
              disabled={loading}
            />
            
            <FormControlLabel
              control={
                <Checkbox 
                  value="remember" 
                  color="primary" 
                  name="rememberMe"
                  checked={credentials.rememberMe}
                  onChange={handleChange}
                  disabled={loading}
                />
              }
              label="Keep me connected"
            />
            
            <Alert severity="info" sx={{ mt: 2 }}>
              <Typography variant="body2">
                This connection is used for screen capture only. We do not store your credentials or perform any trades on your behalf.
              </Typography>
            </Alert>
          </Box>
        </DialogContent>
        
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button 
            onClick={onClose} 
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={loading || !credentials.email || !credentials.password}
            startIcon={loading && <CircularProgress size={20} />}
          >
            {loading ? 'Connecting...' : 'Connect'}
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* OTP Verification Dialog */}
      <OtpVerification
        open={showOtpVerification}
        onClose={handleOtpClose}
        onVerify={handleOtpVerify}
        email={credentials.email}
      />
    </>
  );
};

export default QuotexLogin; 