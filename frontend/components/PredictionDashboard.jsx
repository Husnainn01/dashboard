import { useState, useEffect, useRef } from 'react';
import ConfigurationPanel from './ConfigurationPanel';
import PredictionCard from './PredictionCard';
import ConnectionStatus from './ConnectionStatus';
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
  const [timezone, setTimezone] = useState('UTC');
  const [predictionActive, setPredictionActive] = useState(false);
  
  // Prediction state
  const [prediction, setPrediction] = useState(null);
  const [predictionHistory, setPredictionHistory] = useState([]);
  
  // Connection state
  const [backendStatus, setBackendStatus] = useState('checking');
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  
  // System status
  const [systemStatus, setSystemStatus] = useState({});
  
  // Available trading pairs (matching backend configuration)
  const tradingPairs = [
    { value: 'USD/BRL(OTC)', label: 'USD/BRL OTC', flag: '🇺🇸🇧🇷' },
    { value: 'NZD/CAD(OTC)', label: 'NZD/CAD OTC', flag: '🇳🇿🇨🇦' },
    { value: 'USD/BDT(OTC)', label: 'USD/BDT OTC', flag: '🇺🇸🇧🇩' },
    { value: 'USD/EGP(OTC)', label: 'USD/EGP OTC', flag: '🇺🇸🇪🇬' }
  ];
  
  // Timezone options
  const timezoneOptions = [
    { value: 'UTC', label: 'UTC' },
    { value: 'America/New_York', label: 'New York (EST/EDT)' },
    { value: 'Europe/London', label: 'London (GMT/BST)' },
    { value: 'Asia/Tokyo', label: 'Tokyo (JST)' }
  ];

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
      setBackendStatus(data.status === 'healthy' || data.status === 'degraded' ? 'connected' : 'error');
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
            const predictionData = {
              direction: data.prediction, // Changed from data.direction to data.prediction
              probability: data.probability,
              expectedChange: data.expected_change,
              modelType: data.model_used,
              timestamp: new Date(data.timestamp),
              tradingPair: data.trading_pair
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
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    
    // Subscribe to ML predictions for the selected pair
    wsRef.current.send(JSON.stringify({
      action: 'subscribe',
      trading_pair: selectedPair
    }));
    
    console.log(`🤖 Subscribed to ML predictions for ${selectedPair}`);
    
    // Also fetch latest prediction via REST API
    fetchLatestPrediction();
  };

  const fetchLatestPrediction = async () => {
    try {
      const data = await getLatestPrediction(selectedPair);
      console.log('🤖 ML Prediction via API:', data);
      
      const predictionData = {
        direction: data.prediction, // Changed from data.direction to data.prediction
        probability: data.probability,
        expectedChange: data.expected_change,
        modelType: data.model_used,
        timestamp: new Date(data.timestamp),
        tradingPair: selectedPair
      };
      
      setPrediction(predictionData);
      
      // Add to history if not already there
      setPredictionHistory(prev => {
        // Check if we already have this prediction (avoid duplicates)
        if (prev.length > 0 && 
            prev[0].direction === predictionData.direction && 
            prev[0].probability === predictionData.probability) {
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

  const togglePrediction = () => {
    setPredictionActive(!predictionActive);
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="header">
        <div className="header-title">
          🤖 OTC Predictor - ML Prediction Dashboard
        </div>
        <div className="header-controls">
          <ConnectionStatus 
            wsConnected={wsConnected}
            backendStatus={backendStatus}
          />
        </div>
      </header>

      {/* Main Content */}
      <div className="main-content">
        {/* Left Panel - Configuration */}
        <div className="config-panel">
          <ConfigurationPanel 
            tradingPairs={tradingPairs}
            timezoneOptions={timezoneOptions}
            selectedPair={selectedPair}
            selectedTimezone={timezone}
            onPairChange={handlePairChange}
            onTimezoneChange={handleTimezoneChange}
            predictionActive={predictionActive}
            onTogglePrediction={togglePrediction}
            backendConnected={backendStatus === 'connected'}
            onSystemStatusChange={setSystemStatus}
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