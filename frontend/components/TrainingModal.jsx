import { useEffect, useState, useRef } from 'react';

function formatElapsed(seconds) {
  if (seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m > 0) {
    return `${m}m ${s.toString().padStart(2, '0')}s`;
  }
  return `${s}s`;
}

const STATUS_CONFIG = {
  queued: { label: 'Queued', color: '#f5a623', bgColor: '#f5a62320' },
  training: { label: 'Training', color: '#1d8cf8', bgColor: '#1d8cf820' },
  completed: { label: 'Completed', color: '#00f2c3', bgColor: '#00f2c320' },
  failed: { label: 'Failed', color: '#ff6b6b', bgColor: '#ff6b6b20' },
};

export default function TrainingModal({
  isOpen,
  status,
  progress,
  progressPct,
  startedAt,
  completedAt,
  error,
  modelType,
  tradingPair,
  onCancel,
  onClose,
}) {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  // Elapsed time counter
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);

    if (!startedAt || status === 'completed' || status === 'failed') {
      // Calculate final elapsed if we have both timestamps
      if (startedAt && completedAt) {
        setElapsed(Math.floor((new Date(completedAt) - new Date(startedAt)) / 1000));
      } else if (startedAt) {
        setElapsed(Math.floor((Date.now() - new Date(startedAt)) / 1000));
      }
      return;
    }

    // Live counter
    const start = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    timerRef.current = setInterval(tick, 1000);

    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [startedAt, completedAt, status]);

  if (!isOpen) return null;

  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.queued;
  const isDone = status === 'completed' || status === 'failed';
  const isActive = status === 'training';
  const pct = progressPct || 0;
  const indeterminate = isActive && pct === 0;

  return (
    <div className="tm-overlay">
      <div className="tm-container">
        {/* Header */}
        <div className="tm-header">
          <h2 className="tm-title">Training Model</h2>
          <button className="tm-close-x" onClick={isDone ? onClose : onCancel}>&times;</button>
        </div>

        {/* Body */}
        <div className="tm-body">
          {/* Model info */}
          <div className="tm-info-row">
            <span className="tm-label">Pair</span>
            <span className="tm-value">{tradingPair || '—'}</span>
          </div>
          <div className="tm-info-row">
            <span className="tm-label">Algorithm</span>
            <span className="tm-value">{(modelType || 'xgboost').toUpperCase()}</span>
          </div>

          {/* Status badge */}
          <div className="tm-status-row">
            <span
              className={`tm-badge${isActive ? ' tm-badge-pulse' : ''}`}
              style={{ color: cfg.color, backgroundColor: cfg.bgColor, borderColor: cfg.color }}
            >
              {cfg.label}
            </span>
            {startedAt && (
              <span className="tm-elapsed">{formatElapsed(elapsed)}</span>
            )}
          </div>

          {/* Progress bar */}
          <div className="tm-progress-track">
            <div
              className={`tm-progress-fill${indeterminate ? ' tm-indeterminate' : ''}`}
              style={indeterminate ? {} : { width: `${pct}%` }}
            />
          </div>

          {/* Progress label */}
          <div className="tm-progress-label">{progress || 'Waiting...'}</div>

          {/* Error display */}
          {status === 'failed' && error && (
            <div className="tm-error">{error}</div>
          )}
        </div>

        {/* Footer */}
        <div className="tm-footer">
          {isDone ? (
            <button className="tm-btn tm-btn-primary" onClick={onClose}>Close</button>
          ) : (
            <button className="tm-btn tm-btn-secondary" onClick={onCancel}>Cancel</button>
          )}
        </div>
      </div>

      <style jsx>{`
        .tm-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          display: flex;
          justify-content: center;
          align-items: center;
          z-index: 1100;
        }

        .tm-container {
          background: #1e1e2f;
          border-radius: 10px;
          width: 90%;
          max-width: 440px;
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .tm-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid #2d2d42;
        }

        .tm-title {
          margin: 0;
          color: #fff;
          font-size: 1.2rem;
          font-weight: 600;
        }

        .tm-close-x {
          background: none;
          border: none;
          color: #888;
          font-size: 1.5rem;
          cursor: pointer;
          line-height: 1;
          padding: 0 4px;
        }
        .tm-close-x:hover { color: #fff; }

        .tm-body {
          padding: 20px;
        }

        .tm-info-row {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
        }

        .tm-label {
          color: #888;
          font-size: 0.85rem;
        }

        .tm-value {
          color: #ddd;
          font-size: 0.85rem;
          font-weight: 500;
        }

        .tm-status-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin: 16px 0 12px;
        }

        .tm-badge {
          display: inline-block;
          padding: 4px 12px;
          border-radius: 20px;
          font-size: 0.8rem;
          font-weight: 600;
          border: 1px solid;
        }

        .tm-badge-pulse {
          animation: tmPulse 2s ease-in-out infinite;
        }

        @keyframes tmPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }

        .tm-elapsed {
          color: #aaa;
          font-size: 0.9rem;
          font-variant-numeric: tabular-nums;
        }

        .tm-progress-track {
          width: 100%;
          height: 6px;
          background: #252537;
          border-radius: 3px;
          overflow: hidden;
          margin-bottom: 8px;
        }

        .tm-progress-fill {
          height: 100%;
          background: #1d8cf8;
          border-radius: 3px;
          transition: width 0.5s ease;
        }

        .tm-indeterminate {
          width: 40% !important;
          animation: tmSlide 1.4s ease-in-out infinite;
        }

        @keyframes tmSlide {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(350%); }
        }

        .tm-progress-label {
          color: #aaa;
          font-size: 0.85rem;
          min-height: 1.2em;
        }

        .tm-error {
          margin-top: 12px;
          padding: 10px 14px;
          background: #ff6b6b18;
          border: 1px solid #ff6b6b44;
          border-radius: 6px;
          color: #ff6b6b;
          font-size: 0.85rem;
          line-height: 1.4;
        }

        .tm-footer {
          padding: 14px 20px;
          border-top: 1px solid #2d2d42;
          display: flex;
          justify-content: flex-end;
          gap: 10px;
        }

        .tm-btn {
          padding: 8px 20px;
          border-radius: 6px;
          font-size: 0.9rem;
          font-weight: 500;
          cursor: pointer;
          border: none;
        }

        .tm-btn-primary {
          background: #1d8cf8;
          color: #fff;
        }
        .tm-btn-primary:hover { background: #1a7de0; }

        .tm-btn-secondary {
          background: #252537;
          color: #ccc;
          border: 1px solid #3a3a50;
        }
        .tm-btn-secondary:hover { background: #2d2d42; }
      `}</style>
    </div>
  );
}
