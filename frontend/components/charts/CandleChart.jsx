import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Bar,
  ReferenceLine,
  Line,
  Scatter
} from 'recharts';
import { Box, Typography, CircularProgress } from '@mui/material';
import { format } from 'date-fns';
import LockIcon from '@mui/icons-material/Lock';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';

/**
 * CandleChart Component
 * Displays historical candle data in a chart - only active when authenticated
 */
const CandleChart = ({ data, loading = false, isActive = false }) => {
  console.log('CandleChart rendered', { 
    dataLength: data?.length || 0, 
    loading, 
    isActive 
  });

  // Format data for the chart
  const chartData = useMemo(() => {
    if (!isActive || !data || !data.length) return [];
    
    return data.map((candle) => {
      // Format timestamp
      const timestamp = new Date(candle.timestamp);
      const formattedTime = format(timestamp, 'HH:mm:ss');
      
      return {
        timestamp: formattedTime,
        open: candle.open,
        close: candle.close,
        high: candle.high,
        low: candle.low,
        direction: candle.direction,
        // Calculate height for candlestick body
        height: Math.abs(candle.close - candle.open),
        // Use open as y value for proper positioning
        y: Math.min(candle.open, candle.close),
        // Color based on direction
        color: candle.direction === 'up' ? '#4caf50' : '#f44336',
        // For scatter plot to show actual price
        price: candle.close
      };
    });
  }, [data, isActive]);
  
  // Calculate price range for Y axis
  const priceRange = useMemo(() => {
    if (!isActive || !data || !data.length) return { min: 0, max: 1 };
    
    let min = Math.min(...data.map(c => c.low));
    let max = Math.max(...data.map(c => c.high));
    
    // Add a small padding
    const padding = (max - min) * 0.1;
    return {
      min: min - padding,
      max: max + padding
    };
  }, [data, isActive]);
  
  // Custom tooltip
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <Box
          sx={{
            bgcolor: 'background.paper',
            p: 1,
            border: '1px solid #ccc',
            borderRadius: 1,
            boxShadow: 1
          }}
        >
          <Typography variant="subtitle2">
            {data.timestamp}
          </Typography>
          <Typography variant="body2">
            O: {data.open.toFixed(5)}
          </Typography>
          <Typography variant="body2">
            H: {data.high.toFixed(5)}
          </Typography>
          <Typography variant="body2">
            L: {data.low.toFixed(5)}
          </Typography>
          <Typography variant="body2">
            C: {data.close.toFixed(5)}
          </Typography>
          <Typography 
            variant="body2" 
            sx={{ color: data.direction === 'up' ? '#4caf50' : '#f44336' }}
          >
            Direction: {data.direction.toUpperCase()}
          </Typography>
        </Box>
      );
    }
    return null;
  };

  // Show inactive state when not authenticated
  if (!isActive) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          flexDirection: 'column',
          justifyContent: 'center', 
          alignItems: 'center', 
          height: '100%',
          bgcolor: 'grey.50',
          borderRadius: 1,
          border: '1px dashed',
          borderColor: 'grey.300',
          p: 3
        }}
      >
        <LockIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
        <Typography variant="h6" color="text.secondary" gutterBottom>
          Live Chart Locked
        </Typography>
        <Typography variant="body2" color="text.secondary" textAlign="center">
          Connect to your Quotex account and start the bot<br/>
          to see real-time candle data
        </Typography>
        <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <TrendingUpIcon sx={{ fontSize: 16, color: 'text.disabled' }} />
          <Typography variant="caption" color="text.secondary">
            Waiting for authentication...
          </Typography>
        </Box>
      </Box>
    );
  }
  
  // Show loading state
  if (loading) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          flexDirection: 'column',
          justifyContent: 'center', 
          alignItems: 'center', 
          height: '100%' 
        }}
      >
        <CircularProgress size={40} sx={{ mb: 2 }} />
        <Typography variant="body2" color="text.secondary">
          Loading live candle data...
        </Typography>
      </Box>
    );
  }
  
  // Show no data state
  if (!chartData.length) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          flexDirection: 'column',
          justifyContent: 'center', 
          alignItems: 'center', 
          height: '100%' 
        }}
      >
        <Typography variant="body1" color="text.secondary" gutterBottom>
          No candle data available
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Waiting for data from Quotex...
        </Typography>
      </Box>
    );
  }
  
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 30 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" />
        <YAxis 
          domain={[priceRange.min, priceRange.max]} 
          tickFormatter={(value) => value.toFixed(5)}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        
        {/* Candle wicks (high-low range) */}
        <Bar
          dataKey="low"
          fill="transparent"
          stroke="#000"
          name="Price Range"
          barSize={2}
          yAxisId={0}
        >
          {chartData.map((entry, index) => (
            <ReferenceLine
              key={`wick-${index}`}
              y={entry.high}
              stroke={entry.color}
              strokeWidth={2}
              segment={[
                { x: index + 0.5, y: entry.low },
                { x: index + 0.5, y: entry.high }
              ]}
            />
          ))}
        </Bar>
        
        {/* Candle bodies */}
        <Bar
          dataKey="height"
          fill="#8884d8"
          stroke="#000"
          name="Candle Body"
          barSize={10}
          minPointSize={3}
        >
          {chartData.map((entry, index) => (
            <Bar
              key={`body-${index}`}
              y={entry.y}
              fill={entry.color}
              stroke={entry.color}
            />
          ))}
        </Bar>
        
        {/* Line showing price trend */}
        <Line
          type="monotone"
          dataKey="price"
          stroke="#8884d8"
          dot={{ fill: '#8884d8' }}
          activeDot={{ r: 8 }}
          name="Price"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
};

export default CandleChart; 