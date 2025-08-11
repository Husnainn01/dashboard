# OTC Predictor Cleanup Plan

This document outlines the files that are no longer needed in the microservices architecture, specifically focusing on USD/BRL(OTC) trading pair.

## Files That Can Be Safely Removed

### Monolithic Architecture Files

1. `/backend/main.py` - The monolithic orchestrator is no longer needed as we've moved to microservices
2. `/backend/services/` directory:
   - `data_service.py` - Replaced by data_collection_service microservice
   - `ml_prediction_service.py` - Replaced by prediction_service microservice
   - `prediction_api.py` - Replaced by api_gateway microservice
   - `custom_quotex_client.py` - Keep this as it might still be used by the data_collection module

3. `/backend/signal_generator/` directory:
   - This module is not being used in the microservices architecture

### Legacy Frontend Files

1. Any deleted files that were previously tracked:
   - `otc-predictor/frontend/components/Dashboard.jsx`
   - `otc-predictor/frontend/components/TradingDashboard.jsx`
   - `otc-predictor/frontend/components/PairSelector.jsx`
   - `otc-predictor/frontend/components/TimeframeSelector.jsx`
   - `otc-predictor/frontend/components/MLPredictionToggle.jsx`
   - `otc-predictor/frontend/components/CandlestickChart.jsx`
   - `otc-predictor/frontend/pages/prediction.jsx`

## Files to Keep

### Core Modules

1. `/backend/data_collection/` directory:
   - Still being used by the data_collection_service microservice

2. `/backend/database/` directory:
   - `mongodb_models.py` - Used by multiple microservices
   - `models.py` - May contain shared model definitions

3. `/backend/ml_models/` directory:
   - `feature_engineering.py` - Used by prediction_service and ml_training_service
   - `model_trainer.py` - Used by prediction_service and ml_training_service

### Microservices

All files in the `/backend/microservices/` directory should be kept as they form the core of the new architecture:

1. `api_gateway/`
2. `data_collection_service/`
3. `ml_training_service/`
4. `prediction_service/`

### Frontend Files

All current frontend files should be kept, with the updates to focus on USD/BRL(OTC):

1. `components/ConfigurationPanel.jsx`
2. `components/ConnectionStatus.jsx`
3. `components/MLControlPanel.jsx`
4. `components/PredictionCard.jsx`
5. `components/PredictionDashboard.jsx`
6. `pages/_app.jsx`
7. `pages/index.jsx`

## Implementation Notes

1. **Do not delete files immediately**. First, create a backup or move them to a `legacy` directory.
2. Test the system thoroughly after removing files to ensure everything still works correctly.
3. Update any documentation to reflect the changes.
4. Consider creating a `DEPRECATED.md` file to document what was removed and why.
