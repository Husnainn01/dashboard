import { useEffect, useState, useRef } from 'react';
import {
  getModelsForPair,
  retrainModel,
  selectModel,
  startPredictionService,
  stopPredictionService,
  getTradingPairs,
  getTrainingStatus,
} from '../services/api';

const DEFAULT_PAIRS = [
  { value: 'USD/BRL(OTC)', label: 'USD/BRL OTC', flag: '' },
];

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const diffMs = now - d;
  if (diffMs < 0) return 'just now';
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
}

function formatDate(dateStr) {
  if (!dateStr) return 'Unknown date';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return 'Unknown date';
  const age = timeAgo(dateStr);
  const full = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  return age ? `${age} (${full})` : full;
}

export default function SidePanel({
  selectedPair,
  onPairChange,
  selectedModel,
  onModelChange,
  predictionActive,
  setPredictionActive,
}) {
  const [pairs, setPairs] = useState(DEFAULT_PAIRS);
  const [loadingModels, setLoadingModels] = useState(false);
  const [models, setModels] = useState([]);
  const [isTraining, setIsTraining] = useState(false);
  const [trainMsg, setTrainMsg] = useState(null);
  const [trainError, setTrainError] = useState(null);
  const [serviceBusy, setServiceBusy] = useState(false);
  const pollRef = useRef(null);

  // Fetch trading pairs from API on mount
  useEffect(() => {
    const fetchPairs = async () => {
      try {
        const data = await getTradingPairs();
        if (data?.trading_pairs?.length) {
          setPairs(data.trading_pairs.map((p) => ({
            value: p,
            label: p.replace('_otc', ' OTC').replace('_', '/'),
            flag: '',
          })));
        }
      } catch (e) {
        console.warn('Failed to fetch trading pairs, using defaults', e);
      }
    };
    fetchPairs();
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // Load models when pair changes
  useEffect(() => {
    if (!selectedPair) return;
    refreshModels();
  }, [selectedPair]);

  const refreshModels = async () => {
    try {
      setLoadingModels(true);
      const data = await getModelsForPair(selectedPair);
      const list = [];
      const inferAlgorithm = (m) => {
        if (m.algorithm) return m.algorithm;
        const name = m.model_name || m.model_id || '';
        const prefix = String(name).toLowerCase();
        if (prefix.startsWith('lightgbm')) return 'lightgbm';
        if (prefix.startsWith('random_forest') || prefix.startsWith('randomforest')) return 'random_forest';
        if (prefix.startsWith('xgboost') || prefix.startsWith('xgb')) return 'xgboost';
        return 'xgboost';
      };

      (data.local_models || []).forEach((m) =>
        list.push({
          id: m.model_id || m.model_name,
          name: m.model_name || m.model_id,
          algorithm: inferAlgorithm(m),
          accuracy: m.accuracy,
          created_at: m.created_at || m.saved_at || m.training_date,
          location: 'local',
        })
      );
      (data.cloud_models || []).forEach((m) =>
        list.push({
          id: m.model_id || m.model_name,
          name: m.model_name || m.model_id,
          algorithm: inferAlgorithm(m),
          accuracy: m.accuracy,
          created_at: m.created_at || m.saved_at || m.training_date,
          location: 'cloud',
        })
      );
      list.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
      setModels(list);
      if (!selectedModel && list.length) onModelChange(list[0]);
    } catch (e) {
      console.error('Failed loading models', e);
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  const pollJobStatus = (jobId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    let attempts = 0;
    pollRef.current = setInterval(async () => {
      attempts++;
      try {
        const job = await getTrainingStatus(jobId);
        if (job.status === 'completed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setIsTraining(false);
          setTrainMsg('Training completed successfully!');
          setTrainError(null);
          refreshModels();
          setTimeout(() => setTrainMsg(null), 5000);
        } else if (job.status === 'failed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setIsTraining(false);
          setTrainMsg(null);
          const errMsg = job.error || 'Training failed';
          // Make common errors more user-friendly
          if (errMsg.toLowerCase().includes('insufficient data')) {
            setTrainError('Not enough candle data to train. Collect more data and try again.');
          } else if (errMsg.toLowerCase().includes('no training data')) {
            setTrainError('No candle data available for this pair. Start data collection first.');
          } else {
            setTrainError(errMsg);
          }
        }
        // Stop polling after 5 minutes
        if (attempts > 60) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setIsTraining(false);
          setTrainMsg(null);
          setTrainError('Training timed out. Check server logs.');
        }
      } catch (e) {
        // Job might not be found yet, keep polling
        if (attempts > 60) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setIsTraining(false);
          setTrainMsg(null);
        }
      }
    }, 5000);
  };

  const handleTrain = async (modelType = 'xgboost') => {
    try {
      setIsTraining(true);
      setTrainError(null);
      setTrainMsg(`Submitting ${modelType} training job...`);
      const res = await retrainModel(selectedPair, modelType);
      const jobId = res?.job_id;
      setTrainMsg(`Training ${modelType}...${jobId ? ' (Job: ' + jobId + ')' : ''}`);
      if (jobId) {
        pollJobStatus(jobId);
      } else {
        // No job ID — fallback to delayed refresh
        setTimeout(() => {
          refreshModels();
          setIsTraining(false);
          setTrainMsg(null);
        }, 8000);
      }
    } catch (e) {
      setTrainError(`Training failed: ${e.message}`);
      setTrainMsg(null);
      setIsTraining(false);
    }
  };

  const handleSelectModel = async (modelId) => {
    const model = models.find((m) => (m.id === modelId || m.name === modelId));
    if (!model) return;
    onModelChange(model);
    try {
      await selectModel(selectedPair, model.name, model.algorithm);
    } catch (e) {
      console.warn('Model select failed (will still keep local selection):', e?.message || e);
    }
  };

  const handleTogglePrediction = async () => {
    if (!selectedModel) return;
    try {
      setServiceBusy(true);
      if (predictionActive) {
        await stopPredictionService();
        setPredictionActive(false);
      } else {
        try {
          await selectModel(selectedPair, selectedModel.name, selectedModel.algorithm);
        } catch (_) {}
        await startPredictionService();
        setPredictionActive(true);
      }
    } catch (e) {
      console.error('Toggle prediction failed', e);
      alert(e?.message || 'Failed to toggle prediction');
    } finally {
      setServiceBusy(false);
    }
  };

  return (
    <aside className="side-panel">
      {/* Step 1: Select Pair */}
      <div className="sp-section sp-section-first">
        <div className="sp-title">1. Select Pair</div>
        <select
          className="sp-select"
          value={selectedPair}
          onChange={(e) => onPairChange(e.target.value)}
        >
          {pairs.map((p) => (
            <option key={p.value} value={p.value}>
              {p.flag} {p.label}
            </option>
          ))}
        </select>
      </div>

      {/* Step 2: Train Model */}
      <div className="sp-section">
        <div className="sp-title">2. Train Model</div>
        <div style={{ display: 'grid', gap: 8 }}>
          <button
            className="sp-button primary"
            onClick={() => handleTrain('xgboost')}
            disabled={isTraining || serviceBusy}
          >
            {isTraining ? 'Training...' : 'Train XGBoost'}
          </button>
          <button
            className="sp-button"
            onClick={() => handleTrain('lightgbm')}
            disabled={isTraining || serviceBusy}
          >
            {isTraining ? 'Training...' : 'Train LightGBM'}
          </button>
          <button
            className="sp-button"
            onClick={() => handleTrain('random_forest')}
            disabled={isTraining || serviceBusy}
          >
            {isTraining ? 'Training...' : 'Train Random Forest'}
          </button>
        </div>
        {trainMsg && <div className="sp-hint">{trainMsg}</div>}
        {trainError && (
          <div className="sp-hint" style={{ color: '#ff6b6b', fontWeight: 500 }}>
            {trainError}
          </div>
        )}
      </div>

      {/* Step 3: Select Model */}
      <div className="sp-section">
        <div className="sp-title">3. Select Model</div>
        <select
          className="sp-select"
          value={selectedModel?.name || ''}
          onChange={(e) => handleSelectModel(e.target.value)}
          disabled={loadingModels || isTraining}
        >
          {models.length === 0 && <option value="">No models</option>}
          {models.map((m) => {
            const acc = m.accuracy != null
              ? `${(m.accuracy > 1 ? m.accuracy : m.accuracy * 100).toFixed(1)}%`
              : '';
            const age = timeAgo(m.created_at);
            return (
              <option key={m.id} value={m.name}>
                {m.algorithm.toUpperCase()}{acc ? ` ${acc}` : ''}{age ? ` · ${age}` : ''} · {m.name}
              </option>
            );
          })}
        </select>
        {selectedModel && (
          <div className="sp-hint" style={{ marginTop: 6, lineHeight: 1.5 }}>
            {selectedModel.accuracy != null && (
              <span>Accuracy: <strong>{(selectedModel.accuracy > 1 ? selectedModel.accuracy : selectedModel.accuracy * 100).toFixed(1)}%</strong> · </span>
            )}
            <span>{selectedModel.location === 'cloud' ? 'Cloud' : 'Local'}</span>
            <br />
            <span style={{ opacity: 0.8 }}>{formatDate(selectedModel.created_at)}</span>
          </div>
        )}
        <button className="sp-button ghost" onClick={refreshModels} disabled={loadingModels}>
          {loadingModels ? 'Loading...' : 'Refresh models'}
        </button>
      </div>

      {/* Step 4: Start / Stop Prediction */}
      <div className="sp-section">
        <div className="sp-title">4. Prediction Service</div>
        <button
          className={`sp-button ${predictionActive ? 'danger' : 'success'}`}
          onClick={handleTogglePrediction}
          disabled={!selectedModel || serviceBusy}
        >
          {predictionActive ? 'Stop Prediction' : 'Start Prediction'}
        </button>
        {!selectedModel && (
          <div className="sp-hint">Select a model to enable predictions</div>
        )}
      </div>

      <div className="sp-footer">v1 · {new Date().getFullYear()}</div>
    </aside>
  );
}
