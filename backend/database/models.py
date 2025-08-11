"""
Database Models for OTC-Predictor
Stores market data collected from PyQuotex API
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class CandleData:
    """
    Candle data model - equivalent to CandleData.js schema
    Stores OHLC data from PyQuotex API
    """
    # Basic candle information
    timestamp: datetime
    trading_pair: str = 'EUR/USD OTC'
    timeframe: int = 60  # seconds
    
    # OHLC data from PyQuotex API
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    
    # Derived data
    direction: str = ''  # 'up' or 'down'
    change: float = 0.0
    change_percent: float = 0.0
    
    # PyQuotex API metadata
    api_data: Optional[Dict] = None
    collection_method: str = 'pyquotex_api'
    confidence_score: float = 100.0
    
    # Technical indicators (if available)
    indicators: Optional[Dict] = None
    
    # Pattern matching
    pattern_id: Optional[str] = None
    similar_patterns: Optional[List[int]] = None
    
    # Data quality flags
    is_validated: bool = False
    collection_errors: Optional[List[str]] = None
    
    # Metadata
    session_id: Optional[str] = None
    bot_version: str = '1.0.0'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Database ID
    id: Optional[int] = None
    
    def __post_init__(self):
        """Calculate derived fields after initialization"""
        if self.open and self.close:
            self.change = self.close - self.open
            self.change_percent = (self.change / self.open) * 100 if self.open != 0 else 0
            self.direction = 'up' if self.close > self.open else 'down'
        
        if not self.created_at:
            self.created_at = datetime.now()
        
        if not self.updated_at:
            self.updated_at = datetime.now()
    
    @property
    def body_size(self) -> float:
        """Candle body size (absolute difference between open and close)"""
        return abs(self.close - self.open) if self.close and self.open else 0
    
    @property
    def upper_wick(self) -> float:
        """Upper wick size"""
        if not all([self.high, self.open, self.close]):
            return 0
        return self.high - max(self.open, self.close)
    
    @property
    def lower_wick(self) -> float:
        """Lower wick size"""
        if not all([self.low, self.open, self.close]):
            return 0
        return min(self.open, self.close) - self.low


@dataclass 
class PredictionData:
    """
    Prediction model for storing ML predictions
    """
    # Basic prediction info
    timestamp: datetime
    trading_pair: str = 'EUR/USD OTC'
    direction: str = ''  # 'up' or 'down'
    confidence: float = 0.0
    
    # Algorithm info
    algorithm_used: str = ''
    model_version: str = '1.0.0'
    
    # Input data
    input_candles: Optional[List[int]] = None  # List of candle IDs used for prediction
    features: Optional[Dict] = None
    
    # Results (filled when actual candle arrives)
    actual_direction: Optional[str] = None
    actual_change: Optional[float] = None
    is_correct: Optional[bool] = None
    accuracy_score: Optional[float] = None
    
    # Metadata
    session_id: Optional[str] = None
    is_processed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Database ID
    id: Optional[int] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()
        if not self.updated_at:
            self.updated_at = datetime.now()


class DatabaseManager:
    """
    Database manager for SQLite operations
    """
    
    def __init__(self, db_path: str = "otc_predictor.db"):
        self.db_path = Path(db_path)
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper settings"""
        conn = sqlite3.Connection(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            # Candle data table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candle_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    trading_pair TEXT NOT NULL DEFAULT 'EUR/USD OTC',
                    timeframe INTEGER NOT NULL DEFAULT 60,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    direction TEXT NOT NULL,
                    change REAL NOT NULL,
                    change_percent REAL NOT NULL,
                    api_data TEXT,  -- JSON string
                    collection_method TEXT DEFAULT 'pyquotex_api',
                    confidence_score REAL DEFAULT 100.0,
                    indicators TEXT,  -- JSON string
                    pattern_id TEXT,
                    similar_patterns TEXT,  -- JSON string
                    is_validated BOOLEAN DEFAULT FALSE,
                    collection_errors TEXT,  -- JSON string
                    session_id TEXT,
                    bot_version TEXT DEFAULT '1.0.0',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            
            # Predictions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    trading_pair TEXT NOT NULL DEFAULT 'EUR/USD OTC',
                    direction TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    algorithm_used TEXT NOT NULL,
                    model_version TEXT DEFAULT '1.0.0',
                    input_candles TEXT,  -- JSON string
                    features TEXT,  -- JSON string
                    actual_direction TEXT,
                    actual_change REAL,
                    is_correct BOOLEAN,
                    accuracy_score REAL,
                    session_id TEXT,
                    is_processed BOOLEAN DEFAULT FALSE,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_candle_timestamp ON candle_data(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_candle_pair ON candle_data(trading_pair)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_candle_session ON candle_data(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prediction_timestamp ON predictions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prediction_session ON predictions(session_id)")
            
            conn.commit()
    
    def save_candle(self, candle: CandleData) -> int:
        """Save candle data to database"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO candle_data (
                    timestamp, trading_pair, timeframe, open, high, low, close,
                    direction, change, change_percent, api_data, collection_method,
                    confidence_score, indicators, pattern_id, similar_patterns,
                    is_validated, collection_errors, session_id, bot_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                candle.timestamp, candle.trading_pair, candle.timeframe,
                candle.open, candle.high, candle.low, candle.close,
                candle.direction, candle.change, candle.change_percent,
                json.dumps(candle.api_data) if candle.api_data else None,
                candle.collection_method, candle.confidence_score,
                json.dumps(candle.indicators) if candle.indicators else None,
                candle.pattern_id,
                json.dumps(candle.similar_patterns) if candle.similar_patterns else None,
                candle.is_validated,
                json.dumps(candle.collection_errors) if candle.collection_errors else None,
                candle.session_id, candle.bot_version,
                candle.created_at, candle.updated_at
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_latest_candles(self, limit: int = 20, trading_pair: str = 'EUR/USD OTC') -> List[CandleData]:
        """Get latest candles from database"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM candle_data 
                WHERE trading_pair = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (trading_pair, limit))
            
            candles = []
            for row in cursor.fetchall():
                candle_dict = dict(row)
                # Parse JSON fields
                if candle_dict['api_data']:
                    candle_dict['api_data'] = json.loads(candle_dict['api_data'])
                if candle_dict['indicators']:
                    candle_dict['indicators'] = json.loads(candle_dict['indicators'])
                if candle_dict['similar_patterns']:
                    candle_dict['similar_patterns'] = json.loads(candle_dict['similar_patterns'])
                if candle_dict['collection_errors']:
                    candle_dict['collection_errors'] = json.loads(candle_dict['collection_errors'])
                
                candles.append(CandleData(**candle_dict))
            
            return candles
    
    def save_prediction(self, prediction: PredictionData) -> int:
        """Save prediction to database"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO predictions (
                    timestamp, trading_pair, direction, confidence, algorithm_used,
                    model_version, input_candles, features, actual_direction,
                    actual_change, is_correct, accuracy_score, session_id,
                    is_processed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction.timestamp, prediction.trading_pair, prediction.direction,
                prediction.confidence, prediction.algorithm_used, prediction.model_version,
                json.dumps(prediction.input_candles) if prediction.input_candles else None,
                json.dumps(prediction.features) if prediction.features else None,
                prediction.actual_direction, prediction.actual_change,
                prediction.is_correct, prediction.accuracy_score, prediction.session_id,
                prediction.is_processed, prediction.created_at, prediction.updated_at
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_predictions(self, session_id: Optional[str] = None, limit: int = 10) -> List[PredictionData]:
        """Get predictions from database"""
        with self.get_connection() as conn:
            if session_id:
                cursor = conn.execute("""
                    SELECT * FROM predictions 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM predictions 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
            
            predictions = []
            for row in cursor.fetchall():
                pred_dict = dict(row)
                # Parse JSON fields
                if pred_dict['input_candles']:
                    pred_dict['input_candles'] = json.loads(pred_dict['input_candles'])
                if pred_dict['features']:
                    pred_dict['features'] = json.loads(pred_dict['features'])
                
                predictions.append(PredictionData(**pred_dict))
            
            return predictions
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            candle_count = conn.execute("SELECT COUNT(*) FROM candle_data").fetchone()[0]
            prediction_count = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
            
            # Get accuracy stats
            accuracy_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_predictions,
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_predictions,
                    AVG(confidence) as avg_confidence
                FROM predictions 
                WHERE is_processed = 1
            """).fetchone()
            
            return {
                'candle_count': candle_count,
                'prediction_count': prediction_count,
                'total_processed_predictions': accuracy_stats[0] if accuracy_stats[0] else 0,
                'correct_predictions': accuracy_stats[1] if accuracy_stats[1] else 0,
                'accuracy_rate': (accuracy_stats[1] / accuracy_stats[0] * 100) if accuracy_stats[0] and accuracy_stats[1] else 0,
                'avg_confidence': accuracy_stats[2] if accuracy_stats[2] else 0
            }


# Global database instance
db = DatabaseManager() 