#!/usr/bin/env python3
"""
OTC Predictor Main Service
Orchestrates both monolithic and microservices architectures
"""

import asyncio
import logging
import sys
import signal
import multiprocessing as mp
from datetime import datetime
from pathlib import Path
import os
import argparse

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_monolithic_mode(args):
    """Run the original monolithic mode"""
    from services.data_service import ContinuousDataService
    from services.prediction_api import run_api_server
    from services.ml_prediction_service import run_ml_service
    from config import QUOTEX_EMAIL, QUOTEX_PASSWORD
    
    class OTCPredictorOrchestrator:
        """
        Main service orchestrator for OTC Predictor (Monolithic Mode)
        """
        
        def __init__(self):
            self.data_service = None
            self.api_process = None
            self.ml_process = None
            self.is_running = False
            self.should_stop = False
            
            # Setup signal handlers
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
        
        def signal_handler(self, signum, frame):
            """Handle shutdown signals"""
            logger.info(f"🛑 Received signal {signum}. Initiating shutdown...")
            self.should_stop = True
        
        async def start_data_service(self):
            """Start the continuous data collection service"""
            
            logger.info("🚀 Starting Data Collection Service...")
            
            # Initialize data service
            self.data_service = ContinuousDataService()
            
            if not await self.data_service.initialize():
                logger.error("❌ Failed to initialize data service")
                return False
            
            # Start continuous collection in background
            asyncio.create_task(self.data_service.run_continuous_collection())
            logger.info("✅ Data Collection Service started")
            
            return True
        
        def start_api_service(self, host: str = "0.0.0.0", port: int = 5001):
            """Start the prediction API service in a separate process"""
            
            logger.info("🚀 Starting Prediction API Service...")
            
            # Use a module-level function instead of nested function
            self.api_process = mp.Process(
                target=run_api_server, 
                args=(host, port, False),  # host, port, reload
                daemon=False
            )
            self.api_process.start()
            
            logger.info(f"✅ Prediction API Service started on http://{host}:{port}")
            return True
            
        def start_ml_service(self, host: str = "0.0.0.0", port: int = 6008):
            """Start the ML prediction service in a separate process"""
            
            logger.info("🚀 Starting ML Prediction Service...")
            
            # Use a module-level function
            self.ml_process = mp.Process(
                target=run_ml_service,
                args=(host, port, False),  # host, port, reload
                daemon=False
            )
            self.ml_process.start()
            
            logger.info(f"✅ ML Prediction Service started on http://{host}:{port}")
            return True
        
        async def run_services(self, enable_data_service: bool = True, 
                              enable_api_service: bool = True,
                              enable_ml_service: bool = False,  # ML service disabled by default
                              api_host: str = "0.0.0.0", 
                              api_port: int = 5001,
                              ml_host: str = "0.0.0.0",
                              ml_port: int = 6008):
            """Run both services"""
            
            logger.info("🚀 Starting OTC Predictor Services (Monolithic Mode)")
            logger.info("=" * 60)
            
            self.is_running = True
            services_started = []
            
            try:
                # Start data collection service
                if enable_data_service:
                    if await self.start_data_service():
                        services_started.append("Data Collection")
                    else:
                        logger.error("❌ Failed to start data service")
                        return
                
                # Start API service
                if enable_api_service:
                    if self.start_api_service(api_host, api_port):
                        services_started.append("Prediction API")
                    else:
                        logger.error("❌ Failed to start API service")
                        return
                
                # Start ML service
                if enable_ml_service:
                    if self.start_ml_service(ml_host, ml_port):
                        services_started.append("ML Prediction Service")
                    else:
                        logger.error("❌ Failed to start ML service")
                        return
                
                logger.info(f"✅ Services started: {', '.join(services_started)}")
                logger.info("-" * 60)
                
                if enable_data_service:
                    logger.info("📊 Data Collection: Running continuously")
                if enable_api_service:
                    logger.info(f"🌐 Prediction API: http://{api_host}:{api_port}")
                    logger.info(f"📚 API Documentation: http://{api_host}:{api_port}/docs")
                if enable_ml_service:
                    logger.info(f"🔮 ML Prediction Service: http://{ml_host}:{ml_port}")
                    logger.info(f"📚 ML API Documentation: http://{ml_host}:{ml_port}/docs")
                
                logger.info("Press Ctrl+C to stop all services")
                logger.info("-" * 60)
                
                # Keep running until stopped
                while not self.should_stop:
                    await asyncio.sleep(1)
                    
                    # Check if API process is still alive
                    if enable_api_service and self.api_process and not self.api_process.is_alive():
                        logger.error("❌ API service process died unexpectedly")
                        break
                    
                    # Check if ML process is still alive
                    if enable_ml_service and self.ml_process and not self.ml_process.is_alive():
                        logger.error("❌ ML service process died unexpectedly")
                        break
            
            except Exception as e:
                logger.error(f"❌ Service error: {str(e)}")
            finally:
                await self.shutdown()
        
        async def shutdown(self):
            """Shutdown all services gracefully"""
            
            logger.info("🛑 Shutting down OTC Predictor Services...")
            self.is_running = False
            
            # Shutdown data service
            if self.data_service:
                await self.data_service.shutdown()
                logger.info("✅ Data service stopped")
            
            # Shutdown API service
            if self.api_process and self.api_process.is_alive():
                logger.info("🛑 Stopping API service...")
                self.api_process.terminate()
                self.api_process.join(timeout=10)
                
                if self.api_process.is_alive():
                    logger.warning("⚠️ Force killing API process...")
                    self.api_process.kill()
                
                logger.info("✅ API service stopped")
                
            # Shutdown ML service
            if self.ml_process and self.ml_process.is_alive():
                logger.info("🛑 Stopping ML service...")
                self.ml_process.terminate()
                self.ml_process.join(timeout=10)
                
                if self.ml_process.is_alive():
                    logger.warning("⚠️ Force killing ML process...")
                    self.ml_process.kill()
                
                logger.info("✅ ML service stopped")
            
            logger.info("✅ All services stopped successfully")

    def validate_credentials():
        """Validate PyQuotex credentials"""
        
        email = os.getenv('QUOTEX_EMAIL') or QUOTEX_EMAIL
        password = os.getenv('QUOTEX_PASSWORD') or QUOTEX_PASSWORD
        
        if not email or not password:
            logger.error("❌ Missing PyQuotex credentials")
            logger.error("Please set QUOTEX_EMAIL and QUOTEX_PASSWORD in config.py or environment variables")
            return False
        
        logger.info(f"✅ Credentials configured for: {email}")
        return True

    async def main():
        """Main entry point for monolithic mode"""
        
        # Validate credentials for data service
        enable_data_service = args.mode in ['all', 'data'] and not args.no_data
        enable_api_service = args.mode in ['all', 'api'] and not args.no_api
        enable_ml_service = args.mode in ['all', 'ml'] or args.ml
        
        if enable_data_service:
            if not validate_credentials():
                logger.error("❌ Cannot start data service without credentials")
                if args.mode == 'data':
                    return
                enable_data_service = False
                logger.info("⚠️ Running in API-only mode")
        
        if not enable_data_service and not enable_api_service and not enable_ml_service:
            logger.error("❌ No services enabled")
            return
        
        # Create and run orchestrator
        orchestrator = OTCPredictorOrchestrator()
        
        try:
            await orchestrator.run_services(
                enable_data_service=enable_data_service,
                enable_api_service=enable_api_service,
                enable_ml_service=enable_ml_service,
                api_host=args.host,
                api_port=args.port,
                ml_host=args.host,
                ml_port=args.ml_port
            )
        except KeyboardInterrupt:
            logger.info("⏹️ Interrupted by user")
        except Exception as e:
            logger.error(f"❌ Fatal error: {str(e)}")

    def run_data_only():
        """Run data collection service only"""
        
        print("📊 OTC Predictor - Data Collection Only")
        print("=" * 50)
        
        async def data_main():
            if not validate_credentials():
                return
            
            service = ContinuousDataService()
            if await service.initialize():
                await service.run_continuous_collection()
        
        asyncio.run(data_main())

    def run_api_only():
        """Run API service only"""
        
        print("🌐 OTC Predictor - API Only")
        print("=" * 50)
        
        run_api_server(host=args.host, port=args.port, reload=False)

    def run_ml_only():
        """Run ML service only"""
        
        print("🔮 OTC Predictor - ML Prediction Service Only")
        print("=" * 50)
        
        run_ml_service(host=args.host, port=args.ml_port, reload=False)

    # Run based on mode
    if args.mode == 'data':
        run_data_only()
    elif args.mode == 'api':
        run_api_only()
    elif args.mode == 'ml':
        run_ml_only()
    else:
        asyncio.run(main())

def run_microservices_mode(args):
    """Run the new microservices mode"""
    import uvicorn
    import subprocess
    import time
    
    # Define service configurations
    services = {
        "api_gateway": {
            "module": "microservices.api_gateway.main",
            "host": args.host,
            "port": 5000,
            "reload": args.reload,
            "enabled": True
        },
        "data_collection": {
            "module": "microservices.data_collection_service.main",
            "host": args.host,
            "port": 5001,
            "reload": args.reload,
            "enabled": args.mode in ['all', 'data'] and not args.no_data
        },
        "ml_training": {
            "module": "microservices.ml_training_service.main",
            "host": args.host,
            "port": 5002,
            "reload": args.reload,
            "enabled": args.mode in ['all', 'ml'] or args.ml
        },
        "prediction": {
            "module": "microservices.prediction_service.main",
            "host": args.host,
            "port": 5003,
            "reload": args.reload,
            "enabled": args.mode in ['all', 'api'] and not args.no_api
        }
    }
    
    # Override ports if specified
    if args.port != 5001:
        services["data_collection"]["port"] = args.port
    
    if args.ml_port != 6008:
        services["ml_training"]["port"] = args.ml_port
    
    # Start enabled services
    processes = {}
    try:
        logger.info("🚀 Starting OTC Predictor Services (Microservices Mode)")
        logger.info("=" * 60)
        
        for name, config in services.items():
            if config["enabled"]:
                logger.info(f"🚀 Starting {name.replace('_', ' ').title()} Service...")
                
                # Create command
                cmd = [
                    sys.executable, "-m", "uvicorn", 
                    config["module"] + ":app",
                    "--host", config["host"],
                    "--port", str(config["port"]),
                ]
                
                if config["reload"]:
                    cmd.append("--reload")
                
                # Start process
                processes[name] = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                logger.info(f"✅ {name.replace('_', ' ').title()} Service started on http://{config['host']}:{config['port']}")
                
                # Wait a bit to ensure service starts
                time.sleep(1)
        
        logger.info("-" * 60)
        logger.info("✅ All enabled services started")
        logger.info("Press Ctrl+C to stop all services")
        logger.info("-" * 60)
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
            # Check if any processes have died
            for name, process in list(processes.items()):
                if process.poll() is not None:
                    returncode = process.poll()
                    stdout, stderr = process.communicate()
                    logger.error(f"❌ {name.replace('_', ' ').title()} Service died unexpectedly (code {returncode})")
                    if stderr:
                        logger.error(f"Error output: {stderr}")
                    del processes[name]
            
            # Exit if all processes have died
            if not processes:
                logger.error("❌ All services have died")
                break
    
    except KeyboardInterrupt:
        logger.info("⏹️ Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Error running microservices: {str(e)}")
    finally:
        # Terminate all processes
        for name, process in processes.items():
            logger.info(f"🛑 Stopping {name.replace('_', ' ').title()} Service...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"⚠️ Force killing {name.replace('_', ' ').title()} Service...")
                process.kill()
        
        logger.info("✅ All services stopped")

def run_docker_compose_mode(args):
    """Run using docker-compose"""
    import subprocess
    
    logger.info("🚀 Starting OTC Predictor Services (Docker Compose Mode)")
    logger.info("=" * 60)
    
    try:
        # Build and start services
        logger.info("🏗️ Building and starting services...")
        subprocess.run(
            ["docker-compose", "-f", "microservices/docker-compose.yml", "up", "--build", "-d"],
            check=True
        )
        
        logger.info("✅ Services started successfully")
        logger.info("Use 'docker-compose -f microservices/docker-compose.yml logs -f' to view logs")
        logger.info("Use 'docker-compose -f microservices/docker-compose.yml down' to stop services")
        logger.info("-" * 60)
        
        # Keep running until interrupted
        logger.info("Press Ctrl+C to exit (services will continue running)")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("⏹️ Exiting (services will continue running)")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Docker Compose error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OTC Predictor Service Orchestrator')
    parser.add_argument('--mode', choices=['all', 'data', 'api', 'ml'], default='all',
                       help='Service mode: all (all services), data (collection only), api (API only), ml (ML only)')
    parser.add_argument('--host', default='0.0.0.0', help='API host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5001, help='API port (default: 5001)')
    parser.add_argument('--ml-port', type=int, default=6008, help='ML service port (default: 6008)')
    parser.add_argument('--no-data', action='store_true', help='Disable data collection service')
    parser.add_argument('--no-api', action='store_true', help='Disable API service')
    parser.add_argument('--ml', action='store_true', help='Enable ML prediction service')
    parser.add_argument('--architecture', choices=['monolithic', 'microservices', 'docker'], default='monolithic',
                       help='Architecture to use: monolithic (original), microservices (separate services), docker (docker-compose)')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    
    args = parser.parse_args()
    
    # Print banner
    print("🤖 OTC Predictor - Trading Prediction System")
    print("=" * 60)
    print("🔮 Real-time ML predictions for OTC markets")
    print("📊 Continuous data collection from PyQuotex")
    print("🌐 REST API for predictions and model management")
    print("=" * 60)
    
    # Run based on selected architecture
    if args.architecture == 'monolithic':
        run_monolithic_mode(args)
    elif args.architecture == 'microservices':
        run_microservices_mode(args)
    elif args.architecture == 'docker':
        run_docker_compose_mode(args)