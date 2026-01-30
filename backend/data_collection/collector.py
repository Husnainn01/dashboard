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
import os

# PyQuotex imports
from pyquotex.stable_api import Quotex

# Our database models
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from database.mongodb_models import MongoDBManager, CandleData
from shared.pairs import to_api_asset

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
        self.last_domain_used: Optional[str] = None  # Track which base domain worked
        self.original_ws_urls = {}  # Store original WebSocket URLs
        
        # Storage
        # Use provided MongoDB connection if available, otherwise create a new one
        self.db = db if db is not None else MongoDBManager(uri=os.getenv('MONGODB_URI', ''))
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
            
            # Warn if MongoDB URI is not set
            if not self.db.uri:
                self.logger.warning("⚠️ MONGODB_URI is not configured")
                
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
            
            # Monkey patch the Login class and WebSocket URLs to try multiple base domains
            from pyquotex.http.login import Login
            import os
            # Prefer QUOTEX_BASE_DOMAINS (comma-separated). Fallback to QUOTEX_BASE_DOMAIN. Defaults: quotex.com,qxbroker.com
            domains_env = os.getenv('QUOTEX_BASE_DOMAINS')
            if domains_env:
                domains = [d.strip() for d in domains_env.split(',') if d.strip()]
            else:
                single = os.getenv('QUOTEX_BASE_DOMAIN')
                if single:
                    domains = [single.strip()]
                else:
                    domains = ['quotex.com', 'qxbroker.com']

            check_connect = False
            message = "No domains attempted"
            for base_domain in domains:
                # Store original values for each attempt
                original_base_url = Login.base_url
                original_https_base_url = Login.https_base_url
                
                # Patch Login for this attempt
                Login.base_url = base_domain
                Login.https_base_url = f'https://{base_domain}'
                
                # Also patch WebSocket URLs in the client configuration
                if hasattr(self.client, 'ws_url'):
                    original_ws_url = self.client.ws_url
                    self.client.ws_url = f"wss://ws2.{base_domain}/socket.io/?EIO=3&transport=websocket"
                    self.logger.info(f"🌐 Patched WebSocket URL to: {self.client.ws_url}")
                
                # Patch any other URLs that might be using the domain
                if hasattr(self.client, 'config') and hasattr(self.client.config, 'ws_url'):
                    original_config_ws_url = self.client.config.ws_url
                    self.client.config.ws_url = f"wss://ws2.{base_domain}/socket.io/?EIO=3&transport=websocket"
                    self.logger.info(f"🌐 Patched config WebSocket URL to: {self.client.config.ws_url}")
                
                self.logger.info(f"🌐 Attempting PyQuotex login via domain: {base_domain}")
                try:
                    try:
                        check_connect, message = await self.client.connect()
                    except SystemExit:
                        self.logger.error("❌ PyQuotex login attempted to exit the application")
                        check_connect, message = False, "Login failed with SystemExit"
                except json.JSONDecodeError as json_err:
                    self.logger.error(f"❌ JSON parsing error during connection via {base_domain}: {str(json_err)}")
                    # Wait a moment and retry once on the same domain
                    self.logger.info("🔄 Retrying connection after JSON error...")
                    await asyncio.sleep(3)
                    try:
                        check_connect, message = await self.client.connect()
                    except SystemExit:
                        self.logger.error("❌ PyQuotex login attempted to exit the application")
                        check_connect, message = False, "Login failed with SystemExit"
                except Exception as e:
                    self.logger.error(f"❌ Unexpected connection error via {base_domain}: {e}")
                    check_connect, message = False, str(e)
                finally:
                    if not check_connect:
                        # Restore original values only if connection failed
                        Login.base_url = original_base_url
                        Login.https_base_url = original_https_base_url
                        if hasattr(self.client, 'ws_url'):
                            self.client.ws_url = original_ws_url
                        if hasattr(self.client, 'config') and hasattr(self.client.config, 'ws_url'):
                            self.client.config.ws_url = original_config_ws_url

                if check_connect:
                    self.last_domain_used = base_domain
                    self.logger.info(f"✅ Connected via domain: {base_domain}")
                    # Keep the successful domain patched - don't restore the original values
                    break
                else:
                    self.logger.warning(f"⚠️ Login failed via domain {base_domain}: {message}")

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
    
    async def disconnect(self, close_db: bool = False):
        """Disconnect from PyQuotex and optionally MongoDB.
        By default, keep the DB connection open to avoid disrupting the service during reconnects.
        """
        try:
            if self.client and self.is_connected:
                try:
                    # Avoid hanging indefinitely on close
                    await asyncio.wait_for(self.client.close(), timeout=10)
                except asyncio.TimeoutError:
                    self.logger.warning("⚠️ Timeout while closing PyQuotex client (10s)")
                except Exception as ce:
                    self.logger.warning(f"⚠️ Error while closing PyQuotex client: {ce}")
                finally:
                    self.is_connected = False
                    # Don't clear last_domain_used so we can use it on reconnect
                    self.logger.info("🔌 Disconnected from PyQuotex")
        except Exception as e:
            self.logger.warning(f"⚠️ Unexpected error during disconnect: {e}")

        if close_db:
            try:
                await self.db.disconnect()
            except Exception as de:
                self.logger.warning(f"⚠️ Error while disconnecting from MongoDB: {de}")
    
    async def collect_candle_data(self, asset: str) -> List[CandleData]:
        """
        Collect current candle data for an asset using PyQuotex API.
        Returns all completed candles (excludes the last which may be incomplete).
        Atomic upsert ensures no duplicates — free micro-gap repair.
        """
        try:
            if not self.is_connected:
                self.logger.error("❌ Not connected to PyQuotex")
                return None
            
            # Ensure we're using the last successful domain for WebSocket connections
            if self.last_domain_used and self.client:
                # Re-patch WebSocket URLs if needed to ensure consistency with the domain that worked
                if hasattr(self.client, 'ws_url') and 'ws2.' in self.client.ws_url and self.last_domain_used not in self.client.ws_url:
                    self.client.ws_url = f"wss://ws2.{self.last_domain_used}/socket.io/?EIO=3&transport=websocket"
                    self.logger.info(f"🔄 Re-patched WebSocket URL to use successful domain: {self.client.ws_url}")
                if hasattr(self.client, 'config') and hasattr(self.client.config, 'ws_url') and self.last_domain_used not in self.client.config.ws_url:
                    self.client.config.ws_url = f"wss://ws2.{self.last_domain_used}/socket.io/?EIO=3&transport=websocket"
                    self.logger.info(f"🔄 Re-patched config WebSocket URL to use successful domain: {self.client.config.ws_url}")
            
            self.logger.info(f"📊 Collecting candle data for {asset}...")
            
            # Setup retrieval window: 5 minutes = 5 candles (reduced from 3600s/60 candles)
            offset = 300  # seconds
            period = self.timeframe
            end_from_time = time.time()

            # Resolve asset to a valid/available asset (adds _otc or picks open variant)
            candles_data = None
            # The requested/display name we will store/broadcast
            requested_name = asset
            asset_to_use = asset
            source_symbol_used = None

            # Normalize requested_name to API style using shared utility
            try:
                requested_name = to_api_asset(requested_name) or requested_name
            except Exception:
                pass

            try:
                # Ask API to find the correct/open asset
                try:
                    asset_name, asset_data = await self.client.get_available_asset(asset_to_use, force_open=True)
                    if asset_name:
                        asset_to_use = asset_name
                        self.logger.info(f"📊 Resolved asset: {asset} -> {asset_to_use}")
                except Exception as resolve_err:
                    self.logger.warning(f"⚠️ Could not resolve asset via get_available_asset: {resolve_err}")
                    # Best-effort: ensure _otc suffix if missing
                    if "_otc" not in asset_to_use.lower():
                        asset_to_use = f"{asset_to_use}_otc"

                async def fetch_candles(symbol: str):
                    self.logger.info(f"📊 Requesting candles for {symbol} (period: {period}, offset: {offset})")
                    try:
                        data = await self.client.get_candles(symbol, end_from_time, offset, period)
                        return data
                    except json.JSONDecodeError as json_err:
                        self.logger.error(f"❌ JSON parsing error for {symbol}: {str(json_err)}")
                        self.logger.info("🔄 Reconnecting to PyQuotex after JSON error...")
                        await self.connect()
                        await asyncio.sleep(2)
                        return await self.client.get_candles(symbol, end_from_time, offset, period)

                # First attempt: resolved asset
                candles_data = await fetch_candles(asset_to_use)
                if candles_data:
                    source_symbol_used = asset_to_use

                # Fallback: try inverted asset if empty
                if not candles_data:
                    self.logger.warning(f"⚠️ No candle data received for {asset_to_use} - trying inverted asset fallback")

                    def invert_symbol(sym: str) -> str:
                        s = sym.replace('(OTC)', '').replace('/', '')
                        suffix = ''
                        if s.lower().endswith('_otc'):
                            s = s[:-4]
                            suffix = '_otc'
                        # Expect 6-letter forex like USDBRL
                        if len(s) == 6:
                            a, b = s[:3], s[3:]
                            return f"{b}{a}{suffix}"
                        return sym  # give up

                    inverted = invert_symbol(asset_to_use)
                    if inverted != asset_to_use:
                        # Try resolving the inverted via API too
                        try:
                            inv_name, _ = await self.client.get_available_asset(inverted, force_open=True)
                            if inv_name:
                                inverted = inv_name
                        except Exception as inv_err:
                            self.logger.warning(f"⚠️ Could not resolve inverted asset {inverted}: {inv_err}")
                        self.logger.info(f"🔁 Fallback requesting inverted asset: {inverted}")
                        candles_data = await fetch_candles(inverted)
                        if candles_data:
                            source_symbol_used = inverted

                if not candles_data:
                    self.logger.warning(f"⚠️ No candle data received for either primary or fallback symbols")
                    return None
                else:
                    self.logger.info(f"✅ Received {len(candles_data)} candles")
            except Exception as e:
                self.logger.error(f"❌ Error getting candles for {asset_to_use}: {str(e)}")
                import traceback
                self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
                return None
            
            # Process candles if needed (following PyQuotex example)
            test_candle = candles_data[0] if candles_data else {}
            if not test_candle.get("open"):
                from pyquotex.utils.processor import process_candles
                processed = process_candles(candles_data, period)
                if processed and len(processed) > 0:
                    candles_data = processed
                else:
                    self.logger.warning(f"⚠️ Could not process candle data for {asset}")
                    return []

            # Return all completed candles (exclude last which may be incomplete)
            completed_raw = candles_data[:-1] if len(candles_data) > 1 else candles_data
            formatted_pair = requested_name

            result = []
            for raw in completed_raw:
                candle = CandleData(
                    timestamp=datetime.fromtimestamp(raw.get('time', time.time())),
                    trading_pair=formatted_pair,
                    open_price=float(raw.get('open', 0)),
                    high_price=float(raw.get('high', raw.get('max', 0))),
                    low_price=float(raw.get('low', raw.get('min', 0))),
                    close_price=float(raw.get('close', 0)),
                    volume=0,
                    is_closed=True,
                    is_validated=False,
                    source='pyquotex_api',
                    asset=source_symbol_used or asset_to_use,
                    period=period
                )
                result.append(candle)

            self.logger.info(f"✅ Collected {len(result)} completed candles for {formatted_pair}")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error collecting candle for {asset}: {str(e)}")
            import traceback
            self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return []
    
    async def collect_realtime_data(self, asset: str) -> Optional[Dict]:
        """
        Collect real-time price data for an asset
        """
        try:
            if not self.is_connected:
                return None
            
            # Ensure we're using the last successful domain for WebSocket connections
            if self.last_domain_used and self.client:
                # Re-patch WebSocket URLs if needed to ensure consistency with the domain that worked
                if hasattr(self.client, 'ws_url') and 'ws2.' in self.client.ws_url and self.last_domain_used not in self.client.ws_url:
                    self.client.ws_url = f"wss://ws2.{self.last_domain_used}/socket.io/?EIO=3&transport=websocket"
                    self.logger.info(f"🔄 Re-patched WebSocket URL to use successful domain: {self.client.ws_url}")
                if hasattr(self.client, 'config') and hasattr(self.client.config, 'ws_url') and self.last_domain_used not in self.client.config.ws_url:
                    self.client.config.ws_url = f"wss://ws2.{self.last_domain_used}/socket.io/?EIO=3&transport=websocket"
                    self.logger.info(f"🔄 Re-patched config WebSocket URL to use successful domain: {self.client.config.ws_url}")
            
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
    
    async def get_historical_candles(self, asset: str, days: float = 1, timeframe: int = 60, end_from_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve historical candles for an asset by chunking calls to client.get_candles.
        `days` can be fractional (e.g. 0.01 ≈ 15 minutes).
        Returns a list of raw candle dicts as provided by the API.
        """
        try:
            if not self.is_connected:
                self.logger.error("❌ Not connected to PyQuotex")
                return []
            
            # Ensure we're using the last successful domain for WebSocket connections
            if self.last_domain_used and self.client:
                # Re-patch WebSocket URLs if needed to ensure consistency with the domain that worked
                if hasattr(self.client, 'ws_url') and 'ws2.' in self.client.ws_url and self.last_domain_used not in self.client.ws_url:
                    self.client.ws_url = f"wss://ws2.{self.last_domain_used}/socket.io/?EIO=3&transport=websocket"
                    self.logger.info(f"🔄 Re-patched WebSocket URL to use successful domain: {self.client.ws_url}")
                if hasattr(self.client, 'config') and hasattr(self.client.config, 'ws_url') and self.last_domain_used not in self.client.config.ws_url:
                    self.client.config.ws_url = f"wss://ws2.{self.last_domain_used}/socket.io/?EIO=3&transport=websocket"
                    self.logger.info(f"🔄 Re-patched config WebSocket URL to use successful domain: {self.client.config.ws_url}")
            
            # Normalize to API-style symbol using shared utility
            symbol = to_api_asset(asset) or asset
            
            # Try to resolve to an open/available asset
            try:
                resolved, _ = await self.client.get_available_asset(symbol, force_open=True)
                if resolved:
                    symbol = resolved
            except Exception as e:
                self.logger.warning(f"⚠️ Could not resolve historical symbol '{symbol}': {e}")
            
            total_seconds = max(60, int(float(days) * 86400))
            # API expects 'offset' as the NUMBER OF CANDLES, not seconds. Use a sane chunk of candles per request.
            # Default: 6 hours worth of candles at given timeframe
            default_chunk_seconds = 21600  # 6 hours window
            chunk_candles_default = max(1, default_chunk_seconds // int(timeframe))
            max_candles_per_req = int(os.getenv("QX_MAX_CANDLES_PER_REQUEST", str(chunk_candles_default)))
            # Allow callers to specify an end timestamp to walk back from
            end_from_time = int(end_from_time) if end_from_time is not None else int(time.time())
            collected: List[Dict[str, Any]] = []
            covered_seconds = 0
            
            self.logger.info(f"📚 Fetching ~{days} day(s) of historical data for {symbol} at {timeframe}s timeframe")
            while covered_seconds < total_seconds:
                remaining_seconds = total_seconds - covered_seconds
                remaining_candles = max(1, remaining_seconds // int(timeframe))
                offset_candles = int(min(max_candles_per_req, remaining_candles))
                try:
                    self.logger.info(f"📚 Historical chunk: symbol={symbol} period={timeframe}s offset_candles={offset_candles} end={end_from_time}")
                    data = await self.client.get_candles(symbol, end_from_time, offset_candles, timeframe)
                    if data:
                        collected.extend(data)
                    # Move the window back by the number of candles fetched
                    delta_seconds = offset_candles * int(timeframe)
                    end_from_time -= delta_seconds
                    covered_seconds += delta_seconds
                    await asyncio.sleep(0.2)
                except json.JSONDecodeError as je:
                    self.logger.warning(f"⚠️ JSON decode error on historical chunk: {je}. Reconnecting and retrying chunk once...")
                    await self.connect()
                    await asyncio.sleep(1)
                except Exception as e:
                    self.logger.error(f"❌ Error fetching historical chunk: {e}")
                    break
            
            # De-duplicate and sort by time
            unique = {}
            for c in collected:
                t = c.get('time') or c.get('t')
                if t is not None:
                    unique[int(t)] = c
            ordered = [unique[k] for k in sorted(unique.keys())]
            self.logger.info(f"📚 Historical fetch complete: {len(ordered)} candles")
            return ordered
        except Exception as e:
            self.logger.error(f"❌ Error in get_historical_candles: {e}")
            return []

    async def process_historical_candles(self, candles: List[Dict[str, Any]], base_pair: str) -> int:
        """
        Convert and store historical candles as CandleData.
        base_pair can be human (USD/BRL(OTC)) or API style (USDBRL_otc/BRLUSD_otc).
        Returns number of candles saved.
        """
        try:
            if not candles:
                return 0
            # Normalize trading pair label for storage using shared utility
            requested_name = to_api_asset(base_pair) or base_pair
            
            saved = 0
            period = self.timeframe
            for raw in candles:
                ts = raw.get('time') or raw.get('t')
                if ts is None:
                    continue
                open_v = raw.get('open', raw.get('o'))
                close_v = raw.get('close', raw.get('c'))
                high_v = raw.get('high', raw.get('max', raw.get('h')))
                low_v = raw.get('low', raw.get('min', raw.get('l')))
                if open_v is None or close_v is None or high_v is None or low_v is None:
                    continue
                candle = CandleData(
                    timestamp=datetime.fromtimestamp(int(ts)),
                    trading_pair=requested_name,
                    open_price=float(open_v),
                    high_price=float(high_v),
                    low_price=float(low_v),
                    close_price=float(close_v),
                    volume=0,
                    is_closed=True,
                    is_validated=False,
                    source='pyquotex_api',
                    asset=requested_name,
                    period=period
                )
                try:
                    # Atomic upsert: no race condition, handles duplicates gracefully
                    await self.db.save_candle(candle)
                    saved += 1
                except Exception as se:
                    self.logger.warning(f"⚠️ Failed to save historical candle @ {ts}: {se}")
            self.logger.info(f"💾 Saved {saved} historical candles for {requested_name}")
            return saved
        except Exception as e:
            self.logger.error(f"❌ Error processing historical candles: {e}")
            return 0
    
    async def collect_all_assets(self) -> List[CandleData]:
        """
        Collect candle data for all configured trading pairs
        """
        collected = []

        for asset in self.trading_pairs:
            try:
                candles = await self.collect_candle_data(asset)
                for candle in candles:
                    # Save to MongoDB (atomic upsert handles duplicates)
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

            candles = await self.collect_candle_data(asset_name)
            if candles:
                # Save all candles to MongoDB (atomic upsert handles duplicates)
                for candle in candles:
                    if not hasattr(candle, '_id') or not candle._id:
                        candle_id = await self.db.save_candle(candle)
                        candle._id = candle_id
                return candles
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