import { useState, useEffect, useRef } from 'react';
import { getPredictionAccuracy } from '../services/api';

const AccuracyTracker = () => {
  const [accuracy, setAccuracy] = useState(null);
  const [error, setError] = useState(false);
  const intervalRef = useRef(null);

  const fetchAccuracy = async () => {
    try {
      const data = await getPredictionAccuracy();
      setAccuracy(data);
      setError(false);
    } catch {
      setError(true);
    }
  };

  useEffect(() => {
    fetchAccuracy();
    intervalRef.current = setInterval(fetchAccuracy, 30000);
    return () => clearInterval(intervalRef.current);
  }, []);

  if (error || !accuracy) {
    return (
      <div className="accuracy-tracker">
        <h3>Prediction Accuracy</h3>
        <p className="accuracy-unavailable">
          {error ? 'Prediction service unavailable' : 'Loading...'}
        </p>
      </div>
    );
  }

  if (accuracy.total_predictions === 0) {
    return (
      <div className="accuracy-tracker">
        <h3>Prediction Accuracy</h3>
        <p className="accuracy-unavailable">No predictions recorded yet</p>
      </div>
    );
  }

  const pct = (val) => `${(val * 100).toFixed(1)}%`;

  return (
    <div className="accuracy-tracker">
      <h3>Prediction Accuracy</h3>

      <div className="accuracy-hero">
        <span className="accuracy-big-number">{pct(accuracy.win_rate)}</span>
        <span className="accuracy-big-label">Win Rate</span>
      </div>

      <div className="accuracy-stats-grid">
        <div className="accuracy-stat">
          <span className="stat-value">{pct(accuracy.recent_accuracy_24h)}</span>
          <span className="stat-label">24h</span>
        </div>
        <div className="accuracy-stat">
          <span className="stat-value">{pct(accuracy.recent_accuracy_7d)}</span>
          <span className="stat-label">7d</span>
        </div>
        <div className="accuracy-stat">
          <span className="stat-value">{accuracy.total_predictions}</span>
          <span className="stat-label">Total</span>
        </div>
        <div className="accuracy-stat">
          <span className="stat-value">{accuracy.correct_predictions}</span>
          <span className="stat-label">Correct</span>
        </div>
      </div>

      {accuracy.by_model && Object.keys(accuracy.by_model).length > 0 && (
        <div className="accuracy-models">
          <h4>Per Model</h4>
          {Object.entries(accuracy.by_model).map(([model, stats]) => (
            <div key={model} className="accuracy-model-row">
              <span className="model-name">{model}</span>
              <span className="model-accuracy">{pct(stats.accuracy)}</span>
              <span className="model-count">{stats.correct}/{stats.total}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AccuracyTracker;
