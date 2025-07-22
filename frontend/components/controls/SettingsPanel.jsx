import React, { useState } from 'react';
import {
  Paper,
  Typography,
  Box,
  IconButton,
  Divider,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  FormControlLabel,
  Switch,
  Slider,
  Grid
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SaveIcon from '@mui/icons-material/Save';

/**
 * SettingsPanel Component
 * Allows configuration of application settings
 */
const SettingsPanel = ({ onClose }) => {
  // Default settings
  const [settings, setSettings] = useState({
    tradingPair: 'EUR/USD OTC',
    screenshotInterval: 1000,
    candleTimeframe: 60,
    patternLength: 5,
    headlessBrowser: true,
    saveScreenshots: true,
    modelConfidenceThreshold: 60
  });
  
  // Handle settings change
  const handleChange = (e) => {
    const { name, value, checked, type } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };
  
  // Handle slider change
  const handleSliderChange = (name) => (e, value) => {
    setSettings(prev => ({
      ...prev,
      [name]: value
    }));
  };
  
  // Handle form submit
  const handleSubmit = (e) => {
    e.preventDefault();
    
    // In a real application, this would save settings to API/localStorage
    console.log('Saving settings:', settings);
    
    // Close the panel
    onClose();
  };
  
  return (
    <Paper sx={{ p: 2, mb: 2 }} component="form" onSubmit={handleSubmit} className="settings-panel">
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Settings</Typography>
        <Box>
          <IconButton type="submit" title="Save Settings" color="primary">
            <SaveIcon />
          </IconButton>
          <IconButton onClick={onClose} title="Close">
            <CloseIcon />
          </IconButton>
        </Box>
      </Box>
      
      <Divider sx={{ mb: 3 }} />
      
      <Grid container spacing={3}>
        {/* Trading Settings */}
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1" gutterBottom>
            Trading Settings
          </Typography>
          
          <FormControl fullWidth margin="normal">
            <InputLabel id="trading-pair-label">Trading Pair</InputLabel>
            <Select
              labelId="trading-pair-label"
              name="tradingPair"
              value={settings.tradingPair}
              onChange={handleChange}
              label="Trading Pair"
            >
              <MenuItem value="EUR/USD OTC">EUR/USD OTC</MenuItem>
              <MenuItem value="GBP/USD OTC">GBP/USD OTC</MenuItem>
              <MenuItem value="EUR/JPY OTC">EUR/JPY OTC</MenuItem>
              <MenuItem value="AUD/USD OTC">AUD/USD OTC</MenuItem>
            </Select>
          </FormControl>
          
          <FormControl fullWidth margin="normal">
            <InputLabel id="candle-timeframe-label">Candle Timeframe</InputLabel>
            <Select
              labelId="candle-timeframe-label"
              name="candleTimeframe"
              value={settings.candleTimeframe}
              onChange={handleChange}
              label="Candle Timeframe"
            >
              <MenuItem value={30}>30 seconds</MenuItem>
              <MenuItem value={60}>1 minute</MenuItem>
              <MenuItem value={300}>5 minutes</MenuItem>
              <MenuItem value={900}>15 minutes</MenuItem>
            </Select>
          </FormControl>
        </Grid>
        
        {/* Browser Settings */}
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1" gutterBottom>
            Browser Settings
          </Typography>
          
          <FormControlLabel
            control={
              <Switch
                checked={settings.headlessBrowser}
                onChange={handleChange}
                name="headlessBrowser"
                color="primary"
              />
            }
            label="Use headless browser"
            sx={{ display: 'block', mb: 2 }}
          />
          
          <FormControlLabel
            control={
              <Switch
                checked={settings.saveScreenshots}
                onChange={handleChange}
                name="saveScreenshots"
                color="primary"
              />
            }
            label="Save screenshots"
            sx={{ display: 'block', mb: 2 }}
          />
          
          <Box sx={{ mb: 2 }}>
            <Typography id="screenshot-interval-label" gutterBottom>
              Screenshot Interval (ms): {settings.screenshotInterval}
            </Typography>
            <Slider
              aria-labelledby="screenshot-interval-label"
              value={settings.screenshotInterval}
              onChange={handleSliderChange('screenshotInterval')}
              min={500}
              max={5000}
              step={100}
              valueLabelDisplay="auto"
              marks={[
                { value: 500, label: '0.5s' },
                { value: 1000, label: '1s' },
                { value: 5000, label: '5s' },
              ]}
            />
          </Box>
        </Grid>
        
        {/* Model Settings */}
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Model Settings
          </Typography>
          
          <Box sx={{ mb: 2 }}>
            <Typography id="pattern-length-label" gutterBottom>
              Pattern Length: {settings.patternLength}
            </Typography>
            <Slider
              aria-labelledby="pattern-length-label"
              value={settings.patternLength}
              onChange={handleSliderChange('patternLength')}
              min={3}
              max={15}
              step={1}
              valueLabelDisplay="auto"
              marks={[
                { value: 3, label: '3' },
                { value: 5, label: '5' },
                { value: 10, label: '10' },
                { value: 15, label: '15' },
              ]}
            />
          </Box>
          
          <Box sx={{ mb: 2 }}>
            <Typography id="confidence-threshold-label" gutterBottom>
              Minimum Confidence Threshold: {settings.modelConfidenceThreshold}%
            </Typography>
            <Slider
              aria-labelledby="confidence-threshold-label"
              value={settings.modelConfidenceThreshold}
              onChange={handleSliderChange('modelConfidenceThreshold')}
              min={50}
              max={95}
              step={5}
              valueLabelDisplay="auto"
              marks={[
                { value: 50, label: '50%' },
                { value: 75, label: '75%' },
                { value: 95, label: '95%' },
              ]}
            />
          </Box>
        </Grid>
      </Grid>
      
      <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
        <Button variant="outlined" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="contained" type="submit" startIcon={<SaveIcon />}>
          Save Settings
        </Button>
      </Box>
    </Paper>
  );
};

export default SettingsPanel; 