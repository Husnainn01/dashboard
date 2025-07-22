# MongoDB Atlas Setup Guide

## 1. Database Configuration

Your MongoDB Atlas cluster will automatically create the database `otc-predictor` when the first data is stored.

### Connection String Format:
```
mongodb+srv://<username>:<password>@<cluster-name>.mongodb.net/otc-predictor
```

### Environment Variables
Create a `.env` file in the backend folder:

```bash
# MongoDB Atlas Connection
MONGO_URI=mongodb+srv://your-username:your-password@your-cluster.mongodb.net/otc-predictor

# Alternative names supported
MONGODB_URI=mongodb+srv://your-username:your-password@your-cluster.mongodb.net/otc-predictor

# Server Configuration
PORT=5001
NODE_ENV=development
FRONTEND_URL=http://localhost:3000
```

## 2. Database Collections

The application will automatically create these collections:

### `candledata` Collection
Stores extracted candle data from screen captures:
```json
{
  "timestamp": "2025-01-20T10:30:00.000Z",
  "tradingPair": "EUR/USD OTC",
  "timeframe": 60,
  "open": 1.23456,
  "high": 1.23567,
  "low": 1.23234,
  "close": 1.23445,
  "direction": "up",
  "change": -0.00011,
  "changePercent": -0.01,
  "captureData": {
    "screenshotPath": "/path/to/screenshot.png",
    "captureTimestamp": "2025-01-20T10:30:00.000Z",
    "extractionMethod": "tesseract",
    "confidenceScore": 85
  },
  "indicators": {
    "rsi": 65.2,
    "ema": 1.23400,
    "sma": 1.23380
  },
  "patternId": "pattern_abc123",
  "isValidated": false,
  "sessionId": "session-12345",
  "botVersion": "1.0.0",
  "createdAt": "2025-01-20T10:30:00.000Z",
  "updatedAt": "2025-01-20T10:30:00.000Z"
}
```

### `predictions` Collection
Stores ML predictions and their accuracy:
```json
{
  "timestamp": "2025-01-20T10:30:00.000Z",
  "tradingPair": "EUR/USD OTC",
  "direction": "up",
  "confidence": 74,
  "modelVersion": "1.0.0",
  "algorithmUsed": "pattern_matching",
  "inputCandles": ["ObjectId1", "ObjectId2", "ObjectId3"],
  "patternId": "pattern_abc123",
  "features": {
    "last5CandlesPattern": ["up", "down", "up", "down", "up"],
    "trendDirection": "bullish",
    "volatility": 0.002,
    "consecutiveSameDirection": 2,
    "timeOfDay": "10:30",
    "weekDay": "Monday"
  },
  "actualResult": {
    "direction": "up",
    "actualClose": 1.23445,
    "verifiedAt": "2025-01-20T10:31:00.000Z",
    "correct": true
  },
  "accuracy": 74,
  "sessionId": "session-12345",
  "isBacktest": false,
  "createdAt": "2025-01-20T10:30:00.000Z",
  "updatedAt": "2025-01-20T10:31:00.000Z"
}
```

## 3. Indexes Created Automatically

The application creates these indexes for optimal performance:

### CandleData Indexes:
- `{ timestamp: -1, tradingPair: 1 }` - For time-series queries
- `{ sessionId: 1 }` - For session-based filtering  
- `{ patternId: 1 }` - For pattern matching
- `{ createdAt: -1 }` - For recent data queries

### Prediction Indexes:
- `{ timestamp: -1, tradingPair: 1 }` - For time-series queries
- `{ sessionId: 1 }` - For session-based filtering
- `{ "actualResult.correct": 1 }` - For accuracy calculations
- `{ patternId: 1 }` - For pattern-based queries

## 4. Atlas Network Access

Make sure to whitelist your IP address in MongoDB Atlas:

1. Go to Network Access in your Atlas dashboard
2. Add your current IP address
3. For development, you can use `0.0.0.0/0` (allow all - not recommended for production)

## 5. Atlas Database User

Create a database user with read/write permissions:

1. Go to Database Access in your Atlas dashboard
2. Create a new user with "Read and write to any database" role
3. Use these credentials in your connection string

## 6. Testing Connection

Test your connection by starting the backend:

```bash
cd backend
npm install
node server.js
```

You should see:
```
✅ MongoDB connected successfully
Database: otc-predictor
Host: cluster0-shard-00-01.xxxxx.mongodb.net:27017
```

## 7. Viewing Data

You can view your data in several ways:

### MongoDB Atlas Web Interface
- Go to your cluster in Atlas dashboard
- Click "Browse Collections"
- Select `otc-predictor` database

### MongoDB Compass
- Download MongoDB Compass
- Connect using your Atlas connection string
- Browse collections visually

### Backend API Endpoints
- `GET /api/data/candles` - View captured candle data
- `GET /api/data/predictions` - View predictions
- `GET /api/data/stats` - View database statistics

## 8. Sample Data Flow

1. **Authentication**: User logs into Quotex via embedded iframe
2. **Start Bot**: Triggers `/api/data/start-capture` endpoint
3. **Screen Capture**: Service takes screenshots every 5 seconds
4. **Data Extraction**: Processes screenshots to extract OHLC data
5. **Database Storage**: Saves extracted data to `candledata` collection
6. **Pattern Analysis**: Analyzes patterns and stores predictions
7. **Frontend Display**: Shows real-time data and predictions

The database will grow automatically as the bot captures more data! 