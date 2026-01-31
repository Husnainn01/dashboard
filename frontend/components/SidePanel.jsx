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
import TrainingModal from './TrainingModal';

const DEFAULT_PAIRS = [
  { value: 'USD/BRL(OTC)', label: 'USD/BRL OTC', flag: '' },
];

// Parse date string, treating timezone-naive strings (from Python's datetime.now().isoformat()) as UTC
function parseDate(dateStr) {
  if (!dateStr) return null;
  let s = String(dateStr);
  // If the string has no timezone indicator (no Z, no +/- offset after time), treat as UTC
  if (s.includes('T') && !s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) {
    s += 'Z';
  }
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

function timeAgo(dateStr) {
  const d = parseDate(dateStr);
  if (!d) return '';
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
  const d = parseDate(dateStr);
  if (!d) return 'Unknown date';
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

  // Training modal state
  const [showTrainingModal, setShowTrainingModal] = useState(false);
  const [trainingJobId, setTrainingJobId] = useState(null);
  const [trainingStatus, setTrainingStatus] = useState('queued');
  const [trainingProgress, setTrainingProgress] = useState('Queued');
  const [trainingProgressPct, setTrainingProgressPct] = useState(0);
  const [trainingStartedAt, setTrainingStartedAt] = useState(null);
  const [trainingCompletedAt, setTrainingCompletedAt] = useState(null);
  const [trainingError, setTrainingError] = useState(null);
  const [trainingModelType, setTrainingModelType] = useState('xgboost');

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
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
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
    if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null; }
    let attempts = 0;

    const doPoll = async () => {
      attempts++;
      try {
        const job = await getTrainingStatus(jobId);

        // Feed progress into modal state
        if (job.status) setTrainingStatus(job.status);
        if (job.progress) setTrainingProgress(job.progress);
        if (job.progress_pct != null) setTrainingProgressPct(job.progress_pct);
        if (job.started_at) setTrainingStartedAt(job.started_at);
        if (job.completed_at) setTrainingCompletedAt(job.completed_at);

        if (job.status === 'completed') {
          pollRef.current = null;
          setIsTraining(false);
          setTrainMsg('Training completed successfully!');
          setTrainError(null);
          refreshModels();
          setTimeout(() => setTrainMsg(null), 5000);
          return; // stop polling
        } else if (job.status === 'failed') {
          pollRef.current = null;
          setIsTraining(false);
          setTrainMsg(null);
          const errMsg = job.error || 'Training failed';
          let friendlyErr = errMsg;
          if (errMsg.toLowerCase().includes('insufficient data')) {
            friendlyErr = 'Not enough candle data to train. Collect more data and try again.';
          } else if (errMsg.toLowerCase().includes('no training data')) {
            friendlyErr = 'No candle data available for this pair. Start data collection first.';
          }
          setTrainError(friendlyErr);
          setTrainingError(friendlyErr);
          return; // stop polling
        }

        // Stop polling after 10 minutes (~200 attempts at 3s)
        if (attempts > 200) {
          pollRef.current = null;
          setIsTraining(false);
          setTrainMsg(null);
          setTrainError('Training timed out. Check server logs.');
          setTrainingStatus('failed');
          setTrainingError('Training timed out. Check server logs.');
          return;
        }
      } catch (e) {
        console.warn(`Poll attempt ${attempts} failed:`, e?.message || e);
        if (attempts > 200) {
          pollRef.current = null;
          setIsTraining(false);
          setTrainMsg(null);
          setTrainError('Could not get training status. Check server logs.');
          setTrainingStatus('failed');
          setTrainingError('Could not get training status. Check server logs.');
          return;
        }
      }

      // Schedule next poll
      pollRef.current = setTimeout(doPoll, 3000);
    };

    // Fire first poll immediately
    doPoll();
  };

  const resetTrainingModal = () => {
    setShowTrainingModal(false);
    setTrainingJobId(null);
    setTrainingStatus('queued');
    setTrainingProgress('Queued');
    setTrainingProgressPct(0);
    setTrainingStartedAt(null);
    setTrainingCompletedAt(null);
    setTrainingError(null);
  };

  const handleTrainingCancel = () => {
    if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null; }
    setIsTraining(false);
    resetTrainingModal();
  };

  const handleTrainingClose = () => {
    resetTrainingModal();
    // Refresh models on close after completion
    refreshModels();
  };

  const handleTrain = async (modelType = 'xgboost') => {
    try {
      setIsTraining(true);
      setTrainError(null);
      setTrainMsg(null);

      // Open modal immediately
      setTrainingModelType(modelType);
      setTrainingStatus('queued');
      setTrainingProgress('Queued');
      setTrainingProgressPct(0);
      setTrainingStartedAt(null);
      setTrainingCompletedAt(null);
      setTrainingError(null);
      setShowTrainingModal(true);

      const res = await retrainModel(selectedPair, modelType);
      const jobId = res?.job_id;
      setTrainingJobId(jobId);
      if (jobId) {
        pollJobStatus(jobId);
      } else {
        setTimeout(() => {
          refreshModels();
          setIsTraining(false);
          setTrainingStatus('completed');
          setTrainingProgress('Complete');
          setTrainingProgressPct(100);
        }, 8000);
      }
    } catch (e) {
      setTrainError(`Training failed: ${e.message}`);
      setTrainMsg(null);
      setIsTraining(false);
      setTrainingStatus('failed');
      setTrainingError(e.message);
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
        {!showTrainingModal && trainMsg && <div className="sp-hint">{trainMsg}</div>}
        {!showTrainingModal && trainError && (
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

      <TrainingModal
        isOpen={showTrainingModal}
        status={trainingStatus}
        progress={trainingProgress}
        progressPct={trainingProgressPct}
        startedAt={trainingStartedAt}
        completedAt={trainingCompletedAt}
        error={trainingError}
        modelType={trainingModelType}
        tradingPair={selectedPair}
        onCancel={handleTrainingCancel}
        onClose={handleTrainingClose}
      />
    </aside>
  );
}
