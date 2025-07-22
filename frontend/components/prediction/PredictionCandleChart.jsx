import React, { useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';

/**
 * PredictionCandleChart Component
 * Shows a visual representation of recent candles + predicted next candle
 */
const PredictionCandleChart = ({ 
  recentCandles = [], 
  prediction = null, 
  isActive = false 
}) => {
  console.log('PredictionCandleChart rendered', { 
    candleCount: recentCandles.length, 
    prediction, 
    isActive 
  });

  // Prepare chart data with recent candles + prediction
  const chartData = useMemo(() => {
    if (!isActive || !prediction) {
      return recentCandles.slice(-5).map((candle, index) => ({
        name: `T-${5-index}`,
        open: candle.open,
        close: candle.close,
        high: candle.high,
        low: candle.low,
        direction: candle.direction,
        type: 'actual',
        timestamp: candle.timestamp
      }));
    }

    // Get last 4 actual candles
    const actualCandles = recentCandles.slice(-4).map((candle, index) => ({
      name: `T-${4-index}`,
      open: candle.open,
      close: candle.close,
      high: candle.high,
      low: candle.low,
      direction: candle.direction,
      type: 'actual',
      timestamp: candle.timestamp
    }));

    // Create predicted candle based on the last candle and prediction
    const lastCandle = recentCandles[recentCandles.length - 1];
    if (!lastCandle) return actualCandles;

    // Generate predicted candle values
    const basePrice = lastCandle.close;
    const volatility = Math.abs(lastCandle.high - lastCandle.low) * 0.8; // Use 80% of last candle's volatility
    
    let predictedCandle;
    if (prediction.direction === 'up') {
      // Bullish prediction
      const open = basePrice + (Math.random() - 0.5) * volatility * 0.3;
      const close = open + Math.random() * volatility * 0.8 + volatility * 0.2; // Ensure it closes higher
      const high = Math.max(open, close) + Math.random() * volatility * 0.3;
      const low = Math.min(open, close) - Math.random() * volatility * 0.2;
      
      predictedCandle = {
        name: 'NEXT',
        open,
        close,
        high,
        low,
        direction: 'up',
        type: 'predicted',
        confidence: prediction.confidence
      };
    } else {
      // Bearish prediction
      const open = basePrice + (Math.random() - 0.5) * volatility * 0.3;
      const close = open - Math.random() * volatility * 0.8 - volatility * 0.2; // Ensure it closes lower
      const high = Math.max(open, close) + Math.random() * volatility * 0.2;
      const low = Math.min(open, close) - Math.random() * volatility * 0.3;
      
      predictedCandle = {
        name: 'NEXT',
        open,
        close,
        high,
        low,
        direction: 'down',
        type: 'predicted',
        confidence: prediction.confidence
      };
    }

    return [...actualCandles, predictedCandle];
  }, [recentCandles, prediction, isActive]);

  // Custom candle renderer
  const CandleShape = (props) => {
    const { payload, x, width } = props;
    if (!payload) return null;

    const { open, close, high, low, type, direction, confidence } = payload;
    
    const candleWidth = Math.max(width * 0.6, 8);
    const wickWidth = 2;
    const centerX = x + width / 2;
    
    // Colors based on type and direction
    let fillColor, strokeColor, opacity;
    
    if (type === 'predicted') {
      // Predicted candle - use special styling
      fillColor = direction === 'up' ? '#4caf50' : '#f44336';
      strokeColor = direction === 'up' ? '#2e7d32' : '#c62828';
      opacity = Math.max(confidence / 100 * 0.8, 0.4); // Opacity based on confidence
    } else {
      // Actual candle
      fillColor = direction === 'up' ? '#26a69a' : '#ef5350';
      strokeColor = direction === 'up' ? '#00695c' : '#c62828';
      opacity = 1;
    }

    const bodyTop = Math.max(open, close);
    const bodyBottom = Math.min(open, close);
    const bodyHeight = Math.max(Math.abs(close - open), 1);

    return (
      <g opacity={opacity}>
        {/* High-Low Wick */}
        <line
          x1={centerX}
          y1={high}
          x2={centerX}
          y2={low}
          stroke={strokeColor}
          strokeWidth={wickWidth}
        />
        
        {/* Candle Body */}
        <rect
          x={centerX - candleWidth / 2}
          y={bodyTop}
          width={candleWidth}
          height={bodyHeight}
          fill={fillColor}
          stroke={strokeColor}
          strokeWidth={1}
        />
        
        {/* Special indicator for predicted candle */}
        {type === 'predicted' && (
          <>
            {/* Dashed border for prediction */}
            <rect
              x={centerX - candleWidth / 2 - 2}
              y={bodyTop - 2}
              width={candleWidth + 4}
              height={bodyHeight + 4}
              fill="none"
              stroke={strokeColor}
              strokeWidth={2}
              strokeDasharray="4,2"
              opacity={0.8}
            />
            
            {/* Confidence indicator */}
            <text
              x={centerX}
              y={low + 15}
              textAnchor="middle"
              fontSize="10"
              fill={strokeColor}
              fontWeight="bold"
            >
              {confidence}%
            </text>
          </>
        )}
      </g>
    );
  };

  if (!isActive) {
    return (
      <Box 
        sx={{ 
          height: '200px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          bgcolor: 'grey.50',
          borderRadius: 1,
          border: '1px dashed',
          borderColor: 'grey.300'
        }}
      >
        <Typography variant="body2" color="text.secondary" textAlign="center">
          Visual Prediction Chart<br/>
          <small>Available when bot is active and connected</small>
        </Typography>
      </Box>
    );
  }

  if (!chartData.length) {
    return (
      <Box 
        sx={{ 
          height: '200px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center' 
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Waiting for candle data...
        </Typography>
      </Box>
    );
  }

  // Calculate price range for Y-axis
  const allPrices = chartData.flatMap(d => [d.open, d.close, d.high, d.low]);
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const padding = (maxPrice - minPrice) * 0.1;

  return (
    <Box sx={{ height: '200px', width: '100%', position: 'relative' }}>
      {/* Chart Title */}
      <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center' }}>
        Recent + Predicted Candles
      </Typography>
      
      {/* Legend */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'center', 
        gap: 2, 
        mb: 1,
        fontSize: '12px'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Box sx={{ 
            width: 10, 
            height: 10, 
            bgcolor: '#26a69a',
            border: '1px solid #00695c'
          }} />
          <Typography variant="caption">Actual</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Box sx={{ 
            width: 10, 
            height: 10, 
            bgcolor: prediction?.direction === 'up' ? '#4caf50' : '#f44336',
            border: `1px dashed ${prediction?.direction === 'up' ? '#2e7d32' : '#c62828'}`,
            opacity: 0.7
          }} />
          <Typography variant="caption">Predicted</Typography>
        </Box>
      </Box>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={150}>
        <BarChart
          data={chartData}
          margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
        >
          <XAxis 
            dataKey="name" 
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11 }}
          />
          <YAxis 
            domain={[minPrice - padding, maxPrice + padding]}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10 }}
            tickFormatter={(value) => value.toFixed(4)}
          />
          
          {/* Vertical line to separate actual from predicted */}
          {prediction && (
            <ReferenceLine 
              x={chartData.length - 1.5} 
              stroke="#666" 
              strokeDasharray="2,2"
              opacity={0.5}
            />
          )}
          
          <Bar 
            dataKey="close" 
            shape={CandleShape}
          />
        </BarChart>
      </ResponsiveContainer>
      
      {/* Prediction Info */}
      {prediction && isActive && (
        <Box sx={{ 
          position: 'absolute', 
          top: 25, 
          right: 5, 
          bgcolor: 'rgba(255,255,255,0.9)',
          px: 1,
          py: 0.5,
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'grey.300'
        }}>
          <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
            Prediction: {prediction.direction?.toUpperCase()} ({prediction.confidence}%)
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default PredictionCandleChart; 