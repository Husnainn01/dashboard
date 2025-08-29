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
        
        # Import composite feature generator
        from ml_models.composite_features import CompositeFeatureGenerator
        self.composite_generator = CompositeFeatureGenerator()
        
        # Technical indicator parameters - Enhanced for USD/BRL(OTC)
        self.rsi_period = 14
        self.rsi_periods = [7, 14, 21]  # Multiple RSI periods for better signal detection
        self.sma_periods = [5, 8, 13, 21, 34, 55]  # Fibonacci-based periods
        self.ema_periods = [5, 8, 13, 21, 34, 55]  # Fibonacci-based periods
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2
        self.bb_stds = [1.5, 2, 2.5]  # Multiple Bollinger Band standard deviations
        self.stoch_k = 14
        self.stoch_d = 3
        self.stoch_periods = [(5,3), (14,3), (21,5)]  # Multiple stochastic settings
        self.adx_periods = [14, 21]  # Multiple ADX periods
        self.cci_periods = [14, 20]  # Multiple CCI periods
        self.atr_periods = [7, 14, 21]  # Multiple ATR periods
        self.williams_periods = [7, 14, 21]  # Multiple Williams %R periods
        
        # Feature lookback window - Extended for better pattern recognition
        self.lookback_periods = [5, 8, 13, 21, 34]  # Fibonacci sequence for better pattern detection
        
        # USD/BRL(OTC) specific parameters - Market operates in UTC+7 (Bangkok time)
        self.is_optimized_for_usd_brl = True
        self.market_session_hours = {
            'asian': (17, 1),     # 17:00-01:00 UTC (00:00-08:00 Bangkok time)
            'european': (1, 9),   # 01:00-09:00 UTC (08:00-16:00 Bangkok time)
            'american': (6, 14)   # 06:00-14:00 UTC (13:00-21:00 Bangkok time)
        }
        
        # Add USD/BRL(OTC) specific market hours
        self.brazil_market_hours = {
            'open': 1,    # 01:00 UTC (08:00 Bangkok time)
            'close': 9,   # 09:00 UTC (16:00 Bangkok time)
            'peak': (3, 7)  # 03:00-07:00 UTC (10:00-14:00 Bangkok time)
        }
        
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
            volume = df['volume'].astype(float).values
        else:
            volume = np.ones_like(close_prices)  # Default volume if not available
        
        # Extract all features
        features_dict = {}
        
        try:
            # Basic features
            basic_features = self._extract_basic_features(df)
            features_dict.update(basic_features)
            
            # Technical indicators
            tech_indicators = self._extract_technical_indicators(
                open_prices, high_prices, low_prices, close_prices, volume
            )
            features_dict.update(tech_indicators)
            
            # Price patterns
            price_patterns = self._extract_price_patterns(close_prices)
            features_dict.update(price_patterns)
            
            # Time features
            time_features = self._extract_time_features(df)
            features_dict.update(time_features)
            
            # Volatility features
            volatility_features = self._extract_volatility_features(
                close_prices, high_prices, low_prices, open_prices
            )
            features_dict.update(volatility_features)
            
            # Volume features
            volume_features = self._extract_volume_features(
                close_prices, volume, high_prices, low_prices
            )
            features_dict.update(volume_features)
            
            # Statistical features
            stat_features = self._extract_statistical_features(close_prices)
            features_dict.update(stat_features)
            
            # Generate composite features
            composite_features = self.composite_generator.generate_composite_features(features_dict)
            
            # Add composite_ prefix to all composite features
            composite_features = {f"composite_{k}": v for k, v in composite_features.items()}
            features_dict.update(composite_features)
            
            # Create target variable if requested
            if target_next:
                target = self._create_target_variable(close_prices)
                if target is not None:
                    features_dict['target'] = target
            
            # Check for array length consistency
            feature_lengths = {k: len(v) for k, v in features_dict.items() if isinstance(v, (np.ndarray, list))}
            if len(set(feature_lengths.values())) > 1:
                logger.warning(f"⚠️ Inconsistent feature lengths detected: {feature_lengths}")
                
                # Find the most common length
                from collections import Counter
                lengths_counter = Counter(feature_lengths.values())
                most_common_length = lengths_counter.most_common(1)[0][0]
                
                # Filter features to only include those with the most common length
                features_dict = {k: v for k, v in features_dict.items() 
                           if not isinstance(v, (np.ndarray, list)) or len(v) == most_common_length}
                
                logger.info(f"✂️ Trimmed features to consistent length of {most_common_length}")
            
            # Convert to DataFrame
            feature_arrays = {k: v for k, v in features_dict.items() if v is not None}
            feature_df = pd.DataFrame(feature_arrays)
            
            # Add timestamp
            if 'timestamp' in df.columns:
                feature_df['timestamp'] = df['timestamp'].values[:len(feature_df)]
            
            # First, fill NaN values in features that can be safely interpolated
            numeric_cols = feature_df.select_dtypes(include=['float64', 'int64']).columns
            feature_df[numeric_cols] = feature_df[numeric_cols].interpolate(method='linear').fillna(0)
            
            # For target column, we can't interpolate, so we'll drop rows where target is NaN
            if target_next and 'target' in feature_df.columns:
                feature_df = feature_df.dropna(subset=['target'])
            
            # Check if we still have rows after handling NaNs
            if feature_df.shape[0] == 0:
                logger.error("❌ Empty DataFrame after feature extraction")
                return pd.DataFrame()
            
            logger.info(f"✅ Extracted {feature_df.shape[1]} features from {len(candles)} candles")
            logger.info(f"📊 Feature DataFrame shape: {feature_df.shape}")
            
            return feature_df
            
        except Exception as e:
            logger.error(f"❌ Error extracting features: {str(e)}")
            return pd.DataFrame()
    
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
        """Extract technical indicators using TA-Lib - Enhanced for USD/BRL(OTC)"""
        
        features = {}
        
        try:
            # RSI with multiple periods
            for period in self.rsi_periods:
                rsi = talib.RSI(close_p, timeperiod=period)
                features[f'rsi_{period}'] = rsi
                features[f'rsi_{period}_overbought'] = (rsi > 70).astype(int)
                features[f'rsi_{period}_oversold'] = (rsi < 30).astype(int)
                
                # RSI divergence (price up, RSI down or vice versa)
                if len(close_p) > 5:
                    price_direction = np.sign(close_p[-5:] - close_p[-6:-1])
                    rsi_direction = np.sign(rsi[-5:] - rsi[-6:-1])
                    features[f'rsi_{period}_divergence'] = np.where(
                        price_direction != rsi_direction, 1, 0
                    )[-1] if len(rsi) > 5 else 0
            
            # Moving Averages - Fibonacci-based periods
            for period in self.sma_periods:
                sma = talib.SMA(close_p, timeperiod=period)
                features[f'sma_{period}'] = sma
                features[f'price_above_sma_{period}'] = (close_p > sma).astype(int)
                features[f'sma_{period}_slope'] = np.gradient(sma)
                features[f'sma_{period}_pct_diff'] = (close_p - sma) / sma * 100
            
            for period in self.ema_periods:
                ema = talib.EMA(close_p, timeperiod=period)
                features[f'ema_{period}'] = ema
                features[f'price_above_ema_{period}'] = (close_p > ema).astype(int)
                features[f'ema_{period}_slope'] = np.gradient(ema)
                features[f'ema_{period}_pct_diff'] = (close_p - ema) / ema * 100
            
            # EMA crossovers (short-term crossing long-term)
            for short_period, long_period in [(5, 13), (8, 21), (13, 34)]:
                if short_period in self.ema_periods and long_period in self.ema_periods:
                    short_ema = talib.EMA(close_p, timeperiod=short_period)
                    long_ema = talib.EMA(close_p, timeperiod=long_period)
                    features[f'ema_{short_period}_{long_period}_cross_above'] = (
                        (short_ema > long_ema) & 
                        (np.roll(short_ema, 1) <= np.roll(long_ema, 1))
                    ).astype(int)
                    features[f'ema_{short_period}_{long_period}_cross_below'] = (
                        (short_ema < long_ema) & 
                        (np.roll(short_ema, 1) >= np.roll(long_ema, 1))
                    ).astype(int)
            
            # MACD - Enhanced
            macd, macd_signal, macd_hist = talib.MACD(
                close_p, fastperiod=self.macd_fast, 
                slowperiod=self.macd_slow, signalperiod=self.macd_signal
            )
            features['macd'] = macd
            features['macd_signal'] = macd_signal
            features['macd_histogram'] = macd_hist
            features['macd_bullish'] = (macd > macd_signal).astype(int)
            features['macd_bearish'] = (macd < macd_signal).astype(int)
            
            # MACD histogram crossover (zero line)
            features['macd_hist_cross_above_zero'] = (
                (macd_hist > 0) & (np.roll(macd_hist, 1) <= 0)
            ).astype(int)
            features['macd_hist_cross_below_zero'] = (
                (macd_hist < 0) & (np.roll(macd_hist, 1) >= 0)
            ).astype(int)
            
            # MACD signal line crossover
            features['macd_cross_above_signal'] = (
                (macd > macd_signal) & (np.roll(macd, 1) <= np.roll(macd_signal, 1))
            ).astype(int)
            features['macd_cross_below_signal'] = (
                (macd < macd_signal) & (np.roll(macd, 1) >= np.roll(macd_signal, 1))
            ).astype(int)
            
            # Bollinger Bands - Multiple standard deviations
            for std in self.bb_stds:
                bb_upper, bb_middle, bb_lower = talib.BBANDS(
                    close_p, timeperiod=self.bb_period, nbdevup=std, 
                    nbdevdn=std, matype=0
                )
                features[f'bb_{std}_upper'] = bb_upper
                features[f'bb_{std}_middle'] = bb_middle
                features[f'bb_{std}_lower'] = bb_lower
                features[f'bb_{std}_width'] = (bb_upper - bb_lower) / bb_middle
                features[f'bb_{std}_position'] = (close_p - bb_lower) / (bb_upper - bb_lower + 1e-8)
                features[f'price_above_bb_{std}_upper'] = (close_p > bb_upper).astype(int)
                features[f'price_below_bb_{std}_lower'] = (close_p < bb_lower).astype(int)
                
                # Bollinger Band squeeze (narrowing bands)
                bb_width = (bb_upper - bb_lower) / bb_middle
                features[f'bb_{std}_squeeze'] = (
                    bb_width < np.roll(bb_width, 5)
                ).astype(int)
            
            # Stochastic - Multiple periods
            for k_period, d_period in self.stoch_periods:
                stoch_k, stoch_d = talib.STOCH(
                    high_p, low_p, close_p, fastk_period=k_period, 
                    slowk_period=d_period, slowd_period=d_period
                )
                features[f'stoch_{k_period}_{d_period}_k'] = stoch_k
                features[f'stoch_{k_period}_{d_period}_d'] = stoch_d
                features[f'stoch_{k_period}_{d_period}_overbought'] = (stoch_k > 80).astype(int)
                features[f'stoch_{k_period}_{d_period}_oversold'] = (stoch_k < 20).astype(int)
                features[f'stoch_{k_period}_{d_period}_cross_above'] = (
                    (stoch_k > stoch_d) & (np.roll(stoch_k, 1) <= np.roll(stoch_d, 1))
                ).astype(int)
                features[f'stoch_{k_period}_{d_period}_cross_below'] = (
                    (stoch_k < stoch_d) & (np.roll(stoch_k, 1) >= np.roll(stoch_d, 1))
                ).astype(int)
            
            # ADX (Trend Strength) - Multiple periods
            for period in self.adx_periods:
                adx = talib.ADX(high_p, low_p, close_p, timeperiod=period)
                features[f'adx_{period}'] = adx
                features[f'adx_{period}_strong_trend'] = (adx > 25).astype(int)
                features[f'adx_{period}_very_strong_trend'] = (adx > 50).astype(int)
                
                # Directional Movement Index
                plus_di = talib.PLUS_DI(high_p, low_p, close_p, timeperiod=period)
                minus_di = talib.MINUS_DI(high_p, low_p, close_p, timeperiod=period)
                features[f'plus_di_{period}'] = plus_di
                features[f'minus_di_{period}'] = minus_di
                features[f'di_{period}_bullish'] = (plus_di > minus_di).astype(int)
                features[f'di_{period}_bearish'] = (plus_di < minus_di).astype(int)
                features[f'di_{period}_cross_above'] = (
                    (plus_di > minus_di) & (np.roll(plus_di, 1) <= np.roll(minus_di, 1))
                ).astype(int)
                features[f'di_{period}_cross_below'] = (
                    (plus_di < minus_di) & (np.roll(plus_di, 1) >= np.roll(minus_di, 1))
                ).astype(int)
            
            # Williams %R - Multiple periods
            for period in self.williams_periods:
                williams = talib.WILLR(high_p, low_p, close_p, timeperiod=period)
                features[f'williams_r_{period}'] = williams
                features[f'williams_r_{period}_overbought'] = (williams > -20).astype(int)
                features[f'williams_r_{period}_oversold'] = (williams < -80).astype(int)
            
            # Commodity Channel Index - Multiple periods
            for period in self.cci_periods:
                cci = talib.CCI(high_p, low_p, close_p, timeperiod=period)
                features[f'cci_{period}'] = cci
                features[f'cci_{period}_overbought'] = (cci > 100).astype(int)
                features[f'cci_{period}_oversold'] = (cci < -100).astype(int)
                features[f'cci_{period}_extreme_overbought'] = (cci > 200).astype(int)
                features[f'cci_{period}_extreme_oversold'] = (cci < -200).astype(int)
            
            # Average True Range (Volatility) - Multiple periods
            for period in self.atr_periods:
                atr = talib.ATR(high_p, low_p, close_p, timeperiod=period)
                features[f'atr_{period}'] = atr
                features[f'atr_{period}_ratio'] = atr / close_p
                
                # ATR-based volatility state
                atr_sma = talib.SMA(atr, timeperiod=10)
                features[f'atr_{period}_increasing'] = (atr > atr_sma).astype(int)
            
            # Ichimoku Cloud indicators - Specifically effective for USD/BRL
            if len(close_p) >= 52:  # Need enough data for Ichimoku
                # Tenkan-sen (Conversion Line): (9-period high + 9-period low)/2
                period9_high = talib.MAX(high_p, timeperiod=9)
                period9_low = talib.MIN(low_p, timeperiod=9)
                tenkan_sen = (period9_high + period9_low) / 2
                
                # Kijun-sen (Base Line): (26-period high + 26-period low)/2
                period26_high = talib.MAX(high_p, timeperiod=26)
                period26_low = talib.MIN(low_p, timeperiod=26)
                kijun_sen = (period26_high + period26_low) / 2
                
                # Senkou Span A (Leading Span A): (Tenkan-sen + Kijun-sen)/2
                senkou_span_a = (tenkan_sen + kijun_sen) / 2
                
                # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2
                period52_high = talib.MAX(high_p, timeperiod=52)
                period52_low = talib.MIN(low_p, timeperiod=52)
                senkou_span_b = (period52_high + period52_low) / 2
                
                features['tenkan_sen'] = tenkan_sen
                features['kijun_sen'] = kijun_sen
                features['senkou_span_a'] = senkou_span_a
                features['senkou_span_b'] = senkou_span_b
                features['price_above_cloud'] = ((close_p > senkou_span_a) & (close_p > senkou_span_b)).astype(int)
                features['price_below_cloud'] = ((close_p < senkou_span_a) & (close_p < senkou_span_b)).astype(int)
                features['cloud_bullish'] = (senkou_span_a > senkou_span_b).astype(int)
                features['tenkan_cross_kijun_above'] = ((tenkan_sen > kijun_sen) & (np.roll(tenkan_sen, 1) <= np.roll(kijun_sen, 1))).astype(int)
                features['tenkan_cross_kijun_below'] = ((tenkan_sen < kijun_sen) & (np.roll(tenkan_sen, 1) >= np.roll(kijun_sen, 1))).astype(int)
            
            # USD/BRL specific indicators
            if self.is_optimized_for_usd_brl:
                # Parabolic SAR - Effective for trending markets
                psar = talib.SAR(high_p, low_p, acceleration=0.02, maximum=0.2)
                features['psar'] = psar
                features['price_above_psar'] = (close_p > psar).astype(int)
                features['psar_reversal_bullish'] = ((close_p > psar) & (np.roll(close_p, 1) <= np.roll(psar, 1))).astype(int)
                features['psar_reversal_bearish'] = ((close_p < psar) & (np.roll(close_p, 1) >= np.roll(psar, 1))).astype(int)
                
                # Money Flow Index - Volume-weighted RSI
                if 'volume' in locals() and len(volume) == len(close_p):
                    features['mfi'] = talib.MFI(high_p, low_p, close_p, volume, timeperiod=14)
                    features['mfi_overbought'] = (features['mfi'] > 80).astype(int)
                    features['mfi_oversold'] = (features['mfi'] < 20).astype(int)
                
                # On-Balance Volume
                if 'volume' in locals() and len(volume) == len(close_p):
                    features['obv'] = talib.OBV(close_p, volume)
                    features['obv_sma'] = talib.SMA(features['obv'], timeperiod=20)
                    features['obv_trend_up'] = (features['obv'] > features['obv_sma']).astype(int)
                
                # Aroon Oscillator - Trend direction and strength
                aroon_up, aroon_down = talib.AROON(high_p, low_p, timeperiod=25)
                features['aroon_up'] = aroon_up
                features['aroon_down'] = aroon_down
                features['aroon_oscillator'] = aroon_up - aroon_down
                features['aroon_bullish'] = (aroon_up > 70).astype(int)
                features['aroon_bearish'] = (aroon_down > 70).astype(int)
                
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
        """Extract time-based features - Enhanced for USD/BRL(OTC) market patterns"""
        
        features = {}
        
        # Convert timestamp to datetime if it's not already
        timestamps = pd.to_datetime(df['timestamp'])
        
        # Hour of day (0-23)
        features['hour'] = timestamps.dt.hour.values
        
        # Market sessions - Specific to USD/BRL trading patterns
        features['is_asian_session'] = ((timestamps.dt.hour >= self.market_session_hours['asian'][0]) & 
                                      (timestamps.dt.hour < self.market_session_hours['asian'][1])).astype(int)
        
        features['is_european_session'] = ((timestamps.dt.hour >= self.market_session_hours['european'][0]) & 
                                         (timestamps.dt.hour < self.market_session_hours['european'][1])).astype(int)
        
        features['is_american_session'] = ((timestamps.dt.hour >= self.market_session_hours['american'][0]) & 
                                         (timestamps.dt.hour < self.market_session_hours['american'][1])).astype(int)
        
        # Overlap periods (typically higher volatility)
        features['is_euro_american_overlap'] = ((timestamps.dt.hour >= 13) & 
                                              (timestamps.dt.hour < 16)).astype(int)
        
        # Brazil market hours (BRL specific) - UTC+7 timezone
        features['is_brazil_market_open'] = ((timestamps.dt.hour >= self.brazil_market_hours['open']) & 
                                           (timestamps.dt.hour < self.brazil_market_hours['close'])).astype(int)
        
        # Brazil market peak hours (highest liquidity)
        features['is_brazil_peak_hours'] = ((timestamps.dt.hour >= self.brazil_market_hours['peak'][0]) & 
                                           (timestamps.dt.hour < self.brazil_market_hours['peak'][1])).astype(int)
        
        # Pre and post Brazil market hours
        features['is_pre_brazil_open'] = ((timestamps.dt.hour >= (self.brazil_market_hours['open'] - 2)) & 
                                         (timestamps.dt.hour < self.brazil_market_hours['open'])).astype(int)
        
        features['is_post_brazil_close'] = ((timestamps.dt.hour >= self.brazil_market_hours['close']) & 
                                           (timestamps.dt.hour < (self.brazil_market_hours['close'] + 2))).astype(int)
        
        # Day of week (0=Monday, 6=Sunday)
        features['day_of_week'] = timestamps.dt.dayofweek.values
        features['is_weekend'] = (timestamps.dt.dayofweek >= 5).astype(int)
        
        # Monday and Friday effects (often show different patterns)
        features['is_monday'] = (timestamps.dt.dayofweek == 0).astype(int)
        features['is_friday'] = (timestamps.dt.dayofweek == 4).astype(int)
        
        # Month and quarter
        features['month'] = timestamps.dt.month.values
        features['quarter'] = timestamps.dt.quarter.values
        
        # Beginning/end of month effects (often important for USD/BRL)
        features['is_month_start'] = (timestamps.dt.day <= 5).astype(int)
        features['is_month_end'] = (timestamps.dt.day >= 25).astype(int)
        
        # Time of day segments - Adjusted for Bangkok timezone (UTC+7)
        # Convert UTC hour to Bangkok hour for local time features
        bangkok_hour = (timestamps.dt.hour + 7) % 24
        
        features['is_morning'] = ((bangkok_hour >= 8) & (bangkok_hour < 12)).astype(int)
        features['is_afternoon'] = ((bangkok_hour >= 12) & (bangkok_hour < 17)).astype(int)
        features['is_evening'] = ((bangkok_hour >= 17) & (bangkok_hour < 21)).astype(int)
        features['is_night'] = ((bangkok_hour >= 21) | (bangkok_hour < 8)).astype(int)
        
        # Bangkok-specific time features
        features['is_bangkok_business_hours'] = ((bangkok_hour >= 9) & (bangkok_hour < 18)).astype(int)
        features['is_bangkok_lunch_hours'] = ((bangkok_hour >= 12) & (bangkok_hour < 13)).astype(int)
        
        # Day of month (can capture patterns around salary payments, etc.)
        features['day_of_month'] = timestamps.dt.day.values
        features['day_of_month_sin'] = np.sin(2 * np.pi * timestamps.dt.day.values / 31)
        features['day_of_month_cos'] = np.cos(2 * np.pi * timestamps.dt.day.values / 31)
        
        # Hour cyclical features (better than raw hour)
        features['hour_sin'] = np.sin(2 * np.pi * timestamps.dt.hour.values / 24)
        features['hour_cos'] = np.cos(2 * np.pi * timestamps.dt.hour.values / 24)
        
        # Day of week cyclical features
        features['day_of_week_sin'] = np.sin(2 * np.pi * timestamps.dt.dayofweek.values / 7)
        features['day_of_week_cos'] = np.cos(2 * np.pi * timestamps.dt.dayofweek.values / 7)
        
        return features
    
    def _extract_volatility_features(self, close_p: np.ndarray, high_p: np.ndarray, 
                                   low_p: np.ndarray, open_p: np.ndarray = None) -> Dict[str, np.ndarray]:
        """Extract volatility-based features - Enhanced for USD/BRL(OTC)"""
        
        features = {}
        
        try:
            # Historical volatility over different periods - Fibonacci-based
            for period in [5, 8, 13, 21, 34]:
                if len(close_p) > period:
                    # Log returns
                    returns = np.diff(np.log(close_p))
                    
                    # Standard volatility (standard deviation of returns)
                    rolling_vol = pd.Series(returns).rolling(window=period).std().values
                    features[f'volatility_{period}'] = np.concatenate([[np.nan], rolling_vol])
                    
                    # Annualized volatility (standard in financial analysis)
                    annualized_vol = rolling_vol * np.sqrt(365)  # Assuming daily data
                    features[f'annualized_volatility_{period}'] = np.concatenate([[np.nan], annualized_vol])
                    
                    # Volatility ratio (current vs historical)
                    if period > 8:
                        short_vol = pd.Series(returns).rolling(window=5).std().values
                        vol_ratio = short_vol / (rolling_vol + 1e-8)  # Avoid division by zero
                        features[f'volatility_ratio_5_{period}'] = np.concatenate([[np.nan], vol_ratio])
            
            # True Range and ATR
            if len(high_p) > 1:
                tr1 = high_p[1:] - low_p[1:]
                tr2 = np.abs(high_p[1:] - close_p[:-1])
                tr3 = np.abs(low_p[1:] - close_p[:-1])
                tr = np.maximum(tr1, np.maximum(tr2, tr3))
                features['true_range'] = np.concatenate([[np.nan], tr])
                
                # Normalized True Range (as percentage of price)
                norm_tr = tr / close_p[1:]
                features['normalized_true_range'] = np.concatenate([[np.nan], norm_tr])
                
                # ATR for multiple periods
                for period in [5, 8, 13, 21]:
                    if len(tr) >= period:
                        atr = pd.Series(tr).rolling(window=period).mean().values
                        features[f'atr_{period}'] = np.concatenate([[np.nan], atr])
                        
                        # Normalized ATR
                        norm_atr = atr / close_p[1:]
                        features[f'normalized_atr_{period}'] = np.concatenate([[np.nan], norm_atr])
                        
                        # ATR percent of price
                        atr_pct = atr / close_p[1:] * 100
                        features[f'atr_pct_{period}'] = np.concatenate([[np.nan], atr_pct])
            else:
                features['true_range'] = np.array([np.nan] * len(high_p))
            
            # Volatility breakouts (significant increase in volatility)
            if len(close_p) > 30:
                vol_20 = pd.Series(returns).rolling(window=20).std().values
                vol_5 = pd.Series(returns).rolling(window=5).std().values
                
                # Volatility breakout when short-term vol > 1.5x long-term vol
                vol_breakout = (vol_5 / (vol_20 + 1e-8) > 1.5).astype(int)
                features['volatility_breakout'] = np.concatenate([[np.nan], vol_breakout])
            
            # Garman-Klass volatility (uses OHLC data, better than close-to-close)
            if len(close_p) > 1 and len(open_p) > 1:
                log_hl = np.log(high_p[1:] / low_p[1:]) ** 2
                log_co = np.log(close_p[1:] / open_p[1:]) ** 2
                gk_vol = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
                features['garman_klass_volatility'] = np.concatenate([[np.nan], gk_vol])
                
                # Rolling Garman-Klass volatility
                for period in [5, 10, 20]:
                    if len(gk_vol) >= period:
                        rolling_gk = pd.Series(gk_vol).rolling(window=period).mean().values
                        features[f'garman_klass_volatility_{period}'] = np.concatenate([[np.nan], rolling_gk])
            
            # Volatility regime detection
            if len(close_p) > 50:
                vol_50 = pd.Series(returns).rolling(window=50).std().values
                vol_10 = pd.Series(returns).rolling(window=10).std().values
                
                # High volatility regime
                features['high_volatility_regime'] = (vol_10 > 1.2 * vol_50).astype(int)
                
                # Low volatility regime
                features['low_volatility_regime'] = (vol_10 < 0.8 * vol_50).astype(int)
                
                # Volatility trend
                vol_trend = np.sign(vol_10 - np.roll(vol_10, 5))
                features['volatility_trend'] = vol_trend
            
            # USD/BRL specific volatility features
            if self.is_optimized_for_usd_brl:
                # BRL is known for periodic volatility spikes
                if len(close_p) > 30:
                    # Detect extreme moves (>3 standard deviations)
                    returns_std = np.std(returns)
                    extreme_move = (np.abs(returns) > 3 * returns_std).astype(int)
                    features['extreme_move'] = np.concatenate([[0], extreme_move])
                    
                    # Rolling count of extreme moves
                    rolling_extreme = pd.Series(extreme_move).rolling(window=20).sum().values
                    features['rolling_extreme_moves'] = np.concatenate([[np.nan], rolling_extreme])
                    
                    # Volatility after Brazilian market open
                    # This would be better with actual time features, but as a proxy:
                    if len(returns) > 20:
                        features['post_brazil_open_volatility'] = np.roll(vol_5, -2)  # Shifted to capture effect after open
        
        except Exception as e:
            logger.error(f"Error calculating volatility features: {str(e)}")
        
        return features
    
    def _extract_volume_features(self, close_p: np.ndarray, volume: np.ndarray, 
                                high_p: np.ndarray = None, low_p: np.ndarray = None) -> Dict[str, np.ndarray]:
        """Extract volume-based features - Enhanced for USD/BRL(OTC)"""
        
        features = {}
        
        try:
            # Volume moving averages - Fibonacci-based periods
            for period in [5, 8, 13, 21, 34]:
                features[f'volume_sma_{period}'] = talib.SMA(volume, timeperiod=period)
            
            # Volume ratios (current volume relative to moving averages)
            for period in [5, 8, 13, 21, 34]:
                vol_sma = features[f'volume_sma_{period}']
                features[f'volume_ratio_{period}'] = volume / (vol_sma + 1e-8)  # Avoid division by zero
            
            # Relative volume (today's volume compared to recent average)
            features['relative_volume'] = volume / (talib.SMA(volume, timeperiod=20) + 1e-8)
            
            # Volume trend
            vol_trend = np.sign(talib.SMA(volume, timeperiod=5) - talib.SMA(volume, timeperiod=20))
            # Handle NaN values before casting to int
            vol_trend = np.nan_to_num(vol_trend, nan=0.0)
            features['volume_trend'] = vol_trend.astype(int)
            
            # On-Balance Volume (OBV)
            features['obv'] = talib.OBV(close_p, volume)
            features['obv_sma'] = talib.SMA(features['obv'], timeperiod=20)
            # Handle NaN values before comparison and casting to int
            obv = np.nan_to_num(features['obv'], nan=0.0)
            obv_sma = np.nan_to_num(features['obv_sma'], nan=0.0)
            features['obv_trend'] = (obv > obv_sma).astype(int)
            
            # Chaikin Money Flow
            try:
                if len(close_p) > 20 and high_p is not None and low_p is not None:
                    
                    # Money Flow Multiplier
                    mfm = ((close_p - low_p) - (high_p - close_p)) / (high_p - low_p + 1e-8)
                    
                    # Money Flow Volume
                    mfv = mfm * volume
                    
                    # Chaikin Money Flow (20-period)
                    cmf = pd.Series(mfv).rolling(window=20).sum().values / (
                        pd.Series(volume).rolling(window=20).sum().values + 1e-8
                    )
                    features['chaikin_money_flow'] = cmf
                    features['cmf_positive'] = (cmf > 0).astype(int)
            except Exception as e:
                logger.error(f"Error calculating Chaikin Money Flow: {str(e)}")
            
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
                    
                    # Positive correlation (price and volume move together)
                    features['positive_pv_correlation'] = (corr_array > 0.5).astype(int)
                    
                    # Negative correlation (price and volume move in opposite directions)
                    features['negative_pv_correlation'] = (corr_array < -0.5).astype(int)
            except Exception as e:
                logger.error(f"Error calculating price-volume correlation: {str(e)}")
            
            # Volume spikes (unusual volume)
            vol_mean = np.mean(volume)
            vol_std = np.std(volume)
            features['volume_spike'] = (volume > (vol_mean + 2 * vol_std)).astype(int)
            
            # Volume consistency (low standard deviation relative to mean)
            for period in [5, 10, 20]:
                if len(volume) > period:
                    vol_rolling_std = pd.Series(volume).rolling(window=period).std().values
                    vol_rolling_mean = pd.Series(volume).rolling(window=period).mean().values
                    features[f'volume_consistency_{period}'] = 1 - (vol_rolling_std / (vol_rolling_mean + 1e-8))
            
            # Volume-weighted average price (VWAP)
            typical_price = close_p  # Simplified, ideally would be (high + low + close) / 3
            vwap_num = np.cumsum(typical_price * volume)
            vwap_den = np.cumsum(volume)
            features['vwap'] = vwap_num / (vwap_den + 1e-8)
            features['price_above_vwap'] = (close_p > features['vwap']).astype(int)
            
            # USD/BRL specific volume features
            if hasattr(self, 'is_optimized_for_usd_brl') and self.is_optimized_for_usd_brl:
                # Volume surge during Brazilian market hours
                # This is a placeholder - would be better with actual time data
                features['brazil_market_volume_ratio'] = np.roll(features['relative_volume'], -2)
                
                # Detect climax volume (potential reversal points)
                if len(volume) > 20:
                    max_vol_20 = pd.Series(volume).rolling(window=20).max().values
                    features['climax_volume'] = (volume > 0.9 * max_vol_20).astype(int)
                
        except Exception as e:
            logger.error(f"Error calculating volume features: {str(e)}")
        
        return features
    
    def _extract_statistical_features(self, close_p: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract statistical features - Enhanced for USD/BRL(OTC)"""
        
        features = {}
        
        try:
            # Calculate returns for statistical features
            returns = np.diff(np.log(close_p))
            returns_series = pd.Series(returns)
            
            # Pad returns to match original length
            padded_returns = np.concatenate([[np.nan], returns])
            
            # Rolling statistics - Fibonacci-based windows
            close_series = pd.Series(close_p)
            
            for window in [5, 8, 13, 21, 34]:
                if len(close_p) > window:
                    try:
                        # Standard deviation
                        std_values = close_series.rolling(window=window).std().values
                        if len(std_values) == len(close_p):
                            features[f'std_{window}'] = std_values
                            
                            # Normalized standard deviation (coefficient of variation)
                            rolling_mean = close_series.rolling(window=window).mean().values
                            features[f'cv_{window}'] = std_values / (rolling_mean + 1e-8)
                    except Exception as e:
                        logger.error(f"Error calculating std for window {window}: {str(e)}")
                    
                    try:
                        # Skewness
                        skew_values = close_series.rolling(window=window).skew().values
                        if len(skew_values) == len(close_p):
                            features[f'skew_{window}'] = skew_values
                            
                            # Skewness direction (positive or negative)
                            features[f'positive_skew_{window}'] = (skew_values > 0).astype(int)
                    except Exception as e:
                        logger.error(f"Error calculating skew for window {window}: {str(e)}")
                    
                    try:
                        # Kurtosis
                        kurt_values = close_series.rolling(window=window).kurt().values
                        if len(kurt_values) == len(close_p):
                            features[f'kurtosis_{window}'] = kurt_values
                            
                            # Excess kurtosis (>3 indicates fat tails)
                            features[f'excess_kurtosis_{window}'] = (kurt_values > 3).astype(int)
                    except Exception as e:
                        logger.error(f"Error calculating kurtosis for window {window}: {str(e)}")
            
            # Return-based statistics (if we have returns)
            if len(returns) > 20:
                # Overall return statistics
                features['mean_return'] = np.mean(padded_returns)
                features['std_return'] = np.std(padded_returns)
                
                # Rolling return statistics
                for window in [5, 10, 20]:
                    # Mean return
                    rolling_mean = pd.Series(padded_returns).rolling(window=window).mean().values
                    features[f'mean_return_{window}'] = rolling_mean
                    
                    # Return volatility
                    rolling_std = pd.Series(padded_returns).rolling(window=window).std().values
                    features[f'return_volatility_{window}'] = rolling_std
                    
                    # Sharpe ratio (simplified, without risk-free rate)
                    features[f'sharpe_ratio_{window}'] = rolling_mean / (rolling_std + 1e-8)
                
                # Return autocorrelation (serial correlation)
                for lag in [1, 2, 3, 5]:
                    if len(returns) > lag + 10:
                        try:
                            # Calculate autocorrelation for each rolling window
                            autocorr = np.zeros(len(returns))
                            for i in range(10, len(returns)):
                                window_returns = returns[max(0, i-20):i]
                                if len(window_returns) > lag + 5:
                                    # Calculate autocorrelation
                                    try:
                                        ac = np.corrcoef(window_returns[lag:], window_returns[:-lag])[0, 1]
                                        if not np.isnan(ac) and not np.isinf(ac):
                                            autocorr[i] = ac
                                    except:
                                        pass
                            
                            # Replace NaN values with 0
                            autocorr = np.nan_to_num(autocorr, nan=0.0)
                            
                            # Ensure length matches close_p
                            if len(autocorr) < len(close_p):
                                # Pad with zeros at the beginning
                                autocorr = np.pad(autocorr, (len(close_p) - len(autocorr), 0), 'constant')
                            elif len(autocorr) > len(close_p):
                                # Trim to match length
                                autocorr = autocorr[:len(close_p)]
                                
                            features[f'return_autocorr_{lag}'] = autocorr
                        except Exception as e:
                            logger.warning(f"Error calculating autocorrelation for lag {lag}: {str(e)}")
            
            # Hurst exponent (measure of long-term memory)
            if len(close_p) > 100:
                try:
                    # Calculate Hurst exponent over rolling windows
                    hurst_values = np.zeros(len(close_p))
                    
                    # Function to calculate Hurst exponent
                    def hurst_calc(price_array):
                        # Convert price to returns
                        returns = np.diff(np.log(price_array))
                        if len(returns) < 20:
                            return 0.5  # Default to random walk
                            
                        # Calculate various lags
                        lags = range(2, min(20, len(returns) // 4))
                        tau = [np.sqrt(np.std(np.subtract(returns[lag:], returns[:-lag]))) for lag in lags]
                        
                        # Avoid log(0) errors
                        if any(t == 0 for t in tau) or len(lags) < 2:
                            return 0.5
                            
                        # Linear regression to estimate Hurst
                        m = np.polyfit(np.log(lags), np.log(tau), 1)
                        hurst = m[0] / 2.0
                        return hurst
                    
                    # Calculate for rolling windows
                    window_size = 100
                    for i in range(window_size, len(close_p)):
                        window = close_p[i-window_size:i]
                        try:
                            hurst_values[i] = hurst_calc(window)
                        except:
                            hurst_values[i] = 0.5
                    
                    # Pad with default value (0.5 = random walk)
                    hurst_values[:window_size] = 0.5
                    
                    # Ensure array is the right length
                    if len(hurst_values) != len(close_p):
                        # Adjust array length to match close_p
                        if len(hurst_values) < len(close_p):
                            # Pad with default value
                            hurst_values = np.pad(hurst_values, (0, len(close_p) - len(hurst_values)), 
                                                'constant', constant_values=0.5)
                        else:
                            # Trim to match length
                            hurst_values = hurst_values[:len(close_p)]
                    
                    # Replace any NaN or inf values
                    hurst_values = np.nan_to_num(hurst_values, nan=0.5, posinf=1.0, neginf=0.0)
                    
                    features['hurst_exponent'] = hurst_values
                    
                    # Classify market regime based on Hurst
                    # Use np.nan_to_num to handle any NaN values before casting to int
                    mean_reverting = np.nan_to_num(hurst_values < 0.4, nan=0.0).astype(int)
                    random_walk = np.nan_to_num((hurst_values >= 0.4) & (hurst_values <= 0.6), nan=0.0).astype(int)
                    trending = np.nan_to_num(hurst_values > 0.6, nan=0.0).astype(int)
                    
                    features['mean_reverting'] = mean_reverting
                    features['random_walk'] = random_walk
                    features['trending'] = trending
                except Exception as e:
                    logger.error(f"Error calculating Hurst exponent: {str(e)}")
            
            # USD/BRL specific statistical features
            if hasattr(self, 'is_optimized_for_usd_brl') and self.is_optimized_for_usd_brl:
                # BRL often exhibits higher volatility during certain periods
                # Volatility clustering detection
                if len(returns) > 20:
                    # ARCH effect (volatility clustering)
                    try:
                        squared_returns = padded_returns ** 2
                        lagged_squared_returns = np.roll(squared_returns, 1)
                        lagged_squared_returns[0] = 0
                        
                        # Rolling correlation between squared returns and lagged squared returns
                        arch_effect = pd.Series(squared_returns).rolling(window=20).corr(
                            pd.Series(lagged_squared_returns)
                        ).values
                        
                        # Handle NaN values
                        arch_effect = np.nan_to_num(arch_effect, nan=0.0)
                        
                        # Ensure length matches close_p
                        if len(arch_effect) != len(close_p):
                            if len(arch_effect) < len(close_p):
                                # Pad with zeros
                                arch_effect = np.pad(arch_effect, (0, len(close_p) - len(arch_effect)), 
                                                   'constant', constant_values=0.0)
                            else:
                                # Trim to match length
                                arch_effect = arch_effect[:len(close_p)]
                        
                        # Significant volatility clustering
                        features['arch_effect'] = arch_effect
                        vol_clustering = np.nan_to_num(arch_effect > 0.2, nan=0.0).astype(int)
                        features['volatility_clustering'] = vol_clustering
                    except Exception as e:
                        logger.warning(f"Error calculating ARCH effect: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error calculating statistical features: {str(e)}")
        
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
    
    async def prepare_training_data(self, trading_pair: str = "BRLUSD", 
                                  limit: int = 1000) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare training data with features and targets
        
        Returns:
            Tuple of (features_df, targets_df)
        """
        
        logger.info(f"🔄 Preparing training data for {trading_pair} (period=60s, strict)")
        
        # Connect to MongoDB if not connected
        if not self.mongodb.is_connected:
            await self.mongodb.connect()
        
        # Enforce standard trading pairs only
        allowed_pairs = {"BRLUSD", "BRLUSD_otc"}
        if trading_pair not in allowed_pairs:
            logger.error(
                f"❌ Invalid trading_pair '{trading_pair}'. Use 'BRLUSD' or 'BRLUSD_otc' only."
            )
            return pd.DataFrame(), pd.DataFrame()

        # Single strict fetch via validated DB method (period=60 enforced there)
        try:
            candles = await self.mongodb.get_candles_for_training(limit=limit, trading_pair=trading_pair)
        except Exception as e:
            logger.error(f"❌ Error fetching candles for {trading_pair}: {str(e)}")
            return pd.DataFrame(), pd.DataFrame()
        
        if len(candles) < 50:
            logger.error(f"Insufficient data for {trading_pair} (period=60): {len(candles)} candles")
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
        """Get list of all possible feature names for importance analysis - Enhanced for USD/BRL(OTC)"""
        
        feature_names = []
        
        # Basic features
        basic_features = [
            'price_change', 'price_change_pct', 'high_low_spread', 'high_low_spread_pct',
            'body_ratio', 'upper_wick_ratio', 'lower_wick_ratio', 'direction'
        ]
        feature_names.extend(basic_features)
        
        # Technical indicators - Enhanced for USD/BRL(OTC)
        for period in self.rsi_periods:
            feature_names.extend([
                f'rsi_{period}', f'rsi_{period}_overbought', f'rsi_{period}_oversold',
                f'rsi_{period}_divergence'
            ])
        
        # Moving averages - Fibonacci-based
        for period in self.sma_periods:
            feature_names.extend([
                f'sma_{period}', f'price_above_sma_{period}', f'sma_{period}_slope',
                f'sma_{period}_pct_diff'
            ])
        
        for period in self.ema_periods:
            feature_names.extend([
                f'ema_{period}', f'price_above_ema_{period}', f'ema_{period}_slope',
                f'ema_{period}_pct_diff'
            ])
        
        # EMA crossovers
        for short_period, long_period in [(5, 13), (8, 21), (13, 34)]:
            if short_period in self.ema_periods and long_period in self.ema_periods:
                feature_names.extend([
                    f'ema_{short_period}_{long_period}_cross_above',
                    f'ema_{short_period}_{long_period}_cross_below'
                ])
        
        # MACD - Enhanced
        feature_names.extend([
            'macd', 'macd_signal', 'macd_histogram', 'macd_bullish', 'macd_bearish',
            'macd_hist_cross_above_zero', 'macd_hist_cross_below_zero',
            'macd_cross_above_signal', 'macd_cross_below_signal'
        ])
        
        # Bollinger Bands - Multiple standard deviations
        for std in self.bb_stds:
            feature_names.extend([
                f'bb_{std}_upper', f'bb_{std}_middle', f'bb_{std}_lower',
                f'bb_{std}_width', f'bb_{std}_position',
                f'price_above_bb_{std}_upper', f'price_below_bb_{std}_lower',
                f'bb_{std}_squeeze'
            ])
        
        # Stochastic - Multiple periods
        for k_period, d_period in self.stoch_periods:
            feature_names.extend([
                f'stoch_{k_period}_{d_period}_k', f'stoch_{k_period}_{d_period}_d',
                f'stoch_{k_period}_{d_period}_overbought', f'stoch_{k_period}_{d_period}_oversold',
                f'stoch_{k_period}_{d_period}_cross_above', f'stoch_{k_period}_{d_period}_cross_below'
            ])
        
        # ADX - Multiple periods
        for period in self.adx_periods:
            feature_names.extend([
                f'adx_{period}', f'adx_{period}_strong_trend', f'adx_{period}_very_strong_trend',
                f'plus_di_{period}', f'minus_di_{period}',
                f'di_{period}_bullish', f'di_{period}_bearish',
                f'di_{period}_cross_above', f'di_{period}_cross_below'
            ])
        
        # Williams %R - Multiple periods
        for period in self.williams_periods:
            feature_names.extend([
                f'williams_r_{period}', f'williams_r_{period}_overbought', f'williams_r_{period}_oversold'
            ])
        
        # CCI - Multiple periods
        for period in self.cci_periods:
            feature_names.extend([
                f'cci_{period}', f'cci_{period}_overbought', f'cci_{period}_oversold',
                f'cci_{period}_extreme_overbought', f'cci_{period}_extreme_oversold'
            ])
        
        # ATR - Multiple periods
        for period in self.atr_periods:
            feature_names.extend([
                f'atr_{period}', f'atr_{period}_ratio', f'atr_{period}_increasing'
            ])
        
        # Ichimoku Cloud
        feature_names.extend([
            'tenkan_sen', 'kijun_sen', 'senkou_span_a', 'senkou_span_b',
            'price_above_cloud', 'price_below_cloud', 'cloud_bullish',
            'tenkan_cross_kijun_above', 'tenkan_cross_kijun_below'
        ])
        
        # USD/BRL specific indicators
        feature_names.extend([
            'psar', 'price_above_psar', 'psar_reversal_bullish', 'psar_reversal_bearish',
            'mfi', 'mfi_overbought', 'mfi_oversold',
            'obv', 'obv_sma', 'obv_trend_up',
            'aroon_up', 'aroon_down', 'aroon_oscillator', 'aroon_bullish', 'aroon_bearish'
        ])
        
        # Pattern features
        for period in self.lookback_periods:
            feature_names.extend([f'momentum_{period}', f'roc_{period}'])
        
        feature_names.extend(['distance_to_resistance', 'distance_to_support'])
        
        # Time features - Enhanced for USD/BRL(OTC)
        feature_names.extend([
            'hour', 'is_asian_session', 'is_european_session', 'is_american_session',
            'is_euro_american_overlap', 'is_brazil_market_open',
            'day_of_week', 'is_weekend', 'is_monday', 'is_friday',
            'month', 'quarter', 'is_month_start', 'is_month_end',
            'is_morning', 'is_afternoon', 'is_evening', 'is_night',
            'day_of_month', 'day_of_month_sin', 'day_of_month_cos',
            'hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos'
        ])
        
        # Volatility features - Enhanced for USD/BRL(OTC)
        for period in [5, 8, 13, 21, 34]:
            feature_names.extend([
                f'volatility_{period}', f'annualized_volatility_{period}'
            ])
            
            if period > 8:
                feature_names.append(f'volatility_ratio_5_{period}')
        
        feature_names.extend([
            'true_range', 'normalized_true_range',
            'volatility_breakout', 'garman_klass_volatility',
            'high_volatility_regime', 'low_volatility_regime', 'volatility_trend',
            'extreme_move', 'rolling_extreme_moves', 'post_brazil_open_volatility'
        ])
        
        # ATR features
        for period in [5, 8, 13, 21]:
            feature_names.extend([
                f'atr_{period}', f'normalized_atr_{period}', f'atr_pct_{period}'
            ])
        
        # Garman-Klass volatility
        for period in [5, 10, 20]:
            feature_names.append(f'garman_klass_volatility_{period}')
        
        # Volume features - Enhanced for USD/BRL(OTC)
        for period in [5, 8, 13, 21, 34]:
            feature_names.extend([
                f'volume_sma_{period}', f'volume_ratio_{period}'
            ])
        
        feature_names.extend([
            'relative_volume', 'volume_trend', 'obv', 'obv_sma', 'obv_trend',
            'chaikin_money_flow', 'cmf_positive',
            'price_volume_correlation', 'positive_pv_correlation', 'negative_pv_correlation',
            'volume_spike', 'vwap', 'price_above_vwap',
            'brazil_market_volume_ratio', 'climax_volume'
        ])
        
        # Volume consistency
        for period in [5, 10, 20]:
            feature_names.append(f'volume_consistency_{period}')
        
        # Statistical features - Enhanced for USD/BRL(OTC)
        for window in [5, 8, 13, 21, 34]:
            feature_names.extend([
                f'std_{window}', f'cv_{window}',
                f'skew_{window}', f'positive_skew_{window}',
                f'kurtosis_{window}', f'excess_kurtosis_{window}'
            ])
        
        # Return-based statistics
        feature_names.extend(['mean_return', 'std_return'])
        
        for window in [5, 10, 20]:
            feature_names.extend([
                f'mean_return_{window}', f'return_volatility_{window}', f'sharpe_ratio_{window}'
            ])
        
        # Return autocorrelation
        for lag in [1, 2, 3, 5]:
            feature_names.append(f'return_autocorr_{lag}')
        
        # Market regime features
        feature_names.extend([
            'hurst_exponent', 'mean_reverting', 'random_walk', 'trending',
            'arch_effect', 'volatility_clustering'
        ])
        
        return feature_names 