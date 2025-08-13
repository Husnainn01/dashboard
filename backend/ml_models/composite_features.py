"""
Composite Feature Engineering Module for OTC Predictor
Creates advanced composite features by combining multiple technical indicators
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class CompositeFeatureGenerator:
    """
    Creates advanced composite features by combining multiple technical indicators
    to improve prediction accuracy for trading models
    """
    
    def __init__(self):
        """Initialize the composite feature generator"""
        pass
        
    def generate_composite_features(self, features: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        Generate composite features from individual technical indicators
        
        Args:
            features: Dictionary of feature arrays from FeatureEngineer
            
        Returns:
            Dictionary of composite feature arrays
        """
        composite_features = {}
        
        try:
            # RSI + Bollinger Band composite (oversold + near lower band)
            if 'rsi_14' in features and 'bb_2_position' in features:
                # RSI oversold (< 30) and price near lower BB (position < 0.2)
                composite_features['rsi_bb_oversold'] = np.where(
                    (features['rsi_14'] < 30) & (features['bb_2_position'] < 0.2),
                    1, 0
                )
                
                # RSI overbought (> 70) and price near upper BB (position > 0.8)
                composite_features['rsi_bb_overbought'] = np.where(
                    (features['rsi_14'] > 70) & (features['bb_2_position'] > 0.8),
                    1, 0
                )
            
            # MACD crossover + volume spike
            if all(k in features for k in ['macd_cross_above_signal', 'volume_spike']):
                # Bullish signal: MACD crosses above signal with volume spike
                composite_features['macd_volume_bullish'] = np.where(
                    features['macd_cross_above_signal'] & features['volume_spike'],
                    1, 0
                )
                
            if all(k in features for k in ['macd_cross_below_signal', 'volume_spike']):
                # Bearish signal: MACD crosses below signal with volume spike
                composite_features['macd_volume_bearish'] = np.where(
                    features['macd_cross_below_signal'] & features['volume_spike'],
                    1, 0
                )
            
            # EMA crossover + RSI confirmation
            if all(k in features for k in ['ema_8_21_cross_above', 'rsi_14']):
                # Bullish signal: EMA 8 crosses above EMA 21 with RSI > 50
                composite_features['ema_rsi_bullish'] = np.where(
                    features['ema_8_21_cross_above'] & (features['rsi_14'] > 50),
                    1, 0
                )
                
            if all(k in features for k in ['ema_8_21_cross_below', 'rsi_14']):
                # Bearish signal: EMA 8 crosses below EMA 21 with RSI < 50
                composite_features['ema_rsi_bearish'] = np.where(
                    features['ema_8_21_cross_below'] & (features['rsi_14'] < 50),
                    1, 0
                )
            
            # Volatility breakout + volume confirmation
            if all(k in features for k in ['bb_2_squeeze', 'volume_ratio_5']):
                # Volatility breakout with increased volume
                composite_features['volatility_breakout_volume'] = np.where(
                    features['bb_2_squeeze'] & (features['volume_ratio_5'] > 1.5),
                    1, 0
                )
            
            # Support/Resistance breakout with momentum
            if all(k in features for k in ['distance_to_resistance', 'rsi_14_slope']):
                # Resistance breakout with positive momentum
                resistance_breakout = np.where(
                    (features['distance_to_resistance'] < 0) & 
                    (np.roll(features['distance_to_resistance'], 1) > 0) &
                    (features['rsi_14_slope'] > 0),
                    1, 0
                )
                composite_features['resistance_breakout_momentum'] = resistance_breakout
            
            # Multi-timeframe RSI confluence
            if all(k in features for k in ['rsi_7', 'rsi_14', 'rsi_21']):
                # All RSIs showing oversold
                composite_features['rsi_multi_oversold'] = np.where(
                    (features['rsi_7'] < 30) & 
                    (features['rsi_14'] < 30) & 
                    (features['rsi_21'] < 30),
                    1, 0
                )
                
                # All RSIs showing overbought
                composite_features['rsi_multi_overbought'] = np.where(
                    (features['rsi_7'] > 70) & 
                    (features['rsi_14'] > 70) & 
                    (features['rsi_21'] > 70),
                    1, 0
                )
            
            # Trend strength + momentum
            if all(k in features for k in ['adx_14', 'macd_histogram']):
                # Strong trend with positive momentum
                composite_features['strong_uptrend'] = np.where(
                    (features['adx_14'] > 25) & (features['macd_histogram'] > 0),
                    1, 0
                )
                
                # Strong trend with negative momentum
                composite_features['strong_downtrend'] = np.where(
                    (features['adx_14'] > 25) & (features['macd_histogram'] < 0),
                    1, 0
                )
            
            # Mean reversion potential
            if all(k in features for k in ['bb_2_position', 'rsi_14', 'mean_reverting']):
                # Oversold in mean-reverting market
                composite_features['mean_reversion_buy'] = np.where(
                    (features['bb_2_position'] < 0.2) & 
                    (features['rsi_14'] < 30) & 
                    features['mean_reverting'],
                    1, 0
                )
                
                # Overbought in mean-reverting market
                composite_features['mean_reversion_sell'] = np.where(
                    (features['bb_2_position'] > 0.8) & 
                    (features['rsi_14'] > 70) & 
                    features['mean_reverting'],
                    1, 0
                )
            
            logger.info(f"Generated {len(composite_features)} composite features")
            
        except Exception as e:
            logger.error(f"Error generating composite features: {str(e)}")
        
        return composite_features
