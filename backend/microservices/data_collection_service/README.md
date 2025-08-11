# Data Collection Microservice

This microservice is responsible for collecting real-time market data from PyQuotex and storing it in MongoDB.

## Features

- Continuous data collection from PyQuotex
- WebSocket API for real-time market data streaming
- REST API for historical data and service management
- Automatic reconnection and error handling

## API Endpoints

### REST API

- `GET /` - Service information
- `GET /health` - Health check endpoint
- `GET /status` - Get service status and statistics
- `POST /start` - Start data collection
- `POST /stop` - Stop data collection
- `GET /trading-pairs` - Get configured trading pairs
- `GET /candles/{trading_pair}` - Get historical candles for a trading pair

### WebSocket API

- `/ws/market-data` - WebSocket endpoint for real-time market data
  - Subscribe to a trading pair: `{"action": "subscribe", "trading_pair": "USD/BRL(OTC)"}`
  - Get historical data: `{"action": "get_historical", "trading_pair": "USD/BRL(OTC)", "limit": 50}`

## Configuration

Configuration is loaded from the main backend config file. Key settings:

- `QUOTEX_EMAIL` - PyQuotex account email
- `QUOTEX_PASSWORD` - PyQuotex account password
- `DEFAULT_TRADING_PAIRS` - List of trading pairs to collect data for

## Running the Service

### Prerequisites

- MongoDB running and accessible
- PyQuotex credentials configured

### Start the Service

```bash
# From the microservice directory
python main.py

# With custom host and port
python main.py --host 0.0.0.0 --port 5001

# With auto-reload for development
python main.py --reload
```

## Docker Deployment

```bash
docker build -t otc-predictor-data-collection .
docker run -p 5001:5001 -e MONGODB_URI="mongodb://host.docker.internal:27017" otc-predictor-data-collection
```
