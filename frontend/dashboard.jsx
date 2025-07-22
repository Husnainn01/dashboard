import React, { useState, useEffect } from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Button,
  Box,
  CircularProgress,
  Divider,
  AppBar,
  Toolbar,
  IconButton,
  Switch,
  FormControlLabel
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import SettingsIcon from '@mui/icons-material/Settings';
import HistoryIcon from '@mui/icons-material/History';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

/**
 * Main Dashboard Component
 * This is the primary interface for the OTC Binary Trading Prediction Tool
 */
const Dashboard = () => {
  // State variables
  const [isRunning, setIsRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [candleData, setCandleData] = useState([]);
  const [prediction, setPrediction] = useState({
    direction: null,
    confidence: 0,
    patternId: null
  });
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(null);

  // Mock data for initial development
  useEffect(() => {
    // This would be replaced with actual API calls
    const mockData = Array(20).fill().map((_, index) => ({
      timestamp: new Date(Date.now() - (20 - index) * 60000).toISOString(),
      open: 1.2345 + Math.random() * 0.01,
      close: 1.2345 + Math.random() * 0.01,
      high: 1.2345 + Math.random() * 0.015,
      low: 1.2345 + Math.random() * 0.005,
      direction: Math.random() > 0.5 ? 'up' : 'down'
    }));

    setCandleData(mockData);

    // Mock prediction
    setPrediction({
      direction: Math.random() > 0.5 ? 'up' : 'down',
      confidence: Math.floor(Math.random() * 30) + 60,
      patternId: 'a1b2c3d4'
    });
  }, []);

  // Toggle bot running state
  const toggleBot = () => {
    setIsRunning(!isRunning);
    setLoading(true);
    
    // Simulate API call to start/stop bot
    setTimeout(() => {
      setLoading(false);
      // Would make actual API call here
    }, 1500);
  };

  // Format data for chart
  const chartData = candleData.map(candle => ({
    timestamp: new Date(candle.timestamp).toLocaleTimeString(),
    price: candle.close,
    direction: candle.direction,
    // Add color based on direction
    color: candle.direction === 'up' ? '#4caf50' : '#f44336'
  }));

  return (
    <div>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            OTC Binary Trading Predictor
          </Typography>
          <IconButton 
            color="inherit" 
            onClick={() => setShowHistory(!showHistory)}
          >
            <HistoryIcon />
          </IconButton>
          <IconButton 
            color="inherit"
            onClick={() => setShowSettings(!showSettings)}
          >
            <SettingsIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Grid container spacing={3}>
          {/* Trading View (would be iframe/embedded view) */}
          <Grid item xs={12} md={8}>
            <Paper
              sx={{
                p: 2,
                display: 'flex',
                flexDirection: 'column',
                height: 350,
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              <Typography variant="h6" component="h2">
                Live Trading View
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Box sx={{ 
                display: 'flex', 
                justifyContent: 'center', 
                alignItems: 'center',
                height: '100%',
                bgcolor: '#f5f5f5' 
              }}>
                <Typography variant="body2" color="text.secondary">
                  Quotex chart view would be embedded here
                  {/* This would be replaced with an iframe or browser view */}
                </Typography>
              </Box>
            </Paper>
          </Grid>

          {/* Prediction Display */}
          <Grid item xs={12} md={4}>
            <Paper
              sx={{
                p: 2,
                display: 'flex',
                flexDirection: 'column',
                height: 350,
              }}
            >
              <Typography variant="h6" component="h2">
                Next Candle Prediction
              </Typography>
              <Divider sx={{ my: 1 }} />
              
              <Box sx={{ 
                display: 'flex', 
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                flexGrow: 1
              }}>
                {prediction.direction === 'up' ? (
                  <ArrowUpwardIcon sx={{ fontSize: 80, color: 'green' }} />
                ) : (
                  <ArrowDownwardIcon sx={{ fontSize: 80, color: 'red' }} />
                )}
                
                <Typography variant="h4" sx={{ mt: 2 }}>
                  {prediction.direction === 'up' ? 'UP' : 'DOWN'}
                </Typography>
                
                <Box sx={{ position: 'relative', display: 'inline-flex', mt: 2 }}>
                  <CircularProgress 
                    variant="determinate" 
                    value={prediction.confidence} 
                    color={prediction.confidence > 70 ? "success" : prediction.confidence > 60 ? "info" : "warning"}
                    size={80}
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
                    <Typography variant="h5" component="div">
                      {`${prediction.confidence}%`}
                    </Typography>
                  </Box>
                </Box>
                
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Pattern ID: {prediction.patternId}
                </Typography>
                
                {timeRemaining && (
                  <Typography variant="body1" sx={{ mt: 1 }}>
                    Next candle in: {timeRemaining}s
                  </Typography>
                )}
              </Box>
            </Paper>
          </Grid>

          {/* Historical Chart */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" component="h2">
                Historical Data
              </Typography>
              <Divider sx={{ my: 1 }} />
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="timestamp" />
                  <YAxis domain={['auto', 'auto']} />
                  <Tooltip />
                  <Legend />
                  <Line 
                    type="monotone" 
                    dataKey="price" 
                    name="Price" 
                    stroke="#8884d8" 
                    dot={{ stroke: (entry) => entry.color, fill: (entry) => entry.color }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>

          {/* Controls */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} sm={6}>
                  <Typography variant="h6" component="h2">
                    Bot Controls
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6} sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <FormControlLabel 
                    control={
                      <Switch 
                        checked={isRunning}
                        onChange={toggleBot}
                        disabled={loading}
                      />
                    }
                    label={isRunning ? "Running" : "Stopped"}
                  />
                  <Button
                    variant="contained"
                    color={isRunning ? "error" : "primary"}
                    startIcon={isRunning ? <StopIcon /> : <PlayArrowIcon />}
                    onClick={toggleBot}
                    disabled={loading}
                    sx={{ ml: 2 }}
                  >
                    {loading ? (
                      <CircularProgress size={24} color="inherit" />
                    ) : (
                      isRunning ? "Stop Bot" : "Start Bot"
                    )}
                  </Button>
                </Grid>
              </Grid>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </div>
  );
};

export default Dashboard;
