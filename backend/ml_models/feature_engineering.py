"""
Feature Engineering Module for OTC Predictor
Extracts technical indicators and features from candle data for ML training
"""

import numpy as np
import pandas as pd
import talib
from typing import List, Dict, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from database.mongodb_models import MongoDBManager, CandleData

logger = logging.getLogger(__name__)

class FeatureEngineer:
    """
    Feature engineering class for creating ML features from candle data
    """
    
    def __init__(self, mongodb_manager: MongoDBManager = None):
        self.mongodb = mongodb_manager or MongoDBManager()
        
        # Technical indicator parameters
        self.rsi_period = 14
        self.sma_periods = [5, 10, 20, 50]
        self.ema_periods = [5, 10, 20, 50]
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2
        self.stoch_k = 14
        self.stoch_d = 3
        
        # Feature lookback window
        self.lookback_periods = [5, 10, 20]
        
    async def extract_features_from_candles(self, candles: List[Dict], target_next: bool = True) -> pd.DataFrame:
        """
        Extract comprehensive features from candle data
        
        Args:
            candles: List of candle dictionaries from MongoDB
            target_next: Whether to include next candle direction as target
            
        Returns:
            DataFrame with features and optionally target variable
        """
        
        if len(candles) < 30:  # Need minimum data for indicators
            logger.warning(f"Insufficient data: {len(candles)} candles (need at least 30)")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        
        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'timestamp']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing required columns. Available: {df.columns.tolist()}")
            return pd.DataFrame()
        
        # Convert to numpy arrays for TA-Lib
        open_prices = df['open'].astype(float).values
        high_prices = df['high'].astype(float).values
        low_prices = df['low'].astype(float).values
        close_prices = df['close'].astype(float).values
        
        # Handle volume column (create default if not exists)
        if 'volume' in df.columns:
            volumes = df['volume'].astype(float).values
        else:
            volumes = np.ones(len(df))
        
        # Initialize features dictionary
        features = {}
        
        try:
            # Basic OHLC features
            features.update(self._extract_basic_features(df))
            
            # Technical indicators
            features.update(self._extract_technical_indicators(
                open_prices, high_prices, low_prices, close_prices, volumes
            ))
            
            # Price patterns and relationships
            features.update(self._extract_price_patterns(close_prices))
            
            # Time-based features
            features.update(self._extract_time_features(df))
            
            # Volatility features
            features.update(self._extract_volatility_features(close_prices, high_prices, low_prices))
            
            # Volume features (if available)
            if 'volume' in df.columns:
                features.update(self._extract_volume_features(close_prices, volumes))
            
            # Statistical features
            features.update(self._extract_statistical_features(close_prices))
        except Exception as e:
            logger.error(f"❌ Error extracting features: {str(e)}")
            # Continue with whatever features we have
        
        # Create feature DataFrame
        feature_df = pd.DataFrame(features)
        
        # Add target variable if requested
        if target_next:
            feature_df['target'] = self._create_target_variable(close_prices)
        
        # Add timestamp for reference
        feature_df['timestamp'] = df['timestamp']
        
        # Check if we have any rows before dropping NaN values
        if feature_df.shape[0] == 0:
            logger.error("❌ Empty DataFrame after feature extraction")
            return pd.DataFrame()
        
        # First, fill NaN values in features that can be safely interpolated
        numeric_cols = feature_df.select_dtypes(include=['float64', 'int64']).columns
        feature_df[numeric_cols] = feature_df[numeric_cols].interpolate(method='linear').fillna(0)
        
        # For target column, we can't interpolate, so we'll drop rows where target is NaN
        if target_next and 'target' in feature_df.columns:
            feature_df = feature_df.dropna(subset=['target'])
        
        # Check if we still have rows after handling NaNs
        if feature_df.shape[0] == 0:
            logger.error("❌ No data left after handling NaN values")
            return pd.DataFrame()
        
        logger.info(f"✅ Extracted {feature_df.shape[1]} features from {len(candles)} candles")
        logger.info(f"📊 Feature DataFrame shape: {feature_df.shape}")
        
        return feature_df
    
    def _extract_basic_features(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Extract basic OHLC-based features"""
        
        features = {}
        
        # Price changes
        features['price_change'] = df['close'] - df['open']
        features['price_change_pct'] = (df['close'] - df['open']) / df['open'] * 100
        features['high_low_spread'] = df['high'] - df['low']
        features['high_low_spread_pct'] = (df['high'] - df['low']) / df['open'] * 100
        
        # Body and wick ratios
        body_size = abs(df['close'] - df['open'])
        total_range = df['high'] - df['low']
        features['body_ratio'] = body_size / (total_range + 1e-8)  # Avoid division by zero
        
        upper_wick = df['high'] - np.maximum(df['open'], df['close'])
        lower_wick = np.minimum(df['open'], df['close']) - df['low']
        features['upper_wick_ratio'] = upper_wick / (total_range + 1e-8)
        features['lower_wick_ratio'] = lower_wick / (total_range + 1e-8)
        
        # Direction (1 for up, -1 for down)
        features['direction'] = np.where(df['close'] > df['open'], 1, -1)
        
        return features
    
    def _extract_technical_indicators(self, open_p: np.ndarray, high_p: np.ndarray, 
                                    low_p: np.ndarray, close_p: np.ndarray, 
                                    volume: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract technical indicators using TA-Lib"""
        
        features = {}
        
        try:
            # RSI
            features['rsi'] = talib.RSI(close_p, timeperiod=self.rsi_period)
            features['rsi_overbought'] = (features['rsi'] > 70).astype(int)
            features['rsi_oversold'] = (features['rsi'] < 30).astype(int)
            
            # Moving Averages
            for period in self.sma_periods:
                sma = talib.SMA(close_p, timeperiod=period)
                features[f'sma_{period}'] = sma
                features[f'price_above_sma_{period}'] = (close_p > sma).astype(int)
                features[f'sma_{period}_slope'] = np.gradient(sma)
            
            for period in self.ema_periods:
                ema = talib.EMA(close_p, timeperiod=period)
                features[f'ema_{period}'] = ema
                features[f'price_above_ema_{period}'] = (close_p > ema).astype(int)
                features[f'ema_{period}_slope'] = np.gradient(ema)
            
            # MACD
            macd, macd_signal, macd_hist = talib.MACD(
                close_p, fastperiod=self.macd_fast, 
                slowperiod=self.macd_slow, signalperiod=self.macd_signal
            )
            features['macd'] = macd
            features['macd_signal'] = macd_signal
            features['macd_histogram'] = macd_hist
            features['macd_bullish'] = (macd > macd_signal).astype(int)
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = talib.BBANDS(
                close_p, timeperiod=self.bb_period, nbdevup=self.bb_std, 
                nbdevdn=self.bb_std, matype=0
            )
            features['bb_upper'] = bb_upper
            features['bb_middle'] = bb_middle
            features['bb_lower'] = bb_lower
            features['bb_width'] = (bb_upper - bb_lower) / bb_middle
            features['bb_position'] = (close_p - bb_lower) / (bb_upper - bb_lower)
            features['price_above_bb_upper'] = (close_p > bb_upper).astype(int)
            features['price_below_bb_lower'] = (close_p < bb_lower).astype(int)
            
            # Stochastic
            stoch_k, stoch_d = talib.STOCH(
                high_p, low_p, close_p, fastk_period=self.stoch_k, 
                slowk_period=self.stoch_d, slowd_period=self.stoch_d
            )
            features['stoch_k'] = stoch_k
            features['stoch_d'] = stoch_d
            features['stoch_overbought'] = (stoch_k > 80).astype(int)
            features['stoch_oversold'] = (stoch_k < 20).astype(int)
            
            # ADX (Trend Strength)
            features['adx'] = talib.ADX(high_p, low_p, close_p, timeperiod=14)
            features['strong_trend'] = (features['adx'] > 25).astype(int)
            
            # Williams %R
            features['williams_r'] = talib.WILLR(high_p, low_p, close_p, timeperiod=14)
            
            # Commodity Channel Index
            features['cci'] = talib.CCI(high_p, low_p, close_p, timeperiod=14)
            
            # Average True Range (Volatility)
            features['atr'] = talib.ATR(high_p, low_p, close_p, timeperiod=14)
            features['atr_ratio'] = features['atr'] / close_p
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {str(e)}")
        
        return features
    
    def _extract_price_patterns(self, close_p: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract price pattern features"""
        
        features = {}
        
        # Price momentum over different periods
        for period in self.lookback_periods:
            if len(close_p) > period:
                try:
                    # Calculate momentum
                    momentum = (close_p[period:] - close_p[:-period]) / close_p[:-period] * 100
                    # Make sure the array length matches close_p
                    padded_momentum = np.concatenate([np.full(period, np.nan), momentum])
                    # Ensure the array has the exact same length as close_p
                    if len(padded_momentum) == len(close_p):
                        features[f'momentum_{period}'] = padded_momentum
                    else:
                        # If lengths don't match, just use the ROC function which handles padding internally
                        features[f'momentum_{period}'] = talib.ROC(close_p, timeperiod=period)
                except Exception as e:
                    # Fallback to ROC if there's an error
                    features[f'momentum_{period}'] = talib.ROC(close_p, timeperiod=period)
                
                # Rate of change (already handled by talib)
                features[f'roc_{period}'] = talib.ROC(close_p, timeperiod=period)
        
        # Support and resistance levels (simplified)
        try:
            rolling_max_20 = pd.Series(close_p).rolling(window=20).max().values
            rolling_min_20 = pd.Series(close_p).rolling(window=20).min().values
            
            # Ensure arrays have the same length
            if len(rolling_max_20) == len(close_p) and len(rolling_min_20) == len(close_p):
                features['distance_to_resistance'] = (rolling_max_20 - close_p) / close_p * 100
                features['distance_to_support'] = (close_p - rolling_min_20) / close_p * 100
        except Exception as e:
            # Skip these features if there's an error
            pass
        
        return features
    
    def _extract_time_features(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Extract time-based features"""
        
        features = {}
        
        # Convert timestamp to datetime if it's not already
        timestamps = pd.to_datetime(df['timestamp'])
        
        # Hour of day (0-23)
        features['hour'] = timestamps.dt.hour.values
        features['is_market_open'] = ((timestamps.dt.hour >= 8) & (timestamps.dt.hour <= 17)).astype(int)
        
        # Day of week (0=Monday, 6=Sunday)
        features['day_of_week'] = timestamps.dt.dayofweek.values
        features['is_weekend'] = (timestamps.dt.dayofweek >= 5).astype(int)
        
        # Month
        features['month'] = timestamps.dt.month.values
        
        return features
    
    def _extract_volatility_features(self, close_p: np.ndarray, high_p: np.ndarray, 
                                   low_p: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract volatility-based features"""
        
        features = {}
        
        # Historical volatility over different periods
        for period in [5, 10, 20]:
            if len(close_p) > period:
                returns = np.diff(np.log(close_p))
                rolling_vol = pd.Series(returns).rolling(window=period).std().values
                features[f'volatility_{period}'] = np.concatenate([[np.nan], rolling_vol])
        
        # True Range
        if len(high_p) > 1:
            tr1 = high_p[1:] - low_p[1:]
            tr2 = np.abs(high_p[1:] - close_p[:-1])
            tr3 = np.abs(low_p[1:] - close_p[:-1])
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            features['true_range'] = np.concatenate([[np.nan], tr])
        else:
            features['true_range'] = np.array([np.nan] * len(high_p))
        
        return features
    
    def _extract_volume_features(self, close_p: np.ndarray, volume: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract volume-based features"""
        
        features = {}
        
        try:
            # Volume moving averages
            features['volume_sma_10'] = talib.SMA(volume, timeperiod=10)
            features['volume_ratio'] = volume / (features['volume_sma_10'] + 1e-8)
            
            # Price-Volume relationship
            try:
                price_change = np.diff(close_p)
                volume_change = np.diff(volume)
                
                # Create a safer correlation array
                corr_array = np.full(len(close_p), np.nan)
                
                # Only calculate correlations where we have enough data
                for i in range(10, len(price_change)):
                    try:
                        corr = np.corrcoef(price_change[i-10:i], volume_change[i-10:i])[0,1]
                        corr_array[i+1] = corr  # +1 because diff reduces array length by 1
                    except:
                        pass
                
                # Only add if the array has the right length
                if len(corr_array) == len(close_p):
                    features['price_volume_correlation'] = corr_array
            except Exception as e:
                # Skip correlation if there's an error
                pass
        except Exception as e:
            # Skip volume features if there's an error
            pass
        
        return features
    
    def _extract_statistical_features(self, close_p: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract statistical features"""
        
        features = {}
        
        try:
            # Rolling statistics
            close_series = pd.Series(close_p)
            
            for window in [5, 10, 20]:
                try:
                    # Standard deviation
                    std_values = close_series.rolling(window=window).std().values
                    if len(std_values) == len(close_p):
                        features[f'std_{window}'] = std_values
                except Exception as e:
                    pass
                
                try:
                    # Skewness
                    skew_values = close_series.rolling(window=window).skew().values
                    if len(skew_values) == len(close_p):
                        features[f'skew_{window}'] = skew_values
                except Exception as e:
                    pass
                
                try:
                    # Kurtosis
                    kurt_values = close_series.rolling(window=window).kurt().values
                    if len(kurt_values) == len(close_p):
                        features[f'kurtosis_{window}'] = kurt_values
                except Exception as e:
                    pass
        except Exception as e:
            # Skip statistical features if there's an error
            pass
        
        return features
    
    def _create_target_variable(self, close_p: np.ndarray) -> np.ndarray:
        """
        Create target variable for prediction
        1 if next candle closes higher, 0 if lower
        """
        try:
            # Shift prices to get next candle's close
            next_close = np.roll(close_p, -1)
            
            # Create binary target (1 for up, 0 for down)
            target = (next_close > close_p).astype(float)  # Use float to allow NaN
            
            # Last value is NaN since we don't have next candle
            target[-1] = np.nan
            
            # For safety, replace any potential NaN/inf values with 0.5 (uncertain prediction)
            # This ensures we don't lose rows due to NaN in the target
            target = np.nan_to_num(target, nan=0.5)
            
            # Convert back to binary (0 or 1)
            target = (target > 0.5).astype(float)
            
            return target
        except Exception as e:
            # If there's an error, return a default target (all 0.5)
            logger.error(f"❌ Error creating target variable: {str(e)}")
            return np.full(len(close_p), 0.5)
    
    async def prepare_training_data(self, trading_pair: str = "EURUSD OTC", 
                                  limit: int = 1000) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare training data with features and targets
        
        Returns:
            Tuple of (features_df, targets_df)
        """
        
        logger.info(f"🔄 Preparing training data for {trading_pair}")
        
        # Connect to MongoDB if not connected
        if not self.mongodb.is_connected:
            await self.mongodb.connect()
        
        # Try different formats for the trading pair
        candles = []
        tried_formats = []
        
        # 1. Try the original format
        tried_formats.append(trading_pair)
        candles = await self.mongodb.get_candles_for_training(limit=limit, trading_pair=trading_pair)
        
        # 2. If no candles found, try converting to USD/BRL(OTC) format
        if len(candles) < 50 and " OTC" in trading_pair:
            # Convert USDBRL OTC to USD/BRL(OTC)
            base_quote = trading_pair.replace(" OTC", "")
            if len(base_quote) == 6:  # Standard currency pair length
                alt_format = f"{base_quote[:3]}/{base_quote[3:]}(OTC)"
                tried_formats.append(alt_format)
                logger.info(f"Trying alternative format: {alt_format}")
                candles = await self.mongodb.get_candles_for_training(limit=limit, trading_pair=alt_format)
        
        # 3. If still no candles, try the reverse format
        if len(candles) < 50 and "/" in trading_pair and "(" in trading_pair:
            # Convert USD/BRL(OTC) to USDBRL OTC
            currency_pair = trading_pair.split('(')[0]  # Get USD/BRL
            base, quote = currency_pair.split('/')      # Split into USD and BRL
            alt_format = f"{base}{quote} OTC"          # Make USDBRL OTC
            tried_formats.append(alt_format)
            logger.info(f"Trying alternative format: {alt_format}")
            candles = await self.mongodb.get_candles_for_training(limit=limit, trading_pair=alt_format)
        
        # 4. If still no candles, try to get all available pairs and find the best match
        if len(candles) < 50:
            try:
                all_pairs_cursor = await self.mongodb.db.candle_data.distinct("trading_pair")
                logger.info(f"Available trading pairs in database: {all_pairs_cursor}")
                
                # Try each available pair to see if it might match
                for pair in all_pairs_cursor:
                    # Skip if we already tried this format
                    if pair in tried_formats:
                        continue
                        
                    # Check if this pair might be related to our target pair
                    base_trading_pair = trading_pair.replace(" OTC", "").replace("/", "").replace("(OTC)", "")
                    base_pair = pair.replace(" OTC", "").replace("/", "").replace("(OTC)", "")
                    
                    if base_trading_pair.upper() == base_pair.upper() or base_trading_pair.upper() in base_pair.upper() or base_pair.upper() in base_trading_pair.upper():
                        logger.info(f"Found potential match: {pair} for {trading_pair}")
                        tried_formats.append(pair)
                        candles = await self.mongodb.get_candles_for_training(limit=limit, trading_pair=pair)
                        if len(candles) >= 50:
                            logger.info(f"Using trading pair format: {pair}")
                            break
            except Exception as e:
                logger.error(f"Error searching for alternative formats: {str(e)}")
        
        logger.info(f"Tried formats: {tried_formats}")
        
        if len(candles) < 50:
            logger.error(f"Insufficient data: {len(candles)} candles")
            return pd.DataFrame(), pd.DataFrame()
        
        # Extract features
        feature_df = await self.extract_features_from_candles(candles, target_next=True)
        
        if feature_df.empty:
            logger.error("Failed to extract features")
            return pd.DataFrame(), pd.DataFrame()
        
        # Separate features and target
        target_col = 'target'
        if target_col not in feature_df.columns:
            logger.error("Target variable not found in features")
            return pd.DataFrame(), pd.DataFrame()
        
        # Remove timestamp and target from features
        features = feature_df.drop(columns=[target_col, 'timestamp'])
        targets = feature_df[[target_col, 'timestamp']]
        
        logger.info(f"✅ Training data prepared: {features.shape[0]} samples, {features.shape[1]} features")
        
        return features, targets
    
    def get_feature_importance_names(self) -> List[str]:
        """Get list of all possible feature names for importance analysis"""
        
        feature_names = []
        
        # Basic features
        basic_features = [
            'price_change', 'price_change_pct', 'high_low_spread', 'high_low_spread_pct',
            'body_ratio', 'upper_wick_ratio', 'lower_wick_ratio', 'direction'
        ]
        feature_names.extend(basic_features)
        
        # Technical indicators
        feature_names.extend(['rsi', 'rsi_overbought', 'rsi_oversold'])
        
        for period in self.sma_periods:
            feature_names.extend([f'sma_{period}', f'price_above_sma_{period}', f'sma_{period}_slope'])
        
        for period in self.ema_periods:
            feature_names.extend([f'ema_{period}', f'price_above_ema_{period}', f'ema_{period}_slope'])
        
        feature_names.extend([
            'macd', 'macd_signal', 'macd_histogram', 'macd_bullish',
            'bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'bb_position',
            'price_above_bb_upper', 'price_below_bb_lower',
            'stoch_k', 'stoch_d', 'stoch_overbought', 'stoch_oversold',
            'adx', 'strong_trend', 'williams_r', 'cci', 'atr', 'atr_ratio'
        ])
        
        # Pattern features
        for period in self.lookback_periods:
            feature_names.extend([f'momentum_{period}', f'roc_{period}'])
        
        feature_names.extend(['distance_to_resistance', 'distance_to_support'])
        
        # Time features
        feature_names.extend(['hour', 'is_market_open', 'day_of_week', 'is_weekend', 'month'])
        
        # Volatility features
        for period in [5, 10, 20]:
            feature_names.extend([f'volatility_{period}'])
        feature_names.append('true_range')
        
        # Statistical features
        for window in [5, 10, 20]:
            feature_names.extend([f'std_{window}', f'skew_{window}', f'kurtosis_{window}'])
        
        return feature_names 