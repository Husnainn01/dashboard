import { useState, useEffect, useRef } from 'react';
import ConfigurationPanel from './ConfigurationPanel';
import PredictionCard from './PredictionCard';
import ConnectionStatus from './ConnectionStatus';
import ModelSelectionModal from './ModelSelectionModal';
import { 
  getHealthStatus, 
  createPredictionWebSocket, 
  getLatestPrediction,
  startPredictionService,
  stopPredictionService,
  getModelsForPair
} from '../services/api';

const PredictionDashboard = () => {
  // Configuration state
  const [selectedPair, setSelectedPair] = useState('USD/BRL(OTC)');
  const [timezone, setTimezone] = useState('Asia/Bangkok');
  const [predictionActive, setPredictionActive] = useState(false);
  
  // Model selection state
  const [showModelSelection, setShowModelSelection] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  
  // Prediction state
  const [prediction, setPrediction] = useState(null);
  const [predictionHistory, setPredictionHistory] = useState([]);
  
  // Connection state
  const [backendStatus, setBackendStatus] = useState('checking');
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  
  // System status
  const [systemStatus, setSystemStatus] = useState({});
  
  // Available trading pairs - focused only on USD/BRL(OTC)
  const tradingPairs = [
    { value: 'USD/BRL(OTC)', label: 'USD/BRL OTC', flag: '🇺🇸🇧🇷' }
  ];
  
  // Timezone options
  const timezoneOptions = [
    { value: 'Asia/Bangkok', label: 'UTC+7 (Bangkok)' },
    { value: 'UTC', label: 'UTC' },
    { value: 'America/New_York', label: 'New York (EST/EDT)' },
    { value: 'Europe/London', label: 'London (GMT/BST)' },
    { value: 'Asia/Tokyo', label: 'Tokyo (JST)' }
  ];

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
            // Add a timestamp to ensure we're getting fresh data
            const predictionData = {
              direction: data.prediction, // Changed from data.direction to data.prediction
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
        direction: data.prediction,
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

  const togglePrediction = () => {
    if (!predictionActive) {
      // When starting predictions, first show model selection modal
      fetchAvailableModels();
      setShowModelSelection(true);
    } else {
      // When stopping predictions, just stop
      setPredictionActive(false);
    }
  };
  
  // Fetch available models for the selected trading pair
  const fetchAvailableModels = async () => {
    console.log(`🔄 Starting to fetch models for pair: ${selectedPair}`);
    setIsLoadingModels(true);
    try {
      console.log(`📡 Calling API to get models for pair: ${selectedPair}`);
      const modelsData = await getModelsForPair(selectedPair);
      console.log(`📊 Raw models data received:`, modelsData);
      
      // Create formatted models array
      const formattedModels = [];
      
      // Process local models
      if (modelsData.local_models && Array.isArray(modelsData.local_models)) {
        modelsData.local_models.forEach(model => {
          console.log(`🔍 Local model raw data:`, model);
          console.log(`🔢 Local model accuracy sources:`, {
            directAccuracy: model.accuracy,
            metricsAccuracy: model.metrics?.accuracy,
            rawModel: JSON.stringify(model)
          });
          
          formattedModels.push({
            id: model.model_id || model.model_name,
            name: model.model_name || model.model_id,
            algorithm: model.algorithm || 'unknown',
            accuracy: model.accuracy || model.metrics?.accuracy || 0,
            created_at: model.created_at || 'Unknown',
            location: 'local'
          });
        });
        console.log(`📊 Processed ${modelsData.local_models.length} local models`);
      }
      
      // Process cloud models
      if (modelsData.cloud_models && Array.isArray(modelsData.cloud_models)) {
        modelsData.cloud_models.forEach(model => {
          console.log(`🔍 Cloud model raw data:`, model);
          console.log(`🔢 Cloud model accuracy sources:`, {
            directAccuracy: model.accuracy,
            metricsAccuracy: model.metrics?.accuracy,
            rawModel: JSON.stringify(model)
          });
          
          formattedModels.push({
            id: model.model_id || model.model_name,
            name: model.model_name || model.model_id,
            algorithm: model.algorithm || 'unknown',
            accuracy: model.accuracy || model.metrics?.accuracy || 0,
            created_at: model.created_at || 'Unknown',
            location: 'cloud'
          });
          console.log(`Model ${model.model_id || model.model_name} accuracy:`, model.accuracy || model.metrics?.accuracy || 0);
        });
        console.log(`📊 Processed ${modelsData.cloud_models.length} cloud models`);
      }
      
      console.log(`✅ Total models available: ${formattedModels.length}`);
      
      if (formattedModels.length === 0) {
        console.warn(`⚠️ No models found for pair: ${selectedPair}`);
      } else {
        console.log(`📋 Models available:`, formattedModels.map(m => ({ id: m.id, algorithm: m.algorithm })));
      }
      
      // Sort by creation date (newest first)
      formattedModels.sort((a, b) => {
        const dateA = new Date(a.created_at);
        const dateB = new Date(b.created_at);
        return dateB - dateA;
      });
      
      setAvailableModels(formattedModels);
      
      // Pre-select the newest model if any exist
      if (formattedModels.length > 0) {
        setSelectedModel(formattedModels[0]);
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
    } finally {
      setIsLoadingModels(false);
    }
  };
  
  // Handle model selection confirmation
  const handleModelSelectionConfirm = () => {
    setShowModelSelection(false);
    if (selectedModel) {
      console.log(`Selected model: ${selectedModel.name} (${selectedModel.algorithm})`);
      setPredictionActive(true);
    }
  };
  
  // Handle model selection cancellation
  const handleModelSelectionCancel = () => {
    setShowModelSelection(false);
    setSelectedModel(null);
  };

  return (
    <div className="dashboard-container">
      {/* Model Selection Modal */}
      {showModelSelection && (
        <ModelSelectionModal
          isOpen={showModelSelection}
          models={availableModels}
          selectedModel={selectedModel}
          onSelectModel={setSelectedModel}
          onConfirm={handleModelSelectionConfirm}
          onCancel={handleModelSelectionCancel}
          isLoading={isLoadingModels}
        />
      )}
      {/* Header */}
      <header className="header">
        <div className="header-title">
          🤖 OTC Predictor - USD/BRL(OTC) ML Prediction Dashboard
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