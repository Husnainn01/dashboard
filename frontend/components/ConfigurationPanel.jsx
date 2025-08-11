import { useState } from 'react';
import MLControlPanel from './MLControlPanel';

const ConfigurationPanel = ({
  tradingPairs,
  timezoneOptions,
  selectedPair,
  selectedTimezone,
  onPairChange,
  onTimezoneChange,
  predictionActive,
  onTogglePrediction,
  backendConnected,
  onSystemStatusChange
}) => {
  const [advanced, setAdvanced] = useState(false);
  const [showMLControls, setShowMLControls] = useState(false);
  
  return (
    <div className="config-panel-container">
      <h2>Configuration</h2>
      
      {/* Trading Pair Selection */}
      <div className="config-section">
        <label className="config-label">Trading Pair</label>
        <select 
          className="select"
          value={selectedPair}
          onChange={(e) => onPairChange(e.target.value)}
          disabled={predictionActive}
        >
          {tradingPairs.map((pair) => (
            <option key={pair.value} value={pair.value}>
              {pair.flag} {pair.label}
            </option>
          ))}
        </select>
        
        {/* USD/BRL(OTC) Info */}
        <div className="pair-info">
          <div className="pair-info-item">
            <span className="pair-flag">🇺🇸🇧🇷</span>
            <span className="pair-name">USD/BRL OTC</span>
            <span className="pair-description">Brazilian Real vs US Dollar</span>
          </div>
        </div>
      </div>
      
      {/* Timezone Selection */}
      <div className="config-section">
        <label className="config-label">Timezone</label>
        <select 
          className="select"
          value={selectedTimezone}
          onChange={(e) => onTimezoneChange(e.target.value)}
        >
          {timezoneOptions.map((tz) => (
            <option key={tz.value} value={tz.value}>
              {tz.label}
            </option>
          ))}
        </select>
      </div>
      
      {/* Prediction Control */}
      <div className="config-section">
        <label className="config-label">Prediction Service</label>
        <button 
          className={`btn ${predictionActive ? 'btn-danger' : 'btn-primary'}`}
          onClick={onTogglePrediction}
          disabled={!backendConnected}
          style={{ width: '100%' }}
        >
          {predictionActive ? '⏹️ Stop Predictions' : '▶️ Start Predictions'}
        </button>
        
        {!backendConnected && (
          <div className="backend-warning">
            ⚠️ Backend connection required
          </div>
        )}
      </div>
      
      {/* ML Controls Toggle */}
      <div className="config-section">
        <button 
          className="btn btn-secondary"
          onClick={() => setShowMLControls(!showMLControls)}
          style={{ width: '100%' }}
        >
          {showMLControls ? '▲ Hide ML Controls' : '▼ Show ML Controls'}
        </button>
      </div>
      
      {/* ML Controls Panel */}
      {showMLControls && (
        <MLControlPanel 
          selectedPair={selectedPair}
          onStatusChange={onSystemStatusChange}
        />
      )}
      
      {/* Advanced Settings */}
      <div className="config-section">
        <button 
          className="btn btn-secondary"
          onClick={() => setAdvanced(!advanced)}
          style={{ width: '100%' }}
        >
          {advanced ? '▲ Hide Advanced' : '▼ Show Advanced'}
        </button>
        
        {advanced && (
          <div className="advanced-settings">
            <div className="config-row">
              <label>Debug Mode</label>
              <label className="toggle">
                <input type="checkbox" />
                <span className="toggle-slider"></span>
              </label>
            </div>
            
            <div className="config-row">
              <label>Data Retention</label>
              <select className="select">
                <option value="1">1 day</option>
                <option value="7">7 days</option>
                <option value="30">30 days</option>
                <option value="90">90 days</option>
              </select>
            </div>
            
            <div className="config-row">
              <label>WebSocket Reconnect</label>
              <select className="select">
                <option value="3">3 seconds</option>
                <option value="5">5 seconds</option>
                <option value="10">10 seconds</option>
              </select>
            </div>
          </div>
        )}
      </div>
      
      {/* Status and Info */}
      <div className="config-section status-section">
        <div className="status-row">
          <span>Backend Status:</span>
          <span className={`status-indicator ${backendConnected ? 'connected' : 'disconnected'}`}>
            {backendConnected ? '🟢 Connected' : '🔴 Disconnected'}
          </span>
        </div>
        
        <div className="status-row">
          <span>Prediction Service:</span>
          <span className={`status-indicator ${predictionActive ? 'active' : 'inactive'}`}>
            {predictionActive ? '🟢 Active' : '⚫ Inactive'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ConfigurationPanel;
