"""
Continuous Data Collection Service
Runs 24/7 to collect real-time market data from PyQuotex and store in MongoDB
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import json
import os

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from data_collection.collector import DataCollector
from database.mongodb_models import MongoDBManager, CandleData
from config import QUOTEX_EMAIL, QUOTEX_PASSWORD, DEFAULT_TRADING_PAIRS

logger = logging.getLogger(__name__)

class ContinuousDataService:
    """
    Continuous data collection service that runs in the background
    """
    
    def __init__(self, email: str = None, password: str = None):
        # Configuration
        self.email = email or QUOTEX_EMAIL
        self.password = password or QUOTEX_PASSWORD
        self.collection_interval = 60  # 1 minute (60 seconds) between collections
        self.timeframe = 60  # 1 minute timeframe (60 seconds)
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 30  # seconds
        
        # Service state
        self.collector: Optional[DataCollector] = None
        self.mongodb: Optional[MongoDBManager] = None
        self.is_running = False
        self.should_stop = False
        
        # WebSocket broadcasting
        self.websocket_broadcast_func = None
        
        # Statistics
        self.stats = {
            'service_started': None,
            'uptime_seconds': 0,
            'total_collections': 0,
            'successful_collections': 0,
            'failed_collections': 0,
            'reconnection_attempts': 0,
            'last_collection': None
        }
        
        # Setup logging and signal handlers
        self.setup_logging()
        self.setup_signal_handlers()
    
    def setup_logging(self):
        """Setup comprehensive logging"""
        
        # Create logs directory
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Configure logging
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # File handler
        log_file = logs_dir / f"data_service_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(log_format))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))
        
        # Configure logger
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        
        def signal_handler(signum, frame):
            logger.info(f"🛑 Received signal {signum}. Initiating graceful shutdown...")
            self.should_stop = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def initialize(self) -> bool:
        """Initialize the service"""
        
        logger.info("🚀 Initializing Continuous Data Service...")
        
        # Validate credentials
        if not self.email or not self.password:
            logger.error("❌ Missing PyQuotex credentials. Set QUOTEX_EMAIL and QUOTEX_PASSWORD in config.py")
            return False
        
        # Initialize MongoDB connection
        logger.info("🔌 Connecting to MongoDB...")
        self.mongodb = MongoDBManager()
        if not await self.mongodb.connect():
            logger.error("❌ Failed to connect to MongoDB")
            return False
        
        logger.info("✅ MongoDB connected successfully")
        
        # Initialize data collector
        self.collector = DataCollector(
            email=self.email,
            password=self.password,
            is_demo=True  # Use demo account for safety
        )
        
        # Ensure timeframe is set to 1 minute
        self.collector.timeframe = self.timeframe  # 60 seconds = 1 minute
        
        # Update trading pairs from config 
        # PyQuotex expects base pairs without OTC and without slashes
        # Convert 'USD/BRL(OTC)' to 'USDBRL'
        self.collector.trading_pairs = []
        for pair in DEFAULT_TRADING_PAIRS:
            # Extract the base pair by removing '(OTC)' and the '/'
            base_pair = pair.replace('(OTC)', '').replace('/', '')
            
            # Some PyQuotex assets might need _otc suffix
            # We'll try both formats later if needed
            self.collector.trading_pairs.append(base_pair)
        
        logger.info(f"📊 Configured trading pairs in database: {DEFAULT_TRADING_PAIRS}")
        logger.info(f"📊 Configured trading pairs for PyQuotex: {self.collector.trading_pairs}")
        
        return True
    
    async def connect_to_pyquotex(self) -> bool:
        """Connect to PyQuotex with retry logic"""
        
        for attempt in range(self.max_reconnect_attempts):
            try:
                logger.info(f"🔌 Connecting to PyQuotex (attempt {attempt + 1}/{self.max_reconnect_attempts})...")
                
                if await self.collector.connect():
                    logger.info("✅ Connected to PyQuotex successfully")
                    self.stats['reconnection_attempts'] = 0
                    
                    # Check which pairs are actually available
                    available_pairs = await self.collector.get_available_pairs()
                    logger.info(f"📊 Available pairs in PyQuotex: {available_pairs}")
                    
                    # Filter trading pairs to only include available ones
                    filtered_pairs = []
                    for pair in self.collector.trading_pairs:
                        if pair in available_pairs:
                            filtered_pairs.append(pair)
                        else:
                            logger.warning(f"⚠️ Trading pair not available in PyQuotex: {pair}")
                    
                    if filtered_pairs:
                        self.collector.trading_pairs = filtered_pairs
                        logger.info(f"📊 Using available trading pairs: {filtered_pairs}")
                    else:
                        # Keep trying with configured pairs even if they're not in the available list
                        # This is because the available pairs list might not be complete
                        logger.warning("⚠️ None of the configured pairs were found in the available pairs list")
                        logger.info(f"📊 Continuing with configured pairs: {self.collector.trading_pairs}")
                    
                    return True
                else:
                    logger.warning(f"⚠️ Connection attempt {attempt + 1} failed")
                    
            except Exception as e:
                logger.error(f"❌ Connection error (attempt {attempt + 1}): {str(e)}")
            
            if attempt < self.max_reconnect_attempts - 1:
                logger.info(f"⏳ Waiting {self.reconnect_delay}s before retry...")
                await asyncio.sleep(self.reconnect_delay)
        
        logger.error("❌ Failed to connect to PyQuotex after all attempts")
        self.stats['reconnection_attempts'] += 1
        return False
    
    async def collect_data_cycle(self) -> bool:
        """Execute one data collection cycle"""
        
        try:
            logger.info("📊 Starting data collection cycle...")
            cycle_start = datetime.now()
            
            # Check connection
            if not self.collector.is_connected:
                logger.warning("⚠️ PyQuotex connection lost. Reconnecting...")
                if not await self.connect_to_pyquotex():
                    return False
            
            # Collect data for all assets
            candles = await self.collector.collect_all_assets()
            
            if candles:
                self.stats['successful_collections'] += 1
                self.stats['last_collection'] = datetime.now()
                
                logger.info(f"✅ Collection successful: {len(candles)} candles collected")
                
                # Broadcast each candle via WebSocket
                for candle in candles:
                    # Log candle details
                    logger.info(f"  📈 {candle.trading_pair}: {candle.direction} | "
                              f"O:{candle.open:.5f} C:{candle.close:.5f} | "
                              f"Change: {candle.change:+.5f}")
                    
                    # Broadcast to WebSocket clients
                    if self.websocket_broadcast_func:
                        try:
                            await self.websocket_broadcast_func(candle)
                            logger.debug(f"📡 Broadcasted {candle.trading_pair} to WebSocket clients")
                        except Exception as ws_error:
                            logger.warning(f"⚠️ WebSocket broadcast failed for {candle.trading_pair}: {ws_error}")
                
                # Get database stats
                db_stats = await self.mongodb.get_stats()
                logger.info(f"📊 Database: {db_stats['candle_count']} total candles")
                
                return True
            else:
                logger.warning("⚠️ No candles collected this cycle")
                return False
                
        except Exception as e:
            logger.error(f"❌ Data collection error: {str(e)}")
            self.stats['failed_collections'] += 1
            return False
        finally:
            self.stats['total_collections'] += 1
    
    async def run_continuous_collection(self):
        """Main continuous collection loop"""
        
        logger.info("🔄 Starting continuous data collection...")
        self.is_running = True
        self.stats['service_started'] = datetime.now()
        
        # Initial connection
        if not await self.connect_to_pyquotex():
            logger.error("❌ Failed initial connection. Service cannot start.")
            return
        
        try:
            while not self.should_stop:
                cycle_start = datetime.now()
                
                # Execute collection cycle
                success = await self.collect_data_cycle()
                
                # Update uptime
                if self.stats['service_started']:
                    self.stats['uptime_seconds'] = (datetime.now() - self.stats['service_started']).total_seconds()
                
                # Log periodic statistics
                if self.stats['total_collections'] % 10 == 0:  # Every 10 cycles
                    self.log_statistics()
                
                # Calculate sleep time
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                sleep_time = max(0, self.collection_interval - cycle_duration)
                
                if sleep_time > 0:
                    logger.info(f"⏳ Next collection in {sleep_time:.1f}s...")
                    
                    # Sleep with periodic wake-ups to check stop signal
                    sleep_intervals = int(sleep_time / 5) + 1
                    for _ in range(sleep_intervals):
                        if self.should_stop:
                            break
                        await asyncio.sleep(min(5, sleep_time))
                        sleep_time -= 5
                        if sleep_time <= 0:
                            break
                
        except Exception as e:
            logger.error(f"❌ Critical service error: {str(e)}")
        finally:
            await self.shutdown()
    
    def log_statistics(self):
        """Log service statistics"""
        
        uptime_hours = self.stats['uptime_seconds'] / 3600
        success_rate = (self.stats['successful_collections'] / max(1, self.stats['total_collections'])) * 100
        
        logger.info("📊 Service Statistics:")
        logger.info(f"  🕐 Uptime: {uptime_hours:.2f} hours")
        logger.info(f"  📈 Collections: {self.stats['total_collections']} total, {self.stats['successful_collections']} successful")
        logger.info(f"  ✅ Success rate: {success_rate:.1f}%")
        logger.info(f"  🔄 Reconnections: {self.stats['reconnection_attempts']}")
        if self.stats['last_collection']:
            minutes_ago = (datetime.now() - self.stats['last_collection']).total_seconds() / 60
            logger.info(f"  ⏰ Last collection: {minutes_ago:.1f} minutes ago")
    
    async def shutdown(self):
        """Graceful shutdown"""
        
        logger.info("🛑 Shutting down Continuous Data Service...")
        self.is_running = False
        
        # Disconnect from PyQuotex
        if self.collector:
            await self.collector.disconnect()
        
        # Disconnect from MongoDB
        await self.mongodb.disconnect()
        
        # Log final statistics
        self.log_statistics()
        
        logger.info("✅ Service shutdown complete")
    
    def get_status(self) -> Dict:
        """Get current service status"""
        
        return {
            'is_running': self.is_running,
            'is_connected': self.collector.is_connected if self.collector else False,
            'stats': self.stats.copy(),
            'trading_pairs': self.collector.trading_pairs if self.collector else [],
            'collection_interval': self.collection_interval
        }

    def set_websocket_broadcaster(self, broadcast_func):
        """Set the WebSocket broadcast function from the API service"""
        self.websocket_broadcast_func = broadcast_func
        logger.info("📡 WebSocket broadcaster configured")


async def main():
    """Main entry point for running the service"""
    
    print("🚀 OTC Predictor - Continuous Data Collection Service")
    print("=" * 60)
    
    # Get credentials from environment or config
    email = os.getenv('QUOTEX_EMAIL') or QUOTEX_EMAIL
    password = os.getenv('QUOTEX_PASSWORD') or QUOTEX_PASSWORD
    
    if not email or not password:
        print("❌ Error: Missing PyQuotex credentials")
        print("Please set QUOTEX_EMAIL and QUOTEX_PASSWORD in config.py or environment variables")
        return
    
    # Initialize service
    service = ContinuousDataService(email=email, password=password)
    
    if not await service.initialize():
        print("❌ Failed to initialize service")
        return
    
    print("✅ Service initialized successfully")
    print(f"📊 Trading pairs: {', '.join(DEFAULT_TRADING_PAIRS)}")
    print(f"⏰ Collection interval: {service.collection_interval} seconds")
    print()
    print("Press Ctrl+C to stop the service gracefully")
    print("-" * 60)
    
    # Run the service
    await service.run_continuous_collection()


if __name__ == "__main__":
    asyncio.run(main()) 