import { useState, useEffect } from 'react';

/**
 * Modal component for selecting a model before starting predictions
 */
const ModelSelectionModal = ({
  isOpen,
  models,
  selectedModel,
  onSelectModel,
  onConfirm,
  onCancel,
  isLoading
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredModels, setFilteredModels] = useState(models);
  
  // Update filtered models when models or search term changes
  useEffect(() => {
    if (!searchTerm) {
      setFilteredModels(models);
      return;
    }
    
    const term = searchTerm.toLowerCase();
    const filtered = models.filter(model => 
      (model.name && model.name.toLowerCase().includes(term)) ||
      (model.algorithm && model.algorithm.toLowerCase().includes(term))
    );
    
    setFilteredModels(filtered);
  }, [models, searchTerm]);
  
  // Format date for display
  const formatDate = (dateString) => {
    if (!dateString || dateString === 'Unknown') return 'Unknown';
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch (e) {
      return dateString;
    }
  };
  
  // Format accuracy for display
  const formatAccuracy = (accuracy) => {
    if (typeof accuracy !== 'number') return 'N/A';
    return `${(accuracy * 100).toFixed(1)}%`;
  };
  
  if (!isOpen) return null;
  
  return (
    <div className="modal-overlay">
      <div className="modal-container">
        <div className="modal-header">
          <h2>Select Model for Prediction</h2>
          <button className="modal-close-btn" onClick={onCancel}>×</button>
        </div>
        
        <div className="modal-body">
          <p className="modal-description">
            Please select a model to use for predictions. The model will be used directly without caching.
          </p>
          
          {/* Search input */}
          <div className="modal-search">
            <input
              type="text"
              placeholder="Search models..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="modal-search-input"
            />
          </div>
          
          {/* Models list */}
          <div className="models-list">
            {isLoading ? (
              <div className="loading-indicator">
                <div className="spinner"></div>
                <p>Loading models...</p>
              </div>
            ) : filteredModels.length === 0 ? (
              <div className="no-models">
                <p>No models found. Please train a model first.</p>
              </div>
            ) : (
              filteredModels.map(model => (
                <div 
                  key={model.id}
                  className={`model-item ${selectedModel?.id === model.id ? 'selected' : ''}`}
                  onClick={() => onSelectModel(model)}
                >
                  <div className="model-header">
                    <div className="model-name">{model.name}</div>
                    <div className={`model-algorithm ${model.algorithm}`}>
                      {model.algorithm}
                    </div>
                  </div>
                  
                  <div className="model-details">
                    <div className="model-accuracy">
                      <span className="detail-label">Accuracy:</span>
                      <span className="detail-value">{formatAccuracy(model.accuracy)}</span>
                    </div>
                    <div className="model-created">
                      <span className="detail-label">Created:</span>
                      <span className="detail-value">{formatDate(model.created_at)}</span>
                    </div>
                    <div className="model-location">
                      <span className="detail-label">Location:</span>
                      <span className="detail-value">{model.location}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
        
        <div className="modal-footer">
          <button 
            className="btn btn-secondary" 
            onClick={onCancel}
          >
            Cancel
          </button>
          <button 
            className="btn btn-primary" 
            onClick={onConfirm}
            disabled={!selectedModel || isLoading}
          >
            Start Prediction
          </button>
        </div>
      </div>
      
      {/* Add modal styles */}
      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.7);
          display: flex;
          justify-content: center;
          align-items: center;
          z-index: 1000;
        }
        
        .modal-container {
          background-color: #1e1e2f;
          border-radius: 8px;
          width: 90%;
          max-width: 600px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 5px 15px rgba(0, 0, 0, 0.5);
          display: flex;
          flex-direction: column;
        }
        
        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 15px 20px;
          border-bottom: 1px solid #2d2d42;
        }
        
        .modal-header h2 {
          margin: 0;
          color: #fff;
          font-size: 1.5rem;
        }
        
        .modal-close-btn {
          background: none;
          border: none;
          color: #aaa;
          font-size: 1.5rem;
          cursor: pointer;
        }
        
        .modal-body {
          padding: 20px;
          flex: 1;
          overflow-y: auto;
        }
        
        .modal-description {
          margin-bottom: 20px;
          color: #ccc;
        }
        
        .modal-search {
          margin-bottom: 20px;
        }
        
        .modal-search-input {
          width: 100%;
          padding: 10px;
          border-radius: 4px;
          border: 1px solid #2d2d42;
          background-color: #252537;
          color: #fff;
        }
        
        .models-list {
          display: flex;
          flex-direction: column;
          gap: 10px;
          max-height: 400px;
          overflow-y: auto;
        }
        
        .model-item {
          padding: 15px;
          border-radius: 6px;
          background-color: #252537;
          cursor: pointer;
          transition: all 0.2s ease;
          border: 1px solid transparent;
        }
        
        .model-item:hover {
          background-color: #2a2a3d;
        }
        
        .model-item.selected {
          border-color: #1d8cf8;
          background-color: #1d8cf820;
        }
        
        .model-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
        }
        
        .model-name {
          font-weight: bold;
          font-size: 1.1rem;
          color: #fff;
        }
        
        .model-algorithm {
          padding: 3px 8px;
          border-radius: 4px;
          font-size: 0.8rem;
          font-weight: bold;
        }
        
        .model-algorithm.xgboost {
          background-color: #ff8d72;
          color: #000;
        }
        
        .model-algorithm.lightgbm {
          background-color: #00f2c3;
          color: #000;
        }
        
        .model-algorithm.random_forest {
          background-color: #e14eca;
          color: #fff;
        }
        
        .model-details {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
          font-size: 0.9rem;
        }
        
        .detail-label {
          color: #aaa;
          margin-right: 5px;
        }
        
        .detail-value {
          color: #fff;
        }
        
        .modal-footer {
          padding: 15px 20px;
          border-top: 1px solid #2d2d42;
          display: flex;
          justify-content: flex-end;
          gap: 10px;
        }
        
        .loading-indicator {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 30px;
        }
        
        .spinner {
          border: 4px solid rgba(0, 0, 0, 0.1);
          border-radius: 50%;
          border-top: 4px solid #1d8cf8;
          width: 30px;
          height: 30px;
          animation: spin 1s linear infinite;
          margin-bottom: 15px;
        }
        
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        
        .no-models {
          text-align: center;
          padding: 30px;
          color: #aaa;
        }
      `}</style>
    </div>
  );
};

export default ModelSelectionModal;
