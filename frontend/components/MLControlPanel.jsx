import { useState, useEffect } from 'react';
import { 
  getModelsInfo, 
  retrainModel, 
  getSystemStatus,
  getTradingPairs,
  startPredictionService,
  stopPredictionService
} from '../services/api';

// Helper function to format uptime in a readable format
const formatUptime = (seconds) => {
  if (!seconds) return '0s';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  } else {
    return `${remainingSeconds}s`;
  }
};

// Ensure we parse backend timestamps as UTC.
// Some services return ISO strings without timezone (no trailing 'Z').
// This helper makes them UTC by default to prevent local-offset skew.
const parseUtc = (ts) => {
  if (!ts) return null;
  // If ts already has timezone info ('Z' or '+/-'), parse directly
  if (/(Z|[\+\-]\d{2}:?\d{2})$/.test(ts)) return new Date(ts);
  return new Date(ts + 'Z');
};

const MLControlPanel = ({ selectedPair, onStatusChange }) => {
  // State for ML models and training
  const [models, setModels] = useState({ local_models: [], cloud_models: [] });
  const [systemStatus, setSystemStatus] = useState({});
  const [isTraining, setIsTraining] = useState(false);
  const [trainingStatus, setTrainingStatus] = useState(null);
  const [selectedModelType, setSelectedModelType] = useState('xgboost');
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.7);
  const [updateInterval, setUpdateInterval] = useState(60);
  const [autoTrain, setAutoTrain] = useState(false);
  const [isServiceRunning, setIsServiceRunning] = useState(false);
  
  // Fetch models and system status on mount and when selectedPair changes
  useEffect(() => {
    fetchModelsInfo();
    fetchSystemStatus();
    
    // Set up interval to refresh status
    const intervalId = setInterval(() => {
      fetchSystemStatus();
    }, 30000); // Every 30 seconds
    
    return () => clearInterval(intervalId);
  }, [selectedPair]);
  
  // Fetch models info
  const fetchModelsInfo = async () => {
    try {
      const data = await getModelsInfo();
      setModels(data);
      
      // Check if we have a model for the selected pair
      const pairModels = [...data.local_models, ...data.cloud_models].filter(
        model => model.trading_pair === selectedPair
      );
      
      if (pairModels.length > 0) {
        console.log(`📊 Found ${pairModels.length} models for ${selectedPair}`);
      } else {
        console.log(`⚠️ No models found for ${selectedPair}`);
      }
    } catch (error) {
      console.error('Failed to fetch models info:', error);
    }
  };
  
  // Fetch system status
  const fetchSystemStatus = async () => {
    try {
      const data = await getSystemStatus();
      setSystemStatus(data);
      
      // Update service running status
      setIsServiceRunning(data.prediction?.status === 'running');
      
      // Notify parent component of status change
      if (onStatusChange) {
        onStatusChange(data);
      }
    } catch (error) {
      console.error('Failed to fetch system status:', error);
    }
  };
  
  // Start training a new model
  const handleStartTraining = async () => {
    setIsTraining(true);
    setTrainingStatus('Starting training...');
    
    try {
      const response = await retrainModel(selectedPair, selectedModelType);
      setTrainingStatus(`Training job submitted: ${response.job_id}`);
      
      // Poll for training status
      const checkTrainingStatus = async () => {
        try {
          await fetchModelsInfo();
          await fetchSystemStatus();
          
          // Check if training is still in progress
          const isStillTraining = systemStatus.ml_training?.active_jobs > 0;
          
          if (isStillTraining) {
            // Check again in 5 seconds
            setTimeout(checkTrainingStatus, 5000);
          } else {
            setIsTraining(false);
            setTrainingStatus('Training completed');
            
            // Clear status after a delay
            setTimeout(() => setTrainingStatus(null), 5000);
          }
        } catch (error) {
          console.error('Error checking training status:', error);
        }
      };
      
      // Start polling
      setTimeout(checkTrainingStatus, 5000);
    } catch (error) {
      console.error('Failed to start training:', error);
      setIsTraining(false);
      setTrainingStatus(`Training failed: ${error.message}`);
      
      // Clear error after a delay
      setTimeout(() => setTrainingStatus(null), 5000);
    }
  };
  
  // Toggle prediction service
  const handleToggleService = async () => {
    try {
      if (isServiceRunning) {
        await stopPredictionService();
      } else {
        await startPredictionService();
      }
      
      // Update status
      await fetchSystemStatus();
    } catch (error) {
      console.error('Failed to toggle prediction service:', error);
    }
  };
  
  // Get model status for the selected pair
  const getModelStatus = () => {
    const pairModels = [...models.local_models, ...models.cloud_models].filter(
      model => model.trading_pair === selectedPair
    );
    
    if (pairModels.length === 0) {
      return (
        <div className="model-status not-trained">
          <span>⚠️ No models trained</span>
        </div>
      );
    }
    
    // Find the most recent model (compare in UTC)
    const latestModel = pairModels.reduce((latest, model) => {
      const curr = parseUtc(model.created_at);
      const prev = latest ? parseUtc(latest.created_at) : null;
      if (!latest || (curr && prev && curr > prev) || (curr && !prev)) {
        return model;
      }
      return latest;
    }, null);
    
    if (!latestModel) return null;
    
    // Calculate age in hours (use UTC now and UTC created_at)
    const nowUtc = new Date(new Date().toISOString());
    const createdUtc = parseUtc(latestModel.created_at);
    const ageHours = createdUtc ? (nowUtc - createdUtc) / (1000 * 60 * 60) : 0;
    const ageText = ageHours < 1 
      ? 'Less than 1 hour ago'
      : ageHours < 24
        ? `${Math.round(ageHours)} hours ago`
        : `${Math.round(ageHours / 24)} days ago`;
    
    return (
      <div className="model-status trained">
        <span>✅ Model trained {ageText}</span>
        <span className="model-details">
          {latestModel.algorithm} | Accuracy: {(latestModel.accuracy * 100).toFixed(1)}%
        </span>
      </div>
    );
  };
  
  return (
    <div className="ml-control-panel">
      <h3>ML Training Controls</h3>
      
      {/* Model Status */}
      <div className="panel-section">
        <h4>Model Status</h4>
        {getModelStatus()}
      </div>
      
      {/* Training Controls */}
      <div className="panel-section">
        <h4>Training</h4>
        
        <div className="control-row">
          <label>Model Type:</label>
          <select 
            value={selectedModelType}
            onChange={(e) => setSelectedModelType(e.target.value)}
            disabled={isTraining}
          >
            <option value="xgboost">XGBoost</option>
            <option value="random_forest">Random Forest</option>
            <option value="lightgbm">LightGBM</option>
          </select>
        </div>
        
        <div className="control-row">
          <label>Auto-Train:</label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={autoTrain}
              onChange={() => setAutoTrain(!autoTrain)}
              disabled={isTraining}
            />
            <span className="toggle-slider"></span>
          </label>
          <span className="toggle-label">{autoTrain ? 'On' : 'Off'}</span>
        </div>
        
        <button 
          className="btn btn-primary"
          onClick={handleStartTraining}
          disabled={isTraining}
        >
          {isTraining ? 'Training...' : 'Train New Model'}
        </button>
        
        {trainingStatus && (
          <div className="training-status">
            {trainingStatus}
          </div>
        )}
      </div>
      
      {/* Prediction Controls */}
      <div className="panel-section">
        <h4>Prediction Settings</h4>
        
        <div className="control-row">
          <label>Confidence Threshold:</label>
          <select 
            value={confidenceThreshold}
            onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
          >
            <option value="0.6">60%</option>
            <option value="0.7">70%</option>
            <option value="0.8">80%</option>
            <option value="0.9">90%</option>
          </select>
        </div>
        
        <div className="control-row">
          <label>Update Interval:</label>
          <select 
            value={updateInterval}
            onChange={(e) => setUpdateInterval(parseInt(e.target.value))}
          >
            <option value="30">30 seconds</option>
            <option value="60">1 minute</option>
            <option value="300">5 minutes</option>
          </select>
        </div>
        
        <button 
          className={`btn ${isServiceRunning ? 'btn-danger' : 'btn-success'}`}
          onClick={handleToggleService}
        >
          {isServiceRunning ? 'Stop Prediction Service' : 'Start Prediction Service'}
        </button>
      </div>
      
      {/* System Status */}
      <div className="panel-section">
        <h4>System Status</h4>
        
        <div className="status-grid">
          {/* Data Collection Status */}
          <div className="status-item">
            <span className="status-label">Data Collection:</span>
            <span className={`status-value ${systemStatus.data_collection?.status === 'running' ? 'running' : 'stopped'}`}>
              {systemStatus.data_collection?.status === 'running' ? 'Running' : 'Stopped'}
            </span>
            {systemStatus.data_collection?.stats && (
              <div className="status-details">
                <span>Total: {systemStatus.data_collection.stats.total_collections || 0} candles</span>
                <span>Success: {Math.round((systemStatus.data_collection.stats.successful_collections / Math.max(1, systemStatus.data_collection.stats.total_collections)) * 100)}%</span>
              </div>
            )}
          </div>
          
          {/* ML Training Status */}
          <div className="status-item">
            <span className="status-label">ML Training:</span>
            <span className={`status-value ${systemStatus.ml_training?.status === 'running' ? 'running' : 'stopped'}`}>
              {systemStatus.ml_training?.status === 'running' ? 'Running' : 'Stopped'}
            </span>
            {systemStatus.ml_training && (
              <div className="status-details">
                <span>Queue: {systemStatus.ml_training.queue_size || 0} jobs</span>
                <span>Active: {systemStatus.ml_training.active_jobs || 0} jobs</span>
                <span>Auto-train: {systemStatus.ml_training.auto_training?.enabled ? 'On' : 'Off'}</span>
              </div>
            )}
          </div>
          
          {/* Prediction Status */}
          <div className="status-item">
            <span className="status-label">Prediction:</span>
            <span className={`status-value ${systemStatus.prediction?.status === 'running' ? 'running' : 'stopped'}`}>
              {systemStatus.prediction?.status === 'running' ? 'Running' : 'Stopped'}
            </span>
            {systemStatus.prediction && (
              <div className="status-details">
                <span>Made: {systemStatus.prediction.predictions_made || 0}</span>
                <span>Uptime: {formatUptime(systemStatus.prediction.uptime_seconds)}</span>
              </div>
            )}
          </div>
          
          {/* Models Status */}
          <div className="status-item">
            <span className="status-label">Models:</span>
            <span className="status-value">
              {(systemStatus.ml_training?.models_count?.local || 0) + (systemStatus.ml_training?.models_count?.cloud || 0)} total
            </span>
            {systemStatus.ml_training?.models_count && (
              <div className="status-details">
                <span>Local: {systemStatus.ml_training.models_count.local || 0}</span>
                <span>Cloud: {systemStatus.ml_training.models_count.cloud || 0}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MLControlPanel;
