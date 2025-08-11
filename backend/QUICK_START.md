# 🚀 OTC Predictor - Quick Start Guide

## 🎯 What This System Does

**Real-time trading prediction system** that:
- 📊 **Collects live data** from PyQuotex 24/7
- 🤖 **Trains ML models** (Random Forest, XGBoost, LightGBM)
- 🔮 **Makes predictions** via REST API
- 💾 **Stores everything** in MongoDB Atlas

## ⚡ Quick Setup (5 Minutes)

### 1. **Set PyQuotex Credentials**

Edit `config.py` and add your credentials:

```python
# PyQuotex Settings
QUOTEX_EMAIL = "your-email@example.com"     # Your PyQuotex email
QUOTEX_PASSWORD = "your-password"           # Your PyQuotex password
```

### 2. **Install Dependencies**

```bash
# Activate virtual environment
source venv/bin/activate

# Install all requirements
pip install -r requirements.txt
```

### 3. **Run the System**

```bash
# Run both data collection + API (recommended)
python main.py

# Or run just the API (if you have existing data)
python main.py --mode api

# Or run just data collection
python main.py --mode data
```

## 🌐 API Endpoints

Once running, visit: **http://localhost:8000/docs**

### Key Endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API status |
| `/predict` | POST | Make prediction |
| `/predict/EURUSD OTC` | GET | Quick prediction |
| `/models` | GET | Available models |
| `/status` | GET | Service status |
| `/health` | GET | Health check |

### Example API Usage:

```bash
# Get prediction
curl http://localhost:8000/predict/EURUSD%20OTC

# Response:
{
  "trading_pair": "EURUSD OTC",
  "prediction": "up",
  "confidence": 0.85,
  "probability": 0.85,
  "model_used": "random_forest",
  "timestamp": "2025-08-06T08:30:00",
  "features_used": 82,
  "model_accuracy": 0.65
}
```

## 🔧 Advanced Usage

### Different Run Modes:

```bash
# Full system (data + API)
python main.py

# API only (port 8000)
python main.py --mode api

# Data collection only
python main.py --mode data

# Custom API port
python main.py --port 9000

# API on different host
python main.py --host 127.0.0.1 --port 8080
```

### Test the System:

```bash
# Test API endpoints
python test_api.py

# Test ML training
python test_model_training.py

# Test feature engineering
python test_feature_engineering.py
```

## 📊 System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PyQuotex API  │───▶│  Data Collection │───▶│   MongoDB Atlas │
└─────────────────┘    │     Service      │    └─────────────────┘
                       └──────────────────┘             │
                                                        │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend/     │◄───│  Prediction API  │◄───│   ML Models     │
│   External Apps │    │    (FastAPI)     │    │ (RF/XGB/LGB)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🎯 What Happens When You Run It

### **Data Collection Service:**
1. 🔌 Connects to PyQuotex with your credentials
2. 📊 Collects candle data every 60 seconds
3. 💾 Saves to MongoDB with technical indicators
4. 🔄 Runs continuously 24/7

### **Prediction API Service:**
1. 🚀 Starts FastAPI server on port 8000
2. 📚 Loads trained ML models
3. 🔮 Accepts prediction requests
4. ⚡ Returns predictions in <1 second

### **ML Training (Background):**
1. 🧠 Uses collected data to train models
2. 📈 Extracts 84 technical features
3. 🎯 Trains Random Forest, XGBoost, LightGBM
4. 💾 Saves best models automatically

## 🚨 Important Notes

### **Credentials Required:**
- You **MUST** set `QUOTEX_EMAIL` and `QUOTEX_PASSWORD` in `config.py`
- Use demo account for testing: `is_demo=True` in data service

### **MongoDB:**
- Already configured for MongoDB Atlas
- Connection string is in `config.py`
- No additional setup needed

### **First Run:**
- System will create sample data if none exists
- ML models train automatically when enough data available
- API works immediately with existing trained models

## 🔍 Monitoring & Logs

### **Check Status:**
```bash
# API status
curl http://localhost:8000/status

# Database stats  
curl http://localhost:8000/database/stats

# Available models
curl http://localhost:8000/models
```

### **Logs:**
- Console output shows real-time activity
- Data service logs to `logs/data_service_YYYYMMDD.log`
- API logs to console

## 🛠️ Troubleshooting

### **"No models available"**
- Run: `python test_model_training.py` to train models
- Or wait for automatic training (needs 1000+ candles)

### **"Connection failed"**
- Check PyQuotex credentials in `config.py`
- Verify internet connection
- Try demo account first

### **"MongoDB connection failed"**
- MongoDB Atlas connection is pre-configured
- Check internet connection
- Verify MongoDB Atlas cluster is running

### **API not responding**
- Check if port 8000 is available
- Try different port: `python main.py --port 9000`
- Check firewall settings

## 🎉 Success Indicators

✅ **Data Collection Working:**
```
📊 Collection successful: 4 candles collected
📈 EURUSD OTC: up | O:1.23456 C:1.23467 | Change: +0.00011
📊 Database: 1247 total candles
```

✅ **API Working:**
```
🌐 Prediction API: http://0.0.0.0:8000
📚 API Documentation: http://0.0.0.0:8000/docs
✅ Prediction made: up (0.847 confidence)
```

✅ **Models Training:**
```
✅ random_forest training completed - Accuracy: 0.6500
✅ xgboost training completed - Accuracy: 0.5500
💾 Model saved: random_forest_EURUSD_OTC_20250806_082517
```

## 🚀 Next Steps

1. **Let it run** for a few hours to collect real data
2. **Visit API docs** at http://localhost:8000/docs
3. **Make predictions** via API calls
4. **Integrate with frontend** or trading systems
5. **Monitor performance** and retrain models as needed

**You now have a complete real-time trading prediction system!** 🎯 