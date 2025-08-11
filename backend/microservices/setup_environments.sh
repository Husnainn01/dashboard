#!/bin/bash
# Setup script for OTC Predictor microservices virtual environments

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== OTC Predictor Microservices Environment Setup ===${NC}"
echo

# Base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Services to set up
SERVICES=("data_collection_service" "ml_training_service" "prediction_service" "api_gateway")

# Function to create a virtual environment for a service
create_venv() {
    local service=$1
    echo -e "${YELLOW}Setting up environment for ${service}...${NC}"
    
    # Create virtual environment
    echo "Creating virtual environment..."
    python3 -m venv "${service}/venv"
    
    # Activate virtual environment and install dependencies
    echo "Installing dependencies..."
    source "${service}/venv/bin/activate"
    pip install --upgrade pip
    pip install -r "${service}/requirements.txt"
    
    # Deactivate virtual environment
    deactivate
    
    echo -e "${GREEN}✓ ${service} environment setup complete${NC}"
    echo
}

# Create virtual environments for each service
for service in "${SERVICES[@]}"; do
    if [ -d "$service" ]; then
        create_venv "$service"
    else
        echo -e "${RED}Error: ${service} directory not found${NC}"
    fi
done

echo -e "${GREEN}=== All environments setup complete ===${NC}"
echo
echo "To activate an environment, run:"
echo "  source <service_directory>/venv/bin/activate"
echo
echo "To run a service (after activating its environment):"
echo "  cd <service_directory>"
echo "  python main.py"
echo
echo "Or use the main.py script with the --architecture microservices flag"
