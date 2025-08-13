# Railway Deployment Guide for OTC Predictor

## 🚀 Deployment Overview

This project uses a **microservices architecture** with 5 main services that need to be deployed separately on Railway.

## 📋 Services to Deploy

### 1. **Frontend Service** (Next.js)
- **Port**: 3000
- **Framework**: Next.js
- **Purpose**: User interface for trading dashboard

### 2. **API Gateway Service** (FastAPI)
- **Port**: 5000
- **Framework**: FastAPI
- **Purpose**: Central API gateway, WebSocket connections, service orchestration

### 3. **Data Collection Service** (Python)
- **Port**: 5001
- **Framework**: FastAPI
- **Purpose**: Collects market data from Quotex

### 4. **ML Training Service** (Python)
- **Port**: 5002
- **Framework**: FastAPI
- **Purpose**: Trains and manages ML models

### 5. **Prediction Service** (Python)
- **Port**: 5003
- **Framework**: FastAPI
- **Purpose**: Generates trading predictions

## 🗂️ Railway Project Structure

Create **5 separate Railway services** in your Railway project:

```
OTC-Predictor-Railway/
├── frontend-service/
├── api-gateway-service/
├── data-collection-service/
├── ml-training-service/
└── prediction-service/
```

## 📁 Required Files for Each Service

### Frontend Service
```
frontend/
├── package.json
├── next.config.js
├── Dockerfile (if needed)
└── [all frontend files]
```

### API Gateway Service
```
microservices/api_gateway/
├── main.py
├── config.py
├── requirements.txt
├── Dockerfile
└── [all API gateway files]
```

### Data Collection Service
```
microservices/data_collection_service/
├── main.py
├── config.py
├── requirements.txt
├── Dockerfile
└── [all data collection files]
```

### ML Training Service
```
microservices/ml_training_service/
├── main.py
├── config.py
├── requirements.txt
├── Dockerfile
└── [all ML training files]
```

### Prediction Service
```
microservices/prediction_service/
├── main.py
├── config.py
├── requirements.txt
├── Dockerfile
└── [all prediction files]
```

## 🔧 Shared Dependencies

Each service needs access to these shared modules:

```
backend/
├── config.py (shared configuration)
├── ml_models/ (shared ML utilities)
├── database/ (shared database models)
├── services/ (shared services)
└── requirements.txt (shared dependencies)
```

## 🌐 Environment Variables

### Frontend Service
```env
NEXT_PUBLIC_API_GATEWAY_URL=https://your-api-gateway-service.railway.app
NEXT_PUBLIC_WS_URL=wss://your-api-gateway-service.railway.app/ws
```

### API Gateway Service
```env
DATA_SERVICE_HOST=your-data-collection-service.railway.app
DATA_SERVICE_PORT=443
ML_SERVICE_HOST=your-ml-training-service.railway.app
ML_SERVICE_PORT=443
PREDICTION_SERVICE_HOST=your-prediction-service.railway.app
PREDICTION_SERVICE_PORT=443
MONGODB_URI=your-mongodb-connection-string
```

### Data Collection Service
```env
MONGODB_URI=your-mongodb-connection-string
QUOTEX_EMAIL=your-quotex-email
QUOTEX_PASSWORD=your-quotex-password
```

### ML Training Service
```env
MONGODB_URI=your-mongodb-connection-string
R2_ACCESS_KEY_ID=your-r2-access-key
R2_SECRET_ACCESS_KEY=your-r2-secret-key
R2_BUCKET_NAME=your-r2-bucket
R2_ENDPOINT_URL=your-r2-endpoint
```

### Prediction Service
```env
MONGODB_URI=your-mongodb-connection-string
R2_ACCESS_KEY_ID=your-r2-access-key
R2_SECRET_ACCESS_KEY=your-r2-secret-key
R2_BUCKET_NAME=your-r2-bucket
R2_ENDPOINT_URL=your-r2-endpoint
```

## 🐳 Dockerfile Updates Needed

Each service's Dockerfile needs to be updated to include shared dependencies:

### Example: API Gateway Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy shared dependencies first
COPY requirements.txt /app/requirements.txt
COPY config.py /app/
COPY ml_models/ /app/ml_models/
COPY database/ /app/database/
COPY services/ /app/services/

# Copy the specific service
COPY microservices/api_gateway/ /app/microservices/api_gateway/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose port
EXPOSE 5000

# Run the service
CMD ["python", "microservices/api_gateway/main.py"]
```

## 🚀 Deployment Steps

### Step 1: Create Railway Project
1. Go to Railway.app
2. Create new project
3. Add 5 services (one for each microservice)

### Step 2: Configure Each Service
1. **Frontend Service**: Connect to `frontend/` directory
2. **API Gateway**: Connect to `backend/microservices/api_gateway/` directory
3. **Data Collection**: Connect to `backend/microservices/data_collection_service/` directory
4. **ML Training**: Connect to `backend/microservices/ml_training_service/` directory
5. **Prediction**: Connect to `backend/microservices/prediction_service/` directory

### Step 3: Set Environment Variables
- Add all required environment variables for each service
- Use Railway's environment variable management

### Step 4: Deploy
- Deploy each service individually
- Monitor logs for any issues
- Update service URLs in environment variables

## 🔗 Service Communication

After deployment, services will communicate via HTTPS:

```
Frontend → API Gateway (HTTPS)
API Gateway → Data Collection (HTTPS)
API Gateway → ML Training (HTTPS)
API Gateway → Prediction (HTTPS)
```

## 📊 Monitoring

- Use Railway's built-in monitoring
- Check logs for each service
- Monitor resource usage
- Set up alerts for service failures

## 🔄 Updates

To update services:
1. Push changes to your repository
2. Railway will automatically redeploy
3. Update environment variables if needed
4. Test the updated services

## 🆘 Troubleshooting

### Common Issues:
1. **Port conflicts**: Ensure each service uses the correct port
2. **Environment variables**: Double-check all required variables are set
3. **Dependencies**: Ensure shared modules are properly copied
4. **Database connections**: Verify MongoDB connection strings
5. **Service URLs**: Update URLs after deployment

### Debug Steps:
1. Check Railway logs for each service
2. Verify environment variables are set correctly
3. Test service health endpoints
4. Check service-to-service communication
5. Verify database connectivity
