import React from 'react';
import {
  Paper,
  Typography,
  Box,
  CircularProgress,
  Divider,
  Skeleton,
  Grid
} from '@mui/material';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import QuestionMarkIcon from '@mui/icons-material/QuestionMark';
import PredictionCandleChart from './PredictionCandleChart';

/**
 * PredictionCard Component
 * Displays the next candle prediction with confidence level and visual chart
 */
const PredictionCard = ({ 
  prediction, 
  recentCandles = [], 
  isActive = false,
  loading = false 
}) => {
  console.log('PredictionCard rendered', { 
    prediction, 
    candleCount: recentCandles.length, 
    isActive,
    loading
  });

  const { direction, confidence, patternId } = prediction || {};
  
  // Determine confidence class for styling
  const getConfidenceClass = () => {
    if (!confidence) return '';
    if (confidence >= 70) return 'high-confidence';
    if (confidence >= 60) return 'medium-confidence';
    return 'low-confidence';
  };
  
  // Determine confidence color
  const getConfidenceColor = () => {
    if (!confidence) return 'primary';
    if (confidence >= 70) return 'success';
    if (confidence >= 60) return 'info';
    return 'warning';
  };
  
  return (
    <Paper
      sx={{
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        height: 'auto',
        minHeight: 500,
      }}
      className={`prediction-card ${getConfidenceClass()}`}
    >
      <Typography variant="h6" component="h2" gutterBottom>
        Next Candle Prediction
      </Typography>
      <Divider sx={{ mb: 2 }} />
      
      {/* Visual Prediction Chart */}
      <Box sx={{ mb: 2 }}>
        <PredictionCandleChart 
          recentCandles={recentCandles}
          prediction={prediction}
          isActive={isActive && !loading}
        />
      </Box>
      
      <Divider sx={{ mb: 2 }} />
      
      {/* Traditional Prediction Display */}
      <Grid container spacing={2}>
        {/* Direction and Confidence */}
        <Grid item xs={6}>
          <Box sx={{ 
            display: 'flex', 
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 120
          }}>
            {loading ? (
              <Box sx={{ textAlign: 'center' }}>
                <CircularProgress size={40} />
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Analyzing...
                </Typography>
              </Box>
            ) : (
              <>
                {direction ? (
                  <>
                    {direction === 'up' ? (
                      <ArrowUpwardIcon 
                        sx={{ fontSize: 48, color: 'success.main', mb: 1 }}
                        className="up-direction"
                      />
                    ) : (
                      <ArrowDownwardIcon 
                        sx={{ fontSize: 48, color: 'error.main', mb: 1 }}
                        className="down-direction"
                      />
                    )}
                    
                    <Typography 
                      variant="h6" 
                      sx={{ 
                        fontWeight: 'bold',
                        color: direction === 'up' ? 'success.main' : 'error.main'
                      }}
                      className={direction === 'up' ? 'up-direction' : 'down-direction'}
                    >
                      {direction.toUpperCase()}
                    </Typography>
                  </>
                ) : (
                  <>
                    <QuestionMarkIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography variant="h6" sx={{ color: 'text.disabled' }}>
                      NO DATA
                    </Typography>
                  </>
                )}
              </>
            )}
          </Box>
        </Grid>
        
        {/* Confidence Circle */}
        <Grid item xs={6}>
          <Box sx={{ 
            display: 'flex', 
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 120
          }}>
            {confidence ? (
              <>
                <Box sx={{ position: 'relative', display: 'inline-flex', mb: 1 }}>
                  <CircularProgress 
                    variant="determinate" 
                    value={confidence} 
                    color={getConfidenceColor()}
                    size={60}
                    thickness={6}
                  />
                  <Box
                    sx={{
                      top: 0,
                      left: 0,
                      bottom: 0,
                      right: 0,
                      position: 'absolute',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Typography variant="h6" component="div" fontWeight="bold">
                      {`${confidence}%`}
                    </Typography>
                  </Box>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Confidence
                </Typography>
              </>
            ) : (
              <>
                <Skeleton variant="circular" width={60} height={60} sx={{ mb: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  No prediction
                </Typography>
              </>
            )}
          </Box>
        </Grid>
      </Grid>
      
      {/* Additional Info */}
      <Box sx={{ mt: 2 }}>
        {patternId && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Pattern ID: <strong>{patternId}</strong>
          </Typography>
        )}
        
        {isActive && prediction && (
          <Typography variant="body2" color="primary" sx={{ fontStyle: 'italic' }}>
            📊 Live prediction based on {recentCandles.length > 0 ? recentCandles.length : 0} recent candles
          </Typography>
        )}
        
        {!isActive && (
          <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
            🔒 Connect to Quotex and start the bot to see live predictions
          </Typography>
        )}
      </Box>
    </Paper>
  );
};

export default PredictionCard; 