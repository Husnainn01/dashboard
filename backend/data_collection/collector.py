"""
Data Collection Module
Uses PyQuotex API to collect real-time market data and store in database
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import time
import json

# PyQuotex imports
from pyquotex.stable_api import Quotex

# Our database models
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from database.mongodb_models import MongoDBManager, CandleData

class DataCollector:
    """
    Collects market data from PyQuotex API and stores in database
    """
    
    def __init__(self, email: str, password: str, is_demo: bool = True, db: MongoDBManager = None):
        self.email = email
        self.password = password
        self.is_demo = is_demo
        self.session_id = str(uuid.uuid4())
        
        # PyQuotex client
        self.client: Optional[Quotex] = None
        self.is_connected = False
        
        # Data collection settings
        self.trading_pairs = []  # Will be populated from config
        self.timeframe = 60  # 1 minute candles (60 seconds)
        self.collection_interval = 60  # Collect every 60 seconds
        
        # Storage
        # Use provided MongoDB connection if available, otherwise create a new one
        self.db = db if db is not None else MongoDBManager(uri="mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net/otc-predictor")
        self.collected_candles = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def get_available_pairs(self) -> List[str]:
        """Get list of available trading pairs from PyQuotex"""
        try:
            if not self.is_connected:
                self.logger.error("❌ Not connected to PyQuotex")
                return []
            
            # Get available assets from PyQuotex
            try:
                assets = await self.client.get_all_assets()
                
                if not assets:
                    self.logger.warning("⚠️ No assets returned from PyQuotex")
                    return []
                    
                # Convert dictionary to list of asset names
                asset_names = list(assets.keys())
                self.logger.info(f"📊 Found {len(asset_names)} available assets in PyQuotex")
                return asset_names
                
            except AttributeError:
                # Fallback to get_all_asset_name which is synchronous
                self.logger.warning("⚠️ get_all_assets not available, trying get_all_asset_name")
                try:
                    asset_data = self.client.get_all_asset_name()
                    if asset_data:
                        # Extract just the asset names from the data
                        asset_names = [item[0] for item in asset_data]
                        self.logger.info(f"📊 Found {len(asset_names)} available assets using get_all_asset_name")
                        return asset_names
                except Exception as e:
                    self.logger.error(f"❌ Error with get_all_asset_name: {str(e)}")
                    
                return []
            
            # Log available assets for debugging
            self.logger.info(f"📊 Available assets in PyQuotex: {assets}")
            
            return assets
        except Exception as e:
            self.logger.error(f"❌ Error getting available pairs: {str(e)}")
            return []
    
    async def connect(self) -> bool:
        """Connect to PyQuotex API and MongoDB"""
        try:
            self.logger.info("🔌 Connecting to MongoDB...")
            
            # Make sure MongoDB URI is set correctly
            if not self.db.uri or "localhost" in self.db.uri:
                self.db.uri = "mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net/otc-predictor"
                self.logger.info(f"Updated MongoDB URI to: {self.db.uri}")
                
            # Connect to MongoDB first if not already connected
            if not self.db.is_connected:
                mongodb_connected = await self.db.connect()
                if not mongodb_connected:
                    self.logger.error("❌ Failed to connect to MongoDB")
                    return False
            else:
                self.logger.info("✅ Using existing MongoDB connection")
            
            self.logger.info("🔌 Connecting to PyQuotex...")
            
            # Initialize PyQuotex client with retry
            try:
                self.client = Quotex(
                    email=self.email,
                    password=self.password,
                    lang="en"  # English language
                )
                self.logger.info("✅ PyQuotex client initialized")
            except Exception as e:
                self.logger.error(f"❌ Error initializing PyQuotex client: {str(e)}")
                # Wait a moment and retry
                self.logger.info("🔄 Retrying PyQuotex client initialization...")
                await asyncio.sleep(3)
                self.client = Quotex(
                    email=self.email,
                    password=self.password,
                    lang="en"  # English language
                )
            
            # Monkey patch the Login class to use the correct domain
            from pyquotex.http.login import Login
            
            # Store original values
            original_base_url = Login.base_url
            original_https_base_url = Login.https_base_url
            
            # Patch Login class to use the correct domain
            Login.base_url = 'market-qx.pro'
            Login.https_base_url = f'https://market-qx.pro'
            
            try:
                # Now connect normally - the Login class will use the correct domain
                try:
                    try:
                        check_connect, message = await self.client.connect()
                    except SystemExit:
                        self.logger.error("❌ PyQuotex login attempted to exit the application")
                        return False, "Login failed with SystemExit"
                except json.JSONDecodeError as json_err:
                    self.logger.error(f"❌ JSON parsing error during connection: {str(json_err)}")
                    # Wait a moment and retry once
                    self.logger.info("🔄 Retrying connection after JSON error...")
                    await asyncio.sleep(3)
                    try:
                        check_connect, message = await self.client.connect()
                    except SystemExit:
                        self.logger.error("❌ PyQuotex login attempted to exit the application")
                        return False, "Login failed with SystemExit"
            finally:
                # Restore original values (good practice)
                Login.base_url = original_base_url
                Login.https_base_url = original_https_base_url
            
            if check_connect:
                self.is_connected = True
                self.logger.info(f"✅ Connected to PyQuotex: {message}")
                
                # Get account info with retry
                max_retries = 3
                retry_count = 0
                profile = None
                
                while retry_count < max_retries and not profile:
                    try:
                        profile = await self.client.get_profile()
                        if profile:
                            self.logger.info(f"👤 Account: {profile.nick_name}")
                            balance = profile.demo_balance if self.is_demo else profile.live_balance
                            self.logger.info(f"💰 Balance: {balance} {profile.currency_symbol}")
                            break
                    except json.JSONDecodeError as json_err:
                        retry_count += 1
                        self.logger.warning(f"⚠️ JSON error getting profile (attempt {retry_count}/{max_retries}): {str(json_err)}")
                        if retry_count < max_retries:
                            self.logger.info(f"🔄 Waiting 3s before retry...")
                            await asyncio.sleep(3)
                    except Exception as err:
                        self.logger.error(f"❌ Error getting profile: {str(err)}")
                        break  # Don't retry on non-JSON errors
                
                if retry_count == max_retries:
                    self.logger.warning(f"⚠️ Failed to get profile after {max_retries} attempts, continuing anyway")
                # Continue even if profile fetch fails
                
                return True, "Connected successfully"
            else:
                self.logger.error(f"❌ Failed to connect: {message}")
                return False, message
                
        except Exception as e:
            self.logger.error(f"❌ Connection error: {str(e)}")
            return False, str(e)
    
    async def disconnect(self):
        """Disconnect from PyQuotex and MongoDB"""
        if self.client and self.is_connected:
            await self.client.close()
            self.is_connected = False
            self.logger.info("🔌 Disconnected from PyQuotex")
        
        # Disconnect from MongoDB
        await self.db.disconnect()
    
    async def collect_candle_data(self, asset: str) -> Optional[CandleData]:
        """
        Collect current candle data for an asset using PyQuotex API
        """
        try:
            if not self.is_connected:
                self.logger.error("❌ Not connected to PyQuotex")
                return None
            
            self.logger.info(f"📊 Collecting candle data for {asset}...")
            
            # Get candles from PyQuotex API (following the example pattern)
            offset = 3600  # 1 hour of data in seconds
            period = self.timeframe  # 60 seconds
            end_from_time = time.time()
            
            # Try with the original asset name
            candles_data = None
            asset_to_use = asset
            
            try:
                self.logger.info(f"📊 Requesting candles for {asset_to_use} (period: {period}, offset: {offset})")
                
                # Add robust error handling around PyQuotex API calls
                try:
                    candles_data = await self.client.get_candles(asset_to_use, end_from_time, offset, period)
                except json.JSONDecodeError as json_err:
                    self.logger.error(f"❌ JSON parsing error for {asset_to_use}: {str(json_err)}")
                    self.logger.info(f"🔄 Reconnecting to PyQuotex after JSON error...")
                    # Try to reconnect and retry once
                    await self.connect()
                    await asyncio.sleep(2)  # Short delay before retry
                    candles_data = await self.client.get_candles(asset_to_use, end_from_time, offset, period)
                except Exception as api_err:
                    self.logger.error(f"❌ PyQuotex API error for {asset_to_use}: {str(api_err)}")
                    candles_data = None
                
                # If no data and asset doesn't have _otc suffix, try with it
                if (not candles_data or len(candles_data) == 0) and "_otc" not in asset_to_use.lower():
                    asset_to_use = f"{asset}_otc"
                    self.logger.info(f"📊 Trying with OTC suffix: {asset_to_use}")
                    try:
                        candles_data = await self.client.get_candles(asset_to_use, end_from_time, offset, period)
                    except (json.JSONDecodeError, Exception) as err:
                        self.logger.error(f"❌ Error getting candles for {asset_to_use}: {str(err)}")
                        candles_data = None
                    
                # Special case for USD/BRL - try BRLUSD_otc if USDBRL_otc doesn't work
                if (not candles_data or len(candles_data) == 0) and asset.upper() == "USDBRL":
                    asset_to_use = "BRLUSD_otc"
                    self.logger.info(f"📊 Trying inverse pair: {asset_to_use}")
                    try:
                        candles_data = await self.client.get_candles(asset_to_use, end_from_time, offset, period)
                    except (json.JSONDecodeError, Exception) as err:
                        self.logger.error(f"❌ Error getting candles for {asset_to_use}: {str(err)}")
                        candles_data = None
                
                if not candles_data:
                    self.logger.warning(f"⚠️ No candle data received for {asset_to_use} - returned None")
                    return None
                elif len(candles_data) == 0:
                    self.logger.warning(f"⚠️ Empty candle data for {asset_to_use} - returned empty list")
                    return None
                else:
                    self.logger.info(f"✅ Received {len(candles_data)} candles for {asset_to_use}")
            except Exception as e:
                self.logger.error(f"❌ Error getting candles for {asset_to_use}: {str(e)}")
                import traceback
                self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
                return None
            
            # Get the latest completed candle (second to last, as last might be incomplete)
            latest_candle = candles_data[-2] if len(candles_data) > 1 else candles_data[-1]
            
            # Handle different candle data formats
            if not latest_candle.get("open"):
                # Process candles if needed (following PyQuotex example)
                from pyquotex.utils.processor import process_candles
                processed_candles = process_candles(candles_data, period)
                if processed_candles and len(processed_candles) > 0:
                    latest_candle = processed_candles[-2] if len(processed_candles) > 1 else processed_candles[-1]
                else:
                    self.logger.warning(f"⚠️ Could not process candle data for {asset}")
                    return None
            
            # Create CandleData object with the new format: USD/BRL(OTC)
            # Convert USDBRL to USD/BRL(OTC)
            formatted_pair = ""
            
            # Special case for BRLUSD_otc (inverse of USDBRL)
            if asset_to_use.upper() == "BRLUSD_OTC":
                formatted_pair = "USD/BRL(OTC)"
                # For inverse pair, we need to invert the prices
                latest_candle['open'] = 1 / float(latest_candle.get('open', 1))
                latest_candle['high'] = 1 / float(latest_candle.get('low', 1))  # Note: high becomes low when inverted
                latest_candle['low'] = 1 / float(latest_candle.get('high', 1))  # Note: low becomes high when inverted
                latest_candle['close'] = 1 / float(latest_candle.get('close', 1))
                self.logger.info(f"📊 Inverted BRLUSD_otc prices for USD/BRL(OTC)")
            elif len(asset) == 6:  # Standard pairs like USDBRL
                formatted_pair = f"{asset[:3]}/{asset[3:]}(OTC)"
            else:
                # Handle other lengths if needed
                # Strip _otc suffix if present
                clean_asset = asset_to_use.replace("_otc", "")
                if len(clean_asset) == 6:
                    formatted_pair = f"{clean_asset[:3]}/{clean_asset[3:]}(OTC)"
                else:
                    formatted_pair = f"{asset}(OTC)"
                    self.logger.warning(f"⚠️ Unusual asset length: {asset}, formatted as {formatted_pair}")
            
            candle = CandleData(
                timestamp=datetime.fromtimestamp(latest_candle.get('time', time.time())),
                trading_pair=formatted_pair,
                open_price=float(latest_candle.get('open', 0)),
                high_price=float(latest_candle.get('high', latest_candle.get('max', 0))),
                low_price=float(latest_candle.get('low', latest_candle.get('min', 0))),
                close_price=float(latest_candle.get('close', 0)),
                volume=0,  # Default volume
                is_closed=True,
                is_validated=False,
                source='pyquotex_api'
            )
            
            self.logger.info(f"✅ Collected {asset}: {candle.direction} candle, change: {candle.change:.5f}")
            return candle
            
        except Exception as e:
            self.logger.error(f"❌ Error collecting candle for {asset}: {str(e)}")
            import traceback
            self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None
    
    async def collect_realtime_data(self, asset: str) -> Optional[Dict]:
        """
        Collect real-time price data for an asset
        """
        try:
            if not self.is_connected:
                return None
            
            # Subscribe to real-time data
            await self.client.subscribe_realtime_candle(asset, self.timeframe)
            
            # Wait a bit for data to arrive
            await asyncio.sleep(2)
            
            # Get real-time price data
            realtime_data = self.client.realtime_price.get(asset, [])
            
            if realtime_data:
                latest_price = realtime_data[-1] if isinstance(realtime_data, list) else realtime_data
                self.logger.info(f"📈 Real-time {asset}: {latest_price}")
                return latest_price
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error getting real-time data for {asset}: {str(e)}")
            return None
    
    async def collect_all_assets(self) -> List[CandleData]:
        """
        Collect candle data for all configured trading pairs
        """
        collected = []
        
        for asset in self.trading_pairs:
            try:
                candle = await self.collect_candle_data(asset)
                if candle:
                    # Save to MongoDB
                    candle_id = await self.db.save_candle(candle)
                    candle._id = candle_id
                    collected.append(candle)
                    
                    self.logger.info(f"💾 Saved {asset} candle to MongoDB (ID: {candle_id})")
                
                # Small delay between requests
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"❌ Error collecting {asset}: {str(e)}")
                continue
        
        return collected
        
    async def collect_asset(self, asset_name: str) -> List[CandleData]:
        """
        Collect data for a specific asset - Added to support microservices
        
        Args:
            asset_name: Name of the asset to collect
            
        Returns:
            List[CandleData]: List of collected candles as CandleData objects
        """
        try:
            self.logger.info(f"📊 Collecting data for {asset_name}...")
            
            candle = await self.collect_candle_data(asset_name)
            if candle:
                # Save to MongoDB if not already saved
                if not hasattr(candle, '_id') or not candle._id:
                    candle_id = await self.db.save_candle(candle)
                    candle._id = candle_id
                
                # Return the CandleData object directly
                return [candle]
            else:
                self.logger.warning(f"⚠️ No candle data returned for {asset_name}")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error collecting data for {asset_name}: {str(e)}")
            return []
    
    async def start_continuous_collection(self, duration_minutes: int = 60):
        """
        Start continuous data collection for specified duration
        """
        self.logger.info(f"🚀 Starting continuous data collection for {duration_minutes} minutes...")
        
        if not await self.connect():
            self.logger.error("❌ Failed to connect. Cannot start collection.")
            return
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        collection_count = 0
        
        try:
            while datetime.now() < end_time:
                collection_start = datetime.now()
                
                self.logger.info(f"📊 Collection cycle {collection_count + 1} started...")
                
                # Collect data for all assets
                candles = await self.collect_all_assets()
                
                if candles:
                    collection_count += 1
                    self.logger.info(f"✅ Cycle {collection_count}: Collected {len(candles)} candles")
                    
                    # Log some statistics
                    stats = await self.db.get_stats()
                    self.logger.info(f"📈 MongoDB stats: {stats['candle_count']} total candles")
                else:
                    self.logger.warning("⚠️ No candles collected this cycle")
                
                # Calculate next collection time
                collection_duration = (datetime.now() - collection_start).total_seconds()
                sleep_time = max(0, self.collection_interval - collection_duration)
                
                if sleep_time > 0:
                    self.logger.info(f"⏳ Waiting {sleep_time:.1f}s until next collection...")
                    await asyncio.sleep(sleep_time)
        
        except KeyboardInterrupt:
            self.logger.info("⏹️ Collection stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Collection error: {str(e)}")
        finally:
            await self.disconnect()
            
            # Final statistics
            final_stats = await self.db.get_stats()
            self.logger.info(f"🎯 Collection completed! Total candles: {final_stats['candle_count']}")
    
    async def collect_single_batch(self) -> List[CandleData]:
        """
        Collect a single batch of data (useful for testing)
        """
        self.logger.info("📊 Collecting single batch of data...")
        
        if not await self.connect():
            self.logger.error("❌ Failed to connect")
            return []
        
        try:
            candles = await self.collect_all_assets()
            return candles
        finally:
            await self.disconnect()
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about collected data"""
        return await self.db.get_stats()


# Example usage and testing
async def main():
    """Test the data collector"""
    
    # Demo credentials (replace with real ones)
    collector = DataCollector(
        email="your-email@example.com",  # Replace with your email
        password="your-password",         # Replace with your password
        is_demo=True                     # Use demo account
    )
    
    # Test single batch collection
    print("🧪 Testing single batch collection...")
    candles = await collector.collect_single_batch()
    
    if candles:
        print(f"✅ Successfully collected {len(candles)} candles!")
        for candle in candles:
            print(f"  📊 {candle.trading_pair}: {candle.direction} ({candle.change:+.5f})")
    else:
        print("❌ No candles collected")
    
    # Show database stats
    stats = collector.get_collection_stats()
    print(f"\n📈 Database Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())