import { useState, useEffect, useRef } from 'react';
import SidePanel from './SidePanel';
import PredictionCard from './PredictionCard';
import ConnectionStatus from './ConnectionStatus';
import CandlestickChart from './CandlestickChart';
import ServiceStatusBar from './ServiceStatusBar';
import AccuracyTracker from './AccuracyTracker';
import {
  getHealthStatus,
  createPredictionWebSocket,
  getLatestPrediction,
  startPredictionService,
  stopPredictionService
} from '../services/api';

const PredictionDashboard = () => {
  // Configuration state
  const [selectedPair, setSelectedPair] = useState('USD/BRL(OTC)');
  const [timezone, setTimezone] = useState('Asia/Bangkok');
  const [predictionActive, setPredictionActive] = useState(false);
  
  // Model selection state (managed by SidePanel as single source of truth)
  const [selectedModel, setSelectedModel] = useState(null);

  // Prediction state
  const [prediction, setPrediction] = useState(null);
  const [predictionHistory, setPredictionHistory] = useState([]);
  
  // Connection state
  const [backendStatus, setBackendStatus] = useState('checking');
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  
  // System status
  const [systemStatus, setSystemStatus] = useState({});
  
  // (Timezone remains configurable internally; UI control migrated out for now)

  // Helper: parse backend timestamps as UTC if missing TZ info
  const parseUtc = (ts) => {
    if (!ts) return null;
    if (ts instanceof Date) return ts; // already a Date
    if (/(Z|[\+\-]\d{2}:?\d{2})$/.test(ts)) return new Date(ts);
    return new Date(ts + 'Z');
  };

  // Initialize on component mount
  useEffect(() => {
    checkBackendStatus();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);
  
  // Connect WebSocket when prediction is activated
  useEffect(() => {
    if (predictionActive) {
      connectWebSocket();
      startPredictionService().catch(error => {
        console.error('Failed to start prediction service:', error);
      });
    } else {
      if (wsRef.current) {
        wsRef.current.close();
        setWsConnected(false);
      }
      stopPredictionService().catch(error => {
        console.error('Failed to stop prediction service:', error);
      });
    }
  }, [predictionActive]);
  
  // Subscribe to new pair when it changes
  useEffect(() => {
    if (wsConnected && wsRef.current && predictionActive) {
      subscribeToPredictions();
    }
  }, [selectedPair, wsConnected]);

  const checkBackendStatus = async () => {
    try {
      const data = await getHealthStatus();
      setBackendStatus((data.status === 'healthy' || data.status === 'degraded') ? 'connected' : 'error');
    } catch (error) {
      console.error('Backend health check failed:', error);
      setBackendStatus('error');
    }
  };

  const connectWebSocket = () => {
    try {
      // Use the API service to create WebSocket
      const ws = createPredictionWebSocket();
      
      ws.onopen = () => {
        console.log('🔌 ML WebSocket connected');
        setWsConnected(true);
        subscribeToPredictions();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('🤖 ML WebSocket message:', data);
          
          if (data.type === 'prediction' && data.trading_pair === selectedPair) {
            // Add a timestamp to ensure we're getting fresh data
            const predictionData = {
              direction: (data.prediction || '').toLowerCase(),
              probability: data.probability,
              confidence: data.confidence,
              expectedChange: data.expected_change,
              modelType: data.model_used,
              timestamp: parseUtc(data.timestamp || new Date().toISOString()),
              tradingPair: data.trading_pair,
              _receivedAt: new Date().getTime() // Add client-side timestamp for freshness tracking
            };
            
            console.log('🤖 ML Prediction received:', predictionData);
            setPrediction(predictionData);
            
            // Add to history
            setPredictionHistory(prev => {
              const newHistory = [predictionData, ...prev];
              // Keep only last 20 predictions
              return newHistory.slice(0, 20);
            });
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log('ML WebSocket disconnected');
        setWsConnected(false);
        // Only reconnect if prediction is still active
        if (predictionActive) {
          setTimeout(connectWebSocket, 3000);
        }
      };

      ws.onerror = (error) => {
        console.error('ML WebSocket error:', error);
        setWsConnected(false);
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('ML WebSocket connection failed:', error);
      setWsConnected(false);
    }
  };

  const subscribeToPredictions = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const subscribeMsg = {
        action: 'subscribe',
        trading_pair: selectedPair,
        // Include selected model information if available
        model_name: selectedModel?.name,
        model_type: selectedModel?.algorithm
      };
      wsRef.current.send(JSON.stringify(subscribeMsg));
      console.log(`🔔 Subscribed to predictions for ${selectedPair} using model ${selectedModel?.name || 'default'}`);
    } else {
      console.warn('WebSocket not connected, cannot subscribe');
    }
  };

  const fetchLatestPrediction = async () => {
    try {
      // Pass selected model information to get the latest prediction
      const data = await getLatestPrediction(
        selectedPair, 
        selectedModel?.algorithm, 
        selectedModel?.name
      );
      
      if (!data || !data.prediction) {
        console.log('No prediction available yet');
        return;
      }
      
      console.log('📊 Latest prediction:', data);
      
      // Format the prediction data
      const predictionData = {
        direction: (data.prediction || '').toLowerCase(),
        probability: data.probability,
        confidence: data.confidence,
        expectedChange: data.expected_change,
        modelType: data.model_used,
        timestamp: parseUtc(data.timestamp),
        tradingPair: selectedPair
      };
      
      // Always update the prediction with the latest data
      setPrediction(predictionData);
      
      // Add to history if it's different from the previous one
      setPredictionHistory(prev => {
        // Check if we already have this exact prediction (avoid duplicates)
        if (prev.length > 0 && 
            prev[0].direction === predictionData.direction && 
            prev[0].probability === predictionData.probability &&
            prev[0].confidence === predictionData.confidence &&
            prev[0].modelType === predictionData.modelType) {
          return prev;
        }
        
        const newHistory = [predictionData, ...prev];
        return newHistory.slice(0, 20); // Keep only last 20 predictions
      });
    } catch (error) {
      console.error('Failed to fetch prediction:', error);
    }
  };

  const handlePairChange = (newPair) => {
    setSelectedPair(newPair);
    setPrediction(null);
  };

  const handleTimezoneChange = (newTimezone) => {
    setTimezone(newTimezone);
  };

  // SidePanel will manage start/stop and model selection directly

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="header">
        <div className="header-title">
          OTC Predictor - ML Prediction Dashboard
        </div>
        <div className="header-controls">
          <ConnectionStatus
            wsConnected={wsConnected}
            backendStatus={backendStatus}
          />
        </div>
      </header>

      {/* Service Status Bar */}
      <ServiceStatusBar />

      {/* Main Content: SidePanel | Chart | Predictions */}
      <div className="main-content three-col">
        {/* Left Panel */}
        <div className="config-panel">
          <SidePanel
            selectedPair={selectedPair}
            onPairChange={handlePairChange}
            selectedModel={selectedModel}
            onModelChange={setSelectedModel}
            predictionActive={predictionActive}
            setPredictionActive={setPredictionActive}
          />
        </div>

        {/* Center Panel - Candlestick Chart */}
        <div className="chart-center-panel">
          <CandlestickChart
            tradingPair={selectedPair}
            prediction={prediction}
          />
        </div>

        {/* Right Panel - Prediction Display */}
        <div className="prediction-panel">
          {/* Current Prediction */}
          <div className="current-prediction">
            <h2>Current Prediction</h2>
            {prediction ? (
              <PredictionCard prediction={prediction} timezone={timezone} />
            ) : (
              <div className="no-prediction">
                {predictionActive ? (
                  <div className="loading-prediction">
                    <div className="spinner"></div>
                    <p>Waiting for prediction...</p>
                  </div>
                ) : (
                  <p>Start the prediction service to see results</p>
                )}
              </div>
            )}
          </div>

          {/* Accuracy Tracker */}
          <AccuracyTracker />

          {/* Prediction History */}
          <div className="prediction-history">
            <h2>Prediction History</h2>
            {predictionHistory.length > 0 ? (
              <div className="history-list">
                {predictionHistory.map((pred, index) => (
                  <div key={index} className="history-item">
                    <PredictionCard
                      prediction={pred}
                      timezone={timezone}
                      compact={true}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-history">No prediction history available</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PredictionDashboard;