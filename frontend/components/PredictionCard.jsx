import { useState } from 'react';

const PredictionCard = ({ prediction, timezone = 'UTC', compact = false }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!prediction) return null;
  
  const { 
    direction, 
    probability, 
    expectedChange, 
    modelType, 
    timestamp, 
    tradingPair 
  } = prediction;
  
  // Format timestamp according to timezone
  const formattedTime = timestamp ? new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit',
    timeZone: timezone
  }) : 'Unknown';
  
  const formattedDate = timestamp ? new Date(timestamp).toLocaleDateString([], {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: timezone
  }) : 'Unknown';
  
  // Calculate confidence percentage
  const confidencePercent = probability ? Math.round(probability * 100) : 0;
  
  // Determine color scheme based on direction
  const isUp = direction === 'up';
  const directionColor = isUp ? '#00ff88' : '#ff4444';
  const bgColor = isUp ? 'rgba(0, 255, 136, 0.1)' : 'rgba(255, 68, 68, 0.1)';
  const directionSymbol = isUp ? '↗' : '↘';
  const directionText = isUp ? 'UP' : 'DOWN';
  
  if (compact) {
    // Compact version for history list
    return (
      <div 
        className="prediction-card compact"
        style={{
          borderLeft: `4px solid ${directionColor}`,
          backgroundColor: bgColor,
        }}
      >
        <div className="prediction-header">
          <div className="prediction-direction" style={{ color: directionColor }}>
            {directionSymbol} {directionText}
          </div>
          <div className="prediction-time">
            {formattedTime}
          </div>
        </div>
        <div className="prediction-details">
          <div className="prediction-confidence">
            {confidencePercent}% confidence
          </div>
          <div className="prediction-pair">
            {tradingPair}
          </div>
        </div>
      </div>
    );
  }
  
  // Full version
  return (
    <div 
      className="prediction-card"
      style={{
        borderColor: directionColor,
        backgroundColor: bgColor,
      }}
    >
      <div className="prediction-main">
        <div className="prediction-direction-large" style={{ color: directionColor }}>
          {directionSymbol} {directionText}
        </div>
        <div className="prediction-confidence-large">
          <div className="confidence-value">{confidencePercent}%</div>
          <div className="confidence-label">Confidence</div>
        </div>
      </div>
      
      <div className="prediction-meta">
        <div className="prediction-pair-info">
          <span className="meta-label">Pair:</span>
          <span className="meta-value">{tradingPair}</span>
        </div>
        <div className="prediction-time-info">
          <span className="meta-label">Time:</span>
          <span className="meta-value">{formattedTime}</span>
        </div>
        <div className="prediction-date-info">
          <span className="meta-label">Date:</span>
          <span className="meta-value">{formattedDate}</span>
        </div>
      </div>
      
      <button 
        className="prediction-expand-btn"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? 'Show Less' : 'Show More'}
      </button>
      
      {expanded && (
        <div className="prediction-expanded">
          <div className="expanded-row">
            <span className="expanded-label">Expected Change:</span>
            <span className="expanded-value" style={{ color: directionColor }}>
              {expectedChange > 0 ? '+' : ''}{(expectedChange * 100).toFixed(2)}%
            </span>
          </div>
          <div className="expanded-row">
            <span className="expanded-label">Model:</span>
            <span className="expanded-value">{modelType || 'Unknown'}</span>
          </div>
          <div className="expanded-row">
            <span className="expanded-label">Timezone:</span>
            <span className="expanded-value">{timezone}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default PredictionCard;
