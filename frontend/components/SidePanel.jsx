import { useEffect, useState } from 'react';
import {
  getModelsForPair,
  retrainModel,
  selectModel,
  startPredictionService,
  stopPredictionService,
  getTradingPairs,
} from '../services/api';

const DEFAULT_PAIRS = [
  { value: 'USD/BRL(OTC)', label: 'USD/BRL OTC', flag: '' },
];

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const d = new Date(dateStr);
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
  const [serviceBusy, setServiceBusy] = useState(false);
  const [trainingAlgo, setTrainingAlgo] = useState(null);

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
          created_at: m.created_at || m.saved_at,
          location: 'local',
        })
      );
      (data.cloud_models || []).forEach((m) =>
        list.push({
          id: m.model_id || m.model_name,
          name: m.model_name || m.model_id,
          algorithm: inferAlgorithm(m),
          accuracy: m.accuracy,
          created_at: m.created_at || m.saved_at,
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

  const handleTrain = async (modelType = 'xgboost') => {
    try {
      setIsTraining(true);
      setTrainingAlgo(modelType);
      setTrainMsg(`Submitting ${modelType} training job...`);
      const res = await retrainModel(selectedPair, modelType);
      setTrainMsg(`Training started (${modelType})${res?.job_id ? ' · Job: ' + res.job_id : ''}`);
      setTimeout(refreshModels, 8000);
    } catch (e) {
      setTrainMsg(`Training failed (${modelType}): ${e.message}`);
    } finally {
      setTimeout(() => setTrainMsg(null), 6000);
      setIsTraining(false);
      setTrainingAlgo(null);
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
            {isTraining && trainingAlgo === 'xgboost' ? 'Training...' : 'Train XGBoost'}
          </button>
          <button
            className="sp-button"
            onClick={() => handleTrain('lightgbm')}
            disabled={isTraining || serviceBusy}
          >
            {isTraining && trainingAlgo === 'lightgbm' ? 'Training...' : 'Train LightGBM'}
          </button>
          <button
            className="sp-button"
            onClick={() => handleTrain('random_forest')}
            disabled={isTraining || serviceBusy}
          >
            {isTraining && trainingAlgo === 'random_forest' ? 'Training...' : 'Train Random Forest'}
          </button>
        </div>
        {trainMsg && <div className="sp-hint">{trainMsg}</div>}
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
          <div className="sp-hint" style={{ marginTop: 6, lineHeight: 1.4 }}>
            {selectedModel.accuracy != null && (
              <span>Accuracy: <strong>{(selectedModel.accuracy > 1 ? selectedModel.accuracy : selectedModel.accuracy * 100).toFixed(1)}%</strong> · </span>
            )}
            <span>{selectedModel.location === 'cloud' ? '☁ Cloud' : '💻 Local'}</span>
            {selectedModel.created_at && (
              <span> · {timeAgo(selectedModel.created_at)}</span>
            )}
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
