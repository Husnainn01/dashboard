import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  TextField,
  CircularProgress,
  Alert,
  Divider
} from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';

/**
 * OTP Verification Component
 * Handles OTP (One-Time Password) verification for Quotex login
 */
const OtpVerification = ({ open, onClose, onVerify, email }) => {
  console.log('OtpVerification rendered', { open, email });
  
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [timeLeft, setTimeLeft] = useState(300); // 5 minutes countdown
  
  const otpInputRef = useRef(null);
  
  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      console.log('OTP verification dialog opened');
      setOtp('');
      setError(null);
      setTimeLeft(300);
      setLoading(false); // Ensure loading is reset when dialog opens
    }
  }, [open]);
  
  // Focus OTP input when dialog opens
  useEffect(() => {
    if (open && otpInputRef.current) {
      console.log('Focusing OTP input field');
      setTimeout(() => {
        otpInputRef.current.focus();
      }, 100);
    }
  }, [open]);
  
  // Countdown timer
  useEffect(() => {
    if (!open) return;
    
    console.log('Starting countdown timer');
    const interval = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          console.log('OTP code expired');
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => {
      console.log('Clearing countdown timer');
      clearInterval(interval);
    };
  }, [open]);
  
  // Format time remaining
  const formatTimeRemaining = () => {
    const minutes = Math.floor(timeLeft / 60);
    const seconds = timeLeft % 60;
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
  };
  
  // Handle input change
  const handleOtpChange = (e) => {
    // Only allow numbers
    const value = e.target.value.replace(/[^0-9]/g, '');
    console.log(`OTP input changed: ${value}`);
    setOtp(value);
  };
  
  // Handle form submission
  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    
    console.log('OTP verification form submitted');
    console.log('OTP code:', otp);
    
    if (!otp) {
      console.log('Empty OTP code, showing error');
      setError('Please enter the verification code');
      return;
    }
    
    setError(null);
    setLoading(true);
    
    try {
      console.log('Calling onVerify with OTP code');
      // Call the onVerify callback with the OTP
      const result = await onVerify(otp);
      console.log('OTP verification successful', result);
      
      // Don't need to call onClose here as it's handled by the parent component
      // Successful verification is handled by parent onVerify callback
    } catch (err) {
      console.error('OTP verification error:', err);
      setError(err.message || 'Verification failed');
      setLoading(false);
    }
  };
  
  return (
    <Dialog
      open={open}
      onClose={loading ? undefined : onClose}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center' }}>
        <VerifiedUserIcon sx={{ mr: 1 }} />
        Two-Factor Authentication Required
      </DialogTitle>
      
      <Divider />
      
      <DialogContent>
        <Box component="form" onSubmit={handleSubmit} noValidate sx={{ mt: 1 }}>
          <Typography variant="body2" color="text.secondary" paragraph>
            Quotex has sent a verification code to {email ? <strong>{email}</strong> : 'your email or phone'}.
            Please enter the code below to complete the login process.
          </Typography>
          
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          <TextField
            inputRef={otpInputRef}
            margin="normal"
            required
            fullWidth
            id="otp"
            label="Verification Code"
            name="otp"
            autoComplete="one-time-code"
            value={otp}
            onChange={handleOtpChange}
            disabled={loading}
            inputProps={{ 
              maxLength: 8,
              pattern: '[0-9]*',
              inputMode: 'numeric' 
            }}
            placeholder="Enter code"
            autoFocus
          />
          
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, textAlign: 'center' }}>
            Code expires in: <strong>{formatTimeRemaining()}</strong>
          </Typography>
          
          {timeLeft === 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              The verification code has expired. Please restart the login process to receive a new code.
            </Alert>
          )}
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
          disabled={loading || !otp || timeLeft === 0}
          startIcon={loading ? <CircularProgress size={20} /> : null}
        >
          {loading ? 'Verifying...' : 'Verify'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default OtpVerification; 