# OTC Predictor Microservices Environment Setup

This guide explains how to set up virtual environments for each microservice in the OTC Predictor system.

## Option 1: Automated Setup

We've provided a script to automatically set up virtual environments for all microservices:

```bash
# Make the script executable
chmod +x setup_environments.sh

# Run the setup script
./setup_environments.sh
```

This will create a virtual environment for each microservice and install all required dependencies.

## Option 2: Manual Setup

If you prefer to set up environments manually, follow these steps for each microservice:

### Data Collection Service

```bash
# Create virtual environment
cd data_collection_service
python3 -m venv venv

# Activate environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Deactivate when done
deactivate
```

### ML Training Service

```bash
# Create virtual environment
cd ml_training_service
python3 -m venv venv

# Activate environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Deactivate when done
deactivate
```

### Prediction Service

```bash
# Create virtual environment
cd prediction_service
python3 -m venv venv

# Activate environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Deactivate when done
deactivate
```

### API Gateway

```bash
# Create virtual environment
cd api_gateway
python3 -m venv venv

# Activate environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Deactivate when done
deactivate
```

## Running Microservices

### Option 1: Using the Main Script

The main.py script in the backend directory can run all microservices:

```bash
# Run all microservices
python main.py --architecture microservices

# Run specific services
python main.py --architecture microservices --mode data  # Data collection only
python main.py --architecture microservices --mode api   # API only
python main.py --architecture microservices --mode ml    # ML only

# Run with auto-reload for development
python main.py --architecture microservices --reload
```

### Option 2: Running Individual Services

To run a specific service directly:

```bash
# Activate the service's virtual environment
cd microservices/data_collection_service
source venv/bin/activate

# Run the service
python main.py

# Deactivate when done
deactivate
```

## Docker Deployment

For Docker deployment, use:

```bash
# Run all services using Docker Compose
python main.py --architecture docker

# Or directly with Docker Compose
cd microservices
docker-compose up -d
```

## Troubleshooting

If you encounter package not found errors:

1. Make sure you've activated the correct virtual environment
2. Verify that all dependencies are installed: `pip list`
3. Try reinstalling the requirements: `pip install -r requirements.txt`

For TA-Lib installation issues:

- On Ubuntu: `sudo apt-get install build-essential ta-lib`
- On macOS: `brew install ta-lib`
- On Windows: Download and install from [TA-Lib binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib)
