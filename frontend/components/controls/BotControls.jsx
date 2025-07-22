import React from 'react';
import {
  Paper,
  Typography,
  Button,
  Grid,
  Switch,
  FormControlLabel,
  CircularProgress,
  Tooltip,
  Badge,
  Box,
  Alert
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import PowerSettingsNewIcon from '@mui/icons-material/PowerSettingsNew';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';

/**
 * BotControls Component
 * Provides interface for controlling the trading bot
 * Authentication is handled by TradingView component
 */
const BotControls = ({ isRunning, loading, onToggle }) => {
  return (
    <Paper sx={{ p: 2 }} className="bot-controls">
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12} sm={6} md={4}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Badge 
              color={isRunning ? "success" : "error"}
              variant="dot"
              anchorOrigin={{
                vertical: 'top',
                horizontal: 'left',
              }}
              sx={{ mr: 2 }}
            >
              <PowerSettingsNewIcon />
            </Badge>
            <Typography variant="h6" component="h2">
              Bot Controls
            </Typography>
          </Box>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Tooltip title="Toggle data collection on/off">
            <FormControlLabel 
              control={
                <Switch 
                  checked={isRunning}
                  onChange={onToggle}
                  disabled={loading}
                  color="success"
                />
              }
              label={isRunning ? "Bot Active" : "Bot Inactive"}
            />
          </Tooltip>
        </Grid>
        
        <Grid item xs={12} sm={12} md={5} sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
          <Button
            variant="contained"
            color={isRunning ? "error" : "success"}
            startIcon={isRunning ? <StopIcon /> : <PlayArrowIcon />}
            onClick={onToggle}
            disabled={loading}
            size="large"
          >
            {loading ? (
              <CircularProgress size={24} color="inherit" />
            ) : (
              isRunning ? "Stop Bot" : "Start Bot"
            )}
          </Button>
          
          <Button
            variant="outlined"
            color="primary"
            startIcon={<AssessmentIcon />}
            disabled={loading}
          >
            View Statistics
          </Button>
        </Grid>
        
        {/* Status information */}
        <Grid item xs={12}>
          <Alert 
            severity={isRunning ? "success" : "info"} 
            icon={<TrendingUpIcon />}
          >
            {isRunning 
              ? "Bot is actively collecting data and making predictions from the connected Quotex platform." 
              : "Click 'Start Bot' to begin. The trading view will guide you through connecting to Quotex if needed."}
          </Alert>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default BotControls; 