#!/usr/bin/env python3
"""
Data Collection Microservice
Collects real-time market data from PyQuotex and stores in MongoDB
"""

import asyncio
import logging
import sys
import signal
import resource
from datetime import datetime, timedelta
from pathlib import Path
import os
import argparse
import json
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Add parent directories to path
current_dir = Path(__file__).parent
backend_dir = current_dir.parent.parent
sys.path.append(str(backend_dir))

from data_collection.collector import DataCollector
from database.mongodb_models import MongoDBManager, CandleData
from config import QUOTEX_EMAIL, QUOTEX_PASSWORD, DEFAULT_TRADING_PAIRS
# Use microservice-specific collection settings
from microservices.data_collection_service.config import (
    HISTORICAL_DATA_DAYS as DC_HISTORICAL_DATA_DAYS,
    DATA_COLLECTION_INTERVAL as DC_COLLECTION_INTERVAL,
    DEFAULT_TIMEFRAME as DC_DEFAULT_TIMEFRAME,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service readiness flag - set to True after initialize_service() completes
service_ready = False

# Define lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize service and start data collection
    global mongodb_manager, data_service_running

    logger.info("🚀 Starting Data Collection Service...")
    asyncio.create_task(initialize_service())

    # Stop event for tick streaming graceful shutdown
    tick_stop_event = asyncio.Event()

    # Auto-start data collection if configured
    if os.environ.get("AUTO_START_DATA_COLLECTION", "true").lower() == "true":
        logger.info("🔄 Auto-starting data collection...")
        # Ensure the run loop actually starts
        data_service_running = True
        asyncio.create_task(run_data_service())
        # Start tick streaming in parallel
        asyncio.create_task(run_tick_streaming(tick_stop_event))

    # Start periodic WebSocket cleanup task
    async def ws_cleanup_loop():
        while True:
            await asyncio.sleep(60)
            await manager.cleanup_stale_connections()

    asyncio.create_task(ws_cleanup_loop())

    yield

    # Shutdown: signal tick streaming to stop
    tick_stop_event.set()

    # Shutdown: Stop data collection and disconnect from MongoDB
    logger.info("🛑 Shutting down Data Collection Service...")
    await stop_service()

    # Disconnect from MongoDB
    if mongodb_manager and mongodb_manager.is_connected:
        logger.info("🔌 Disconnecting from MongoDB...")
        mongodb_manager.disconnect()
        logger.info("✅ MongoDB disconnected")

# Create FastAPI app
app = FastAPI(
    title="OTC Predictor Data Collection Service",
    description="Collects real-time market data from PyQuotex",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    MAX_CONNECTIONS = 100

    def __init__(self):
        self.active_connections = []
        self.subscriptions = {}

    async def connect(self, websocket: WebSocket):
        # Reject if at capacity
        if len(self.active_connections) >= self.MAX_CONNECTIONS:
            logger.warning(f"WebSocket connection rejected: at capacity ({self.MAX_CONNECTIONS})")
            await websocket.close(code=1013)  # Try Again Later
            return
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
        logger.info(f"📡 WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info(f"📡 WebSocket client disconnected. Active connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"❌ Error sending WebSocket message: {str(e)}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict, trading_pair: str = None):
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                # Check if client is subscribed to this trading pair
                if trading_pair and trading_pair not in self.subscriptions.get(connection, []):
                    continue

                await connection.send_json(message)
            except Exception as e:
                logger.error(f"❌ WebSocket broadcast error: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def cleanup_stale_connections(self):
        """Ping all connections and remove dead ones"""
        dead = []
        for conn in self.active_connections:
            try:
                await asyncio.wait_for(conn.send_json({"type": "ping"}), timeout=5)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)
        if dead:
            logger.info(f"Cleaned up {len(dead)} stale WebSocket connections")

# Create connection manager
manager = ConnectionManager()

# Global services
mongodb_manager = None
data_collector = None
data_service_running = False

class ContinuousDataService:
    """
    Continuous data collection service optimized for USD/BRL(OTC)
    """
    
    def __init__(self, email: str = None, password: str = None):
        # Configuration
        self.email = email or QUOTEX_EMAIL
        self.password = password or QUOTEX_PASSWORD
        self.collection_interval = DC_COLLECTION_INTERVAL  # seconds
        self.timeframe = DC_DEFAULT_TIMEFRAME  # seconds per candle
        self.max_reconnect_attempts = 10  # Increased reconnect attempts
        self.reconnect_delay = 15  # Reduced delay between reconnection attempts (seconds)
        self.historical_data_days = DC_HISTORICAL_DATA_DAYS  # Backfill N days of historical data on startup
        
        # Priority pair settings
        self.is_optimized_for_usd_brl = True
        # Use API-style name for priority to keep everything consistent
        self.priority_pair = "BRLUSD_otc"  # Priority pair for data collection
        self.data_quality_checks = True  # Enable data quality checks
        self.retry_on_error = True  # Retry data collection on error
        self.max_retries = 3  # Maximum number of retries
        
        # Service state
        self.collector = None
        self.mongodb = None
        self.is_running = False
        self.should_stop = False
        
        # Statistics
        self.stats = {
            'service_started': None,
            'uptime_seconds': 0,
            'total_collections': 0,
            'successful_collections': 0,
            'failed_collections': 0,
            'reconnection_attempts': 0,
            'last_collection': None,
            'usd_brl_collections': 0,  # Track USD/BRL specific collections
            'data_quality_issues': 0,   # Track data quality issues
            'retries': 0                # Track retry attempts
        }
    
    async def initialize(self) -> bool:
        """Initialize the service"""
        
        logger.info("🚀 Initializing Continuous Data Service...")
        
        # Validate credentials
        if not self.email or not self.password:
            logger.error("❌ Missing PyQuotex credentials. Set QUOTEX_EMAIL and QUOTEX_PASSWORD in config.py")
            return False
        
        # Initialize MongoDB connection
        logger.info("🔌 Connecting to MongoDB...")
        self.mongodb = mongodb_manager
        if not self.mongodb.is_connected:
            logger.error("❌ MongoDB not connected")
            return False
        
        logger.info("✅ MongoDB connection verified")
        
        # Initialize data collector with the existing MongoDB connection
        self.collector = DataCollector(
            email=self.email,
            password=self.password,
            is_demo=True,  # Use demo account for safety
            db=self.mongodb  # Pass the existing MongoDB connection
        )
        
        logger.info("✅ DataCollector initialized with existing MongoDB connection")
        
        # Ensure timeframe is set to 1 minute
        self.collector.timeframe = self.timeframe  # 60 seconds = 1 minute
        
        # Update trading pairs from config using shared normalization utilities
        # Accepts aliases and converts to API asset form, e.g., 'USDBRL_otc'
        from shared.pairs import to_api_asset
        self.collector.trading_pairs = [to_api_asset(pair) for pair in DEFAULT_TRADING_PAIRS]
        
        logger.info(f"📊 Configured trading pairs in database: {DEFAULT_TRADING_PAIRS}")
        logger.info(f"📊 Configured trading pairs for PyQuotex: {self.collector.trading_pairs}")
        
        return True
    
    async def connect_to_pyquotex(self) -> bool:
        """Connect to PyQuotex with retry logic"""
        
        for attempt in range(self.max_reconnect_attempts):
            logger.info(f"🔌 Connecting to PyQuotex (attempt {attempt + 1}/{self.max_reconnect_attempts})...")
            
            try:
                # Attempt to connect to PyQuotex
                connect_result, message = await self.collector.connect()
                
                if connect_result:
                    logger.info("✅ Connected to PyQuotex successfully")
                    self.stats['reconnection_attempts'] = 0
                    
                    # Check which pairs are actually available
                    try:
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
                            logger.warning("⚠️ None of the configured pairs were found in the available pairs list")
                            logger.info(f"📊 Continuing with configured pairs: {self.collector.trading_pairs}")
                    except Exception as e:
                        logger.error(f"❌ Error getting available pairs: {str(e)}")
                        # Continue even if we can't get available pairs
                    
                    # Successfully connected and processed pairs
                    return True
                else:
                    logger.error(f"❌ Failed to connect to PyQuotex: {message}")
            except Exception as e:
                logger.error(f"❌ Connection error (attempt {attempt + 1}): {str(e)}")
            
            # If we get here, the connection attempt failed
            if attempt < self.max_reconnect_attempts - 1:
                logger.info(f"⏳ Waiting {self.reconnect_delay}s before retry...")
                await asyncio.sleep(self.reconnect_delay)
        
        # All attempts failed
        logger.error("❌ Failed to connect to PyQuotex after all attempts")
        self.stats['reconnection_attempts'] += 1
        return False
    
    async def collect_data_cycle(self) -> bool:
        """Execute one data collection cycle - Optimized for USD/BRL(OTC)"""
        
        max_retries = self.max_retries
        retry_count = 0
        success = False
        
        # Use iterative approach instead of recursion to prevent stack overflow
        while retry_count <= max_retries and not success:
            try:
                if retry_count > 0:
                    logger.info(f"🔄 Retry attempt {retry_count}/{max_retries}...")
                    await asyncio.sleep(5)  # Short delay before retry
                else:
                    logger.info("📊 Starting optimized data collection cycle...")
                
                cycle_start = datetime.now()
                
                # Check connection
                if not self.collector.is_connected:
                    logger.warning("⚠️ PyQuotex connection lost. Reconnecting...")
                    if not await self.connect_to_pyquotex():
                        retry_count += 1
                        self.stats['retries'] += 1
                        continue
                
                # Prioritize priority pair collection
                if self.is_optimized_for_usd_brl:
                    # First collect priority pair specifically
                    usd_brl_candles = await self.collect_priority_pair()
                    
                    if usd_brl_candles:
                        self.stats['usd_brl_collections'] += 1
                        logger.info(f"✅ {self.priority_pair} collection successful: {len(usd_brl_candles)} candles")
                        
                        # Perform data quality checks for USD/BRL(OTC)
                        if self.data_quality_checks:
                            for candle in usd_brl_candles:
                                if not self.check_data_quality(candle):
                                    self.stats['data_quality_issues'] += 1
                                
                        # Broadcast priority pair candles via WebSocket
                        for candle in usd_brl_candles:
                            # Log candle details with enhanced information
                            logger.info(f"  📈 {candle.trading_pair}: {candle.direction} | "
                                      f"O:{candle.open:.5f} C:{candle.close:.5f} H:{candle.high:.5f} L:{candle.low:.5f} | "
                                      f"Change: {candle.change:+.5f}")
                            
                            # Broadcast to WebSocket clients
                            await broadcast_market_update(candle)
                
                # Track if we already collected something via the priority step
                had_priority_success = bool(self.is_optimized_for_usd_brl and 'usd_brl_candles' in locals() and usd_brl_candles)
                
                # Collect data for all configured assets EXCEPT the priority pair to avoid duplicates
                # Normalize priority to API-style for comparison
                priority_api = self.priority_pair
                if not priority_api.lower().endswith("_otc"):
                    priority_api = f"{priority_api.replace('(OTC)', '').replace('/', '')}_otc"

                candles = []
                for asset in self.collector.trading_pairs:
                    if asset == priority_api:
                        continue
                    try:
                        asset_candles = await self.collector.collect_candle_data(asset)
                        for candle in asset_candles:
                            candle_id = await self.mongodb.save_candle(candle)
                            candle._id = candle_id
                            candles.append(candle)
                            logger.info(f"💾 Saved {asset} candle to MongoDB (ID: {candle_id})")
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"❌ Error collecting {asset}: {str(e)}")
                        continue
                
                if candles or had_priority_success:
                    self.stats['successful_collections'] += 1
                    self.stats['last_collection'] = datetime.now()
                    total_count = len(candles) + (len(usd_brl_candles) if had_priority_success else 0)
                    logger.info(f"✅ Collection successful: {total_count} candles collected")

                    # Broadcast each candle via WebSocket (except the priority pair which was already broadcast)
                    for candle in candles:
                        if self.is_optimized_for_usd_brl and candle.trading_pair == priority_api:
                            continue
                        logger.info(f"  📈 {candle.trading_pair}: {candle.direction} | "
                                    f"O:{candle.open:.5f} C:{candle.close:.5f} | "
                                    f"Change: {candle.change:+.5f}")
                        await broadcast_market_update(candle)

                    # Get database stats
                    db_stats = await self.mongodb.get_stats()
                    logger.info(f"📊 Database: {db_stats['candles']['count']} total candles")
                    success = True
                    break
                else:
                    logger.warning("⚠️ No candles collected this cycle")
                    if self.retry_on_error:
                        retry_count += 1
                        self.stats['retries'] += 1
                    else:
                        break
                    
            except Exception as e:
                logger.error(f"❌ Data collection error: {str(e)}")
                self.stats['failed_collections'] += 1
                
                if self.retry_on_error:
                    retry_count += 1
                    self.stats['retries'] += 1
                else:
                    break
        
        # Update total collections counter regardless of success
        self.stats['total_collections'] += 1
        return success
            
    async def collect_priority_pair(self) -> list:
        """Collect data specifically for the priority pair (USD/BRL)"""
        try:
            logger.info(f"🔍 Collecting data for priority pair: {self.priority_pair}")
            
            # Extract the base pair by removing '(OTC)' and the '/'
            base_pair = self.priority_pair.replace('(OTC)', '').replace('/', '')
            
            # Collect data for the specific pair
            candles = await self.collector.collect_asset(base_pair)
            
            if candles:
                logger.info(f"✅ Collected {len(candles)} candles for {self.priority_pair}")
                return candles
            else:
                logger.warning(f"⚠️ No candles collected for {self.priority_pair}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error collecting priority pair data: {str(e)}")
            return []
            
    def check_data_quality(self, candle) -> bool:
        """Check data quality for a candle"""
        try:
            # Basic sanity checks
            if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
                logger.warning(f"⚠️ Invalid price values in candle: {candle.trading_pair}")
                return False
                
            # Check for unrealistic price movements
            price_range = abs(candle.high - candle.low)
            avg_price = (candle.open + candle.close) / 2
            if price_range > avg_price * 0.1:  # More than 10% range in a single candle
                logger.warning(f"⚠️ Suspicious price range in candle: {candle.trading_pair}, range: {price_range:.5f}")
                return False
                
            # Check for OHLC consistency
            if candle.low > candle.open or candle.low > candle.close:
                logger.warning(f"⚠️ Low price inconsistency in candle: {candle.trading_pair}")
                return False
                
            if candle.high < candle.open or candle.high < candle.close:
                logger.warning(f"⚠️ High price inconsistency in candle: {candle.trading_pair}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"❌ Error in data quality check: {str(e)}")
            return False
    
    async def run_continuous_collection(self):
        """Main continuous collection loop - Optimized for USD/BRL(OTC)"""
        
        logger.info("🔄 Starting optimized continuous data collection for USD/BRL(OTC)...")
        self.is_running = True
        self.stats['service_started'] = datetime.now()
        
        # Initial connection with retry logic
        connection_attempts = 0
        max_initial_attempts = 5
        
        while connection_attempts < max_initial_attempts:
            try:
                connection_attempts += 1
                logger.info(f"🔄 Initial connection attempt {connection_attempts}/{max_initial_attempts}")
                
                if await self.connect_to_pyquotex():
                    logger.info("✅ Initial connection successful")
                    break
                else:
                    logger.warning(f"⚠️ Initial connection failed, retrying in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
            except Exception as e:
                logger.error(f"❌ Error during initial connection: {str(e)}")
                await asyncio.sleep(self.reconnect_delay)
        
        if connection_attempts >= max_initial_attempts:
            logger.error("❌ Failed all initial connection attempts. Service will continue running but in limited mode.")
            # Don't return - instead continue with limited functionality
        
        # Collect historical data on startup if enabled
        if self.is_optimized_for_usd_brl and self.historical_data_days > 0:
            await self.collect_historical_data()
        
        # Track last successful collection time for watchdog
        last_ping_time = datetime.now()
        reconnect_threshold = 180  # Force reconnect if no successful collection for 3 minutes
        hard_watchdog_threshold = 600  # Hard reset if no success for 10 minutes
        ping_failures = 0  # Count consecutive failures to react faster
        
        try:
            while not self.should_stop:
                cycle_start = datetime.now()
                
                # Check if we need to send a ping or force reconnect
                time_since_last_ping = (datetime.now() - last_ping_time).total_seconds()
                
                # If no successful collection for a while, proactively reconnect
                if ping_failures >= 3:
                    logger.warning(f"⚠️ {ping_failures} consecutive ping failures. Proactively reconnecting...")
                    try:
                        if self.collector and self.collector.client:
                            await self.collector.disconnect(close_db=False)
                        if await self.connect_to_pyquotex():
                            logger.info("✅ Proactive reconnection successful")
                            last_ping_time = datetime.now()
                            ping_failures = 0
                        else:
                            logger.error("❌ Proactive reconnection failed")
                    except Exception as e:
                        logger.error(f"❌ Proactive reconnection error: {str(e)}")
                
                # Force reconnect if we haven't had a successful ping in a while
                if time_since_last_ping >= reconnect_threshold:
                    logger.warning(f"⚠️ No successful ping for {time_since_last_ping:.1f}s. Forcing reconnection...")
                    try:
                        # Disconnect first
                        if self.collector and self.collector.client:
                            await self.collector.disconnect(close_db=False)
                        
                        # Then reconnect
                        if await self.connect_to_pyquotex():
                            logger.info("✅ Reconnection successful")
                            last_ping_time = datetime.now()
                            ping_failures = 0
                        else:
                            logger.error("❌ Reconnection failed")
                    except Exception as e:
                        logger.error(f"❌ Reconnection error: {str(e)}")

                # Hard watchdog: if still no ping for a prolonged period, perform hard reset of collector
                if time_since_last_ping >= hard_watchdog_threshold:
                    logger.error(f"🧭 Watchdog: No successful ping for {time_since_last_ping:.1f}s. Performing hard reset of client and connection...")
                    try:
                        if self.collector:
                            try:
                                await self.collector.disconnect(close_db=False)
                            except Exception:
                                pass
                            # Recreate the collector instance to clear any internal stuck state
                            from data_collection.collector import DataCollector
                            self.collector = DataCollector(email=self.email, password=self.password, is_demo=True, db=self.mongodb)
                            self.collector.trading_pairs = [self.priority_pair]
                            self.collector.timeframe = self.timeframe
                        # Attempt to reconnect end-to-end
                        if await self.connect_to_pyquotex():
                            logger.info("✅ Hard reset reconnection successful")
                            last_ping_time = datetime.now()
                            ping_failures = 0
                        else:
                            logger.critical("Hard reset failed. Exiting for container restart.")
                            sys.exit(1)
                    except Exception as e:
                        logger.critical(f"Hard reset error: {e}. Exiting for container restart.")
                        sys.exit(1)
                
                # Align collection to 3 seconds after the next minute boundary
                # This guarantees exactly 1 collection per candle, timed after candle close
                now = datetime.now()
                next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
                wait_until = next_minute + timedelta(seconds=3)  # 3s after candle close
                sleep_seconds = (wait_until - now).total_seconds()
                logger.info(f"⏱️ Waiting {sleep_seconds:.1f}s until next minute boundary + 3s...")
                # Interruptible sleep in 2s chunks
                while sleep_seconds > 0 and not self.should_stop:
                    await asyncio.sleep(min(2, sleep_seconds))
                    sleep_seconds -= 2

                # Execute collection cycle
                success = await self.collect_data_cycle()
                
                # Collection success is the liveness signal (replaces standalone ping)
                if success:
                    last_ping_time = datetime.now()
                    ping_failures = 0
                    # Auto-detect and fill any data gaps
                    await self.detect_and_fill_gaps()
                else:
                    ping_failures += 1
                
                # Update uptime
                if self.stats['service_started']:
                    self.stats['uptime_seconds'] = (datetime.now() - self.stats['service_started']).total_seconds()
                
                # Log statistics more frequently for USD/BRL(OTC)
                if self.is_optimized_for_usd_brl:
                    if self.stats['total_collections'] % 5 == 0:  # Every 5 cycles
                        self.log_statistics()
                else:
                    if self.stats['total_collections'] % 10 == 0:  # Every 10 cycles
                        self.log_statistics()
                
                # No separate sleep needed — minute-boundary alignment at top of loop handles timing
                
        except Exception as e:
            logger.error(f"❌ Critical service error: {str(e)}")
        finally:
            await self.shutdown()
            
    async def detect_and_fill_gaps(self):
        """Detect gaps in candle data and auto-repair by backfilling missing candles"""
        try:
            latest = await self.mongodb.get_candles(trading_pair=self.priority_pair, limit=1)
            if not latest:
                return
            gap_seconds = (datetime.now() - latest[0]["timestamp"]).total_seconds()
            if gap_seconds > 120:  # More than 2 minutes behind
                gap_days = max(1, int(gap_seconds / 86400) + 1)
                logger.warning(f"Gap detected: {gap_seconds:.0f}s behind. Backfilling {gap_days} day(s)...")
                candles = await self.collector.get_historical_candles(
                    asset=self.priority_pair, days=gap_days, timeframe=self.timeframe
                )
                if candles:
                    saved = await self.collector.process_historical_candles(candles, self.priority_pair)
                    logger.info(f"Gap fill complete: {saved} candles backfilled")
        except Exception as e:
            logger.error(f"Error in gap detection: {e}")

    async def collect_historical_data(self):
        """Collect historical data for USD/BRL(OTC)"""
        try:
            # Feature flag to quickly disable historical backfill if it interferes with other services
            if os.environ.get("ENABLE_HISTORICAL_BACKFILL", "true").lower() != "true":
                logger.info("⏭️ Historical backfill disabled via ENABLE_HISTORICAL_BACKFILL=false")
                return
            # Determine missing window by looking at latest stored candle
            now_ts = datetime.now()
            latest = []
            try:
                latest = await self.mongodb.get_candles(
                    trading_pair=self.priority_pair,
                    limit=1
                )
            except Exception as e:
                logger.warning(f"⚠️ Could not query latest candle: {e}")

            latest_ts = None
            if latest:
                latest_ts = latest[0].get("timestamp")

            # Compute how many days are actually missing
            missing_days = self.historical_data_days
            if latest_ts:
                delta_sec = max(0, int((now_ts - latest_ts).total_seconds()))
                missing_days = (delta_sec + 86399) // 86400  # ceil to days

            if missing_days <= 0:
                logger.info(f"✅ Historical data up-to-date for {self.priority_pair}; skipping backfill")
            else:
                logger.info(f"📚 Collecting {missing_days} missing day(s) of historical data for {self.priority_pair}...")

                # Use priority pair directly (already API-style, e.g., BRLUSD_otc)
                base_pair = self.priority_pair

                # Attempt to collect historical data for missing window only (forward gap fill)
                if hasattr(self.collector, 'get_historical_candles'):
                    historical_candles = await self.collector.get_historical_candles(
                        asset=base_pair,
                        days=missing_days,
                        timeframe=self.timeframe
                    )
                    if historical_candles and len(historical_candles) > 0:
                        logger.info(f"✅ Collected {len(historical_candles)} historical candles for {self.priority_pair}")
                        if hasattr(self.collector, 'process_historical_candles'):
                            await self.collector.process_historical_candles(historical_candles, base_pair)
                    else:
                        logger.warning(f"⚠️ No historical data collected for {self.priority_pair}")
                else:
                    logger.warning("⚠️ Historical data collection not supported by collector")

            # After forward gap fill, ensure we have at least historical_data_days of total history
            # Find the OLDEST candle for THIS trading pair and timeframe (not global oldest)
            try:
                cursor = self.mongodb.db.candles.find({
                    "trading_pair": self.priority_pair,
                    "period": self.timeframe
                }).sort("timestamp", 1).limit(1)
                docs = await cursor.to_list(length=1)
                oldest_ts = docs[0]["timestamp"] if docs else None
            except Exception as e:
                logger.warning(f"⚠️ Could not query oldest candle for {self.priority_pair}: {e}")
                oldest_ts = None

            if oldest_ts:
                desired_start = now_ts - timedelta(days=self.historical_data_days)
                if oldest_ts > desired_start:
                    # Need to go further back from the current oldest boundary (single-shot)
                    need_seconds = int((oldest_ts - desired_start).total_seconds())
                    additional_days = max(1, (need_seconds + 86399) // 86400)
                    logger.info(f"📚 Extending history by ~{additional_days} day(s) prior to oldest {oldest_ts.isoformat()} for {self.priority_pair}")
                    if hasattr(self.collector, 'get_historical_candles'):
                        try:
                            more_candles = await self.collector.get_historical_candles(
                                asset=self.priority_pair,
                                days=additional_days,
                                timeframe=self.timeframe,
                                end_from_time=int(oldest_ts.timestamp())
                            )
                            if more_candles:
                                logger.info(f"✅ Collected {len(more_candles)} additional older candles for {self.priority_pair}")
                                if hasattr(self.collector, 'process_historical_candles'):
                                    await self.collector.process_historical_candles(more_candles, self.priority_pair)
                        except Exception as ee:
                            logger.warning(f"⚠️ Failed to collect additional older history: {ee}")
            else:
                logger.info("ℹ️ No oldest timestamp available; skipping early extension step")

        except Exception as e:
            logger.error(f"❌ Error collecting historical data: {str(e)}")
            # Continue with real-time collection even if historical collection fails
    
    def log_statistics(self):
        """Log service statistics - Enhanced for USD/BRL(OTC) with memory monitoring"""

        uptime_hours = self.stats['uptime_seconds'] / 3600
        success_rate = (self.stats['successful_collections'] / max(1, self.stats['total_collections'])) * 100

        # Memory monitoring via resource.getrusage()
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss is in bytes on Linux, kilobytes on macOS
        rss_mb = usage.ru_maxrss / (1024 * 1024) if sys.platform == 'linux' else usage.ru_maxrss / 1024

        logger.info("📊 Service Statistics:")
        logger.info(f"  Uptime: {uptime_hours:.2f} hours")
        logger.info(f"  Collections: {self.stats['total_collections']} total, {self.stats['successful_collections']} successful")
        logger.info(f"  Success rate: {success_rate:.1f}%")
        logger.info(f"  Reconnections: {self.stats['reconnection_attempts']}")
        logger.info(f"  Memory RSS: {rss_mb:.1f} MB")

        # USD/BRL(OTC) specific statistics
        if self.is_optimized_for_usd_brl:
            usd_brl_rate = (self.stats['usd_brl_collections'] / max(1, self.stats['total_collections'])) * 100
            logger.info(f"  USD/BRL(OTC) collections: {self.stats['usd_brl_collections']} ({usd_brl_rate:.1f}%)")
            logger.info(f"  Data quality issues: {self.stats['data_quality_issues']}")
            logger.info(f"  Retry attempts: {self.stats['retries']}")

        if self.stats['last_collection']:
            minutes_ago = (datetime.now() - self.stats['last_collection']).total_seconds() / 60
            logger.info(f"  Last collection: {minutes_ago:.1f} minutes ago")

        # Memory guard: exit if RSS exceeds 450MB for container restart
        if rss_mb > 450:
            logger.critical(f"Memory usage {rss_mb:.1f} MB exceeds 450 MB limit. Exiting for container restart.")
            sys.exit(1)

        # Database statistics (if available)
        try:
            if self.mongodb and hasattr(self.mongodb, 'get_stats_sync'):
                db_stats = self.mongodb.get_stats_sync()
                if db_stats and 'candles' in db_stats:
                    logger.info(f"  Database: {db_stats['candles'].get('count', 0)} total candles")

                    # USD/BRL(OTC) specific count if available
                    if 'pair_counts' in db_stats and self.priority_pair in db_stats['pair_counts']:
                        logger.info(f"  USD/BRL(OTC) candles: {db_stats['pair_counts'][self.priority_pair]}")
        except Exception as e:
            pass  # Silently ignore database stats errors
    
    async def shutdown(self):
        """Graceful shutdown"""
        
        logger.info("🛑 Shutting down Continuous Data Service...")
        self.is_running = False
        
        # Disconnect from PyQuotex
        if self.collector:
            await self.collector.disconnect()
        
        # Log final statistics
        self.log_statistics()
        
        logger.info("✅ Service shutdown complete")
    
    def get_status(self):
        """Get current service status"""
        
        return {
            'is_running': self.is_running,
            'is_connected': self.collector.is_connected if self.collector else False,
            'stats': self.stats.copy(),
            'trading_pairs': self.collector.trading_pairs if self.collector else [],
            'collection_interval': self.collection_interval
        }

# Global data service instance
data_service = None

# API routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OTC Predictor Data Collection Service",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global mongodb_manager, data_service, service_ready

    if not service_ready:
        return {
            "status": "starting",
            "timestamp": datetime.now().isoformat(),
            "service": "data_collection",
            "mongodb_connected": False,
            "data_service_running": False
        }

    mongo_connected = mongodb_manager.is_connected if mongodb_manager else False
    status = "healthy" if mongo_connected else "unhealthy"

    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "service": "data_collection",
        "mongodb_connected": mongo_connected,
        "data_service_running": data_service.is_running if data_service else False
    }

@app.get("/status")
async def get_status():
    """Get service status"""
    global data_service
    
    if not data_service:
        return {
            "status": "not_initialized",
            "timestamp": datetime.now().isoformat()
        }
    
    return {
        "status": "running" if data_service.is_running else "stopped",
        "timestamp": datetime.now().isoformat(),
        **data_service.get_status()
    }

@app.post("/start")
async def start_service():
    """Start data collection service"""
    global data_service, data_service_running
    
    if data_service_running:
        return {"status": "already_running"}
    
    # Start data collection in background task
    data_service_running = True
    asyncio.create_task(run_data_service())
    
    return {"status": "starting"}

@app.post("/stop")
async def stop_service():
    """Stop data collection service"""
    global data_service, data_service_running
    
    if not data_service_running:
        return {"status": "not_running"}
    
    if data_service:
        data_service.should_stop = True
    
    data_service_running = False
    
    return {"status": "stopping"}

@app.get("/trading-pairs")
async def get_trading_pairs():
    """Get configured trading pairs"""
    return {
        "trading_pairs": DEFAULT_TRADING_PAIRS,
        "count": len(DEFAULT_TRADING_PAIRS)
    }

@app.get("/candles/{trading_pair:path}")
async def get_candles(trading_pair: str, limit: int = 50):
    """Get latest candles for a trading pair"""
    global mongodb_manager
    
    try:
        # Get latest candles from MongoDB
        candles = await mongodb_manager.get_latest_candles(trading_pair=trading_pair, limit=limit)
        
        if not candles:
            return {
                "trading_pair": trading_pair,
                "candles": [],
                "count": 0
            }
        
        # Format candles for response
        candle_data = []
        for candle in candles:
            candle_data.append({
                "timestamp": candle.timestamp.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": getattr(candle, 'volume', 0),
                "direction": candle.direction
            })
        
        return {
            "trading_pair": trading_pair,
            "candles": candle_data,
            "count": len(candle_data)
        }
    
    except Exception as e:
        logger.error(f"❌ Error getting candles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving candles: {str(e)}")

# WebSocket endpoint for live market data
@app.websocket("/ws/market-data")
async def websocket_market_data(websocket: WebSocket):
    """WebSocket endpoint for live market data"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for client messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "subscribe":
                trading_pair = message.get("trading_pair")
                logger.info(f"📡 WebSocket subscription request for: {trading_pair}")
                
                if trading_pair and websocket in manager.subscriptions:
                    if trading_pair not in manager.subscriptions[websocket]:
                        manager.subscriptions[websocket].append(trading_pair)
                    logger.info(f"✅ Client subscribed to {trading_pair}")
                    
                    # Send latest candle for this pair
                    await send_latest_candle(websocket, trading_pair)
                    
            elif message.get("action") == "get_historical":
                trading_pair = message.get("trading_pair")
                limit = message.get("limit", 50)
                logger.info(f"📚 WebSocket historical data request: {trading_pair}, limit: {limit}")
                await send_historical_data(websocket, trading_pair, limit)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"❌ WebSocket market-data error: {str(e)}")
    finally:
        manager.disconnect(websocket)

async def send_latest_candle(websocket: WebSocket, trading_pair: str):
    """Send latest candle for a trading pair"""
    global mongodb_manager
    
    try:
        # Get latest candle from MongoDB
        candles = await mongodb_manager.get_latest_candles(trading_pair=trading_pair, limit=1)
        
        if candles:
            candle = candles[0]
            
            # Send candle data
            candle_data = {
                "type": "candle_data",
                "trading_pair": trading_pair,
                "timestamp": candle.timestamp.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": getattr(candle, 'volume', 0)
            }
            
            await manager.send_personal_message(candle_data, websocket)
            logger.info(f"📡 Sent latest candle for {trading_pair}")
        else:
            logger.warning(f"⚠️ No candles found for {trading_pair}")
    except Exception as e:
        logger.error(f"❌ Error sending latest candle: {str(e)}")

async def send_historical_data(websocket: WebSocket, trading_pair: str, limit: int = 50):
    """Send historical candle data"""
    global mongodb_manager
    
    try:
        # Get historical candles from MongoDB
        candles = await mongodb_manager.get_latest_candles(trading_pair=trading_pair, limit=limit)
        
        if candles:
            historical_data = {
                "type": "historical_data",
                "trading_pair": trading_pair,
                "candles": [
                    {
                        "timestamp": candle.timestamp.isoformat(),
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": getattr(candle, 'volume', 0)
                    }
                    for candle in reversed(candles)  # Reverse to get chronological order
                ]
            }
            
            await manager.send_personal_message(historical_data, websocket)
            logger.info(f"📡 Sent historical data for {trading_pair}: {len(historical_data['candles'])} candles")
        else:
            logger.warning(f"⚠️ No historical data found for {trading_pair}")
            # Send empty data response
            empty_data = {
                "type": "historical_data",
                "trading_pair": trading_pair,
                "candles": []
            }
            await manager.send_personal_message(empty_data, websocket)
    except Exception as e:
        logger.error(f"❌ Error sending historical data: {str(e)}")

async def broadcast_market_update(candle_data: CandleData):
    """Broadcast new market data to all connected WebSocket clients"""
    try:
        trading_pair = candle_data.trading_pair
        
        # Candle data message
        candle_message = {
            "type": "candle_data",
            "trading_pair": trading_pair,
            "timestamp": candle_data.timestamp.isoformat(),
            "open": candle_data.open,
            "high": candle_data.high,
            "low": candle_data.low,
            "close": candle_data.close,
            "volume": getattr(candle_data, 'volume', 0)
        }
        
        # Broadcast to subscribed clients
        await manager.broadcast(candle_message, trading_pair)
        
        logger.info(f"📡 Broadcasted {trading_pair} update to WebSocket clients")
        
    except Exception as e:
        logger.error(f"❌ Error broadcasting market update: {str(e)}")

async def run_data_service():
    """Run the data collection service with auto-restart watchdog"""
    global data_service, data_service_running

    restart_attempt = 0
    max_backoff = 60
    max_consecutive_restarts = 10
    last_stable_time = datetime.now()
    stable_threshold = 300  # 5 minutes of stable operation resets counter

    while data_service_running:
        try:
            # Initialize data service
            data_service = ContinuousDataService()
            if not await data_service.initialize():
                logger.error("❌ Failed to initialize data service")
                break

            # Run continuous collection
            await data_service.run_continuous_collection()

            # If we ran for more than stable_threshold, reset restart counter
            if data_service.stats.get('uptime_seconds', 0) >= stable_threshold:
                restart_attempt = 0
                last_stable_time = datetime.now()

            # If loop exits normally (should_stop), break if stop requested
            if data_service.should_stop:
                break

        except Exception as e:
            logger.error(f"❌ Data service error: {str(e)}")
        finally:
            # If we are still marked running, sleep with backoff and restart
            if data_service_running and (not data_service or not data_service.should_stop):
                restart_attempt += 1

                # Exit if too many consecutive restarts without stable operation
                if restart_attempt > max_consecutive_restarts:
                    logger.critical(
                        f"Exceeded {max_consecutive_restarts} consecutive restarts without "
                        f"{stable_threshold}s of stable operation. Exiting for container restart."
                    )
                    sys.exit(1)

                backoff = min(max_backoff, 2 * restart_attempt)
                logger.warning(f"🔁 Restarting data service in {backoff}s (attempt {restart_attempt}/{max_consecutive_restarts})...")
                await asyncio.sleep(backoff)
                continue
            else:
                break

    data_service_running = False
    logger.info("🛑 Data service stopped")

async def run_tick_streaming(stop_event: asyncio.Event):
    """Stream real-time price ticks and broadcast via WebSocket.
    Purely additive — if this fails, batch pipeline is unaffected."""
    global data_service

    logger.info("📡 Tick streaming task started — waiting for collector to be connected...")

    # Wait until data_service and its collector are connected
    while not stop_event.is_set():
        if data_service and data_service.collector and data_service.collector.is_connected:
            break
        await asyncio.sleep(2)

    if stop_event.is_set():
        return

    priority_pair = data_service.priority_pair
    collector = data_service.collector
    logger.info(f"📡 Starting tick stream for {priority_pair}")

    while not stop_event.is_set():
        try:
            # Resolve asset for subscription (same logic as collect_candle_data)
            asset_to_use = priority_pair
            try:
                from shared.pairs import to_api_asset
                asset_to_use = to_api_asset(priority_pair) or priority_pair
            except Exception:
                pass

            try:
                asset_name, _ = await collector.client.get_available_asset(asset_to_use, force_open=True)
                if asset_name:
                    asset_to_use = asset_name
            except Exception:
                pass

            async for tick in collector.stream_realtime_ticks(asset_to_use, stop_event):
                if stop_event.is_set():
                    break
                tick_message = {
                    "type": "price_tick",
                    "trading_pair": priority_pair,
                    "price": tick["price"],
                    "timestamp": tick["timestamp"],
                }
                await manager.broadcast(tick_message, priority_pair)

        except Exception as e:
            logger.error(f"❌ Tick streaming error: {e}")

        if not stop_event.is_set():
            logger.info("📡 Tick stream ended — retrying in 5s...")
            await asyncio.sleep(5)

    logger.info("📡 Tick streaming task stopped")


async def initialize_service():
    """Initialize the service"""
    global mongodb_manager, service_ready

    # Initialize MongoDB connection
    mongodb_uri = os.environ.get("MONGODB_URI", "")
    if not mongodb_uri:
        logger.warning("⚠️ MONGODB_URI not set. Database features will be unavailable.")
    else:
        logger.info(f"Using MongoDB URI: {mongodb_uri[:30]}...")
    mongodb_manager = MongoDBManager(uri=mongodb_uri)
    if not await mongodb_manager.connect():
        logger.error("❌ Failed to connect to MongoDB")
        return False

    logger.info("✅ MongoDB connected successfully")
    service_ready = True
    return True

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    
    def signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}. Initiating graceful shutdown...")
        global data_service, data_service_running
        
        if data_service:
            data_service.should_stop = True
        
        data_service_running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

# Setup signal handlers for graceful shutdown
setup_signal_handlers()

def run_service(host: str = "0.0.0.0", port: int = 5008, reload: bool = False):
    """Run the data collection service"""
    print("🚀 OTC Predictor - Data Collection Service")
    print("=" * 50)
    print(f"🌐 API: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print("-" * 50)
    
    uvicorn.run("main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OTC Predictor Data Collection Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '5008')), help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    args = parser.parse_args()
    
    run_service(host=args.host, port=args.port, reload=args.reload)
