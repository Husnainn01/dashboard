"""
Configuration for Data Collection
Manages credentials and collection settings
"""

import os
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class CollectionConfig:
    """Configuration for data collection"""
    
    # PyQuotex credentials
    email: str = ""
    password: str = ""
    is_demo: bool = True
    
    # Collection settings
    trading_pairs: List[str] = None
    timeframe: int = 60  # seconds
    collection_interval: int = 60  # seconds
    
    # Database settings
    database_path: str = "otc_predictor.db"
    
    def __post_init__(self):
        if self.trading_pairs is None:
            self.trading_pairs = [
                'EURUSD',  # Euro/US Dollar
                'GBPUSD',  # British Pound/US Dollar  
                'USDJPY',  # US Dollar/Japanese Yen
                'AUDUSD',  # Australian Dollar/US Dollar
                'USDCAD',  # US Dollar/Canadian Dollar
                'EURJPY',  # Euro/Japanese Yen
                'EURGBP',  # Euro/British Pound
                'NZDUSD'   # New Zealand Dollar/US Dollar
            ]
    
    @classmethod
    def from_env(cls) -> 'CollectionConfig':
        """Create configuration from environment variables"""
        return cls(
            email=os.getenv('QUOTEX_EMAIL', ''),
            password=os.getenv('QUOTEX_PASSWORD', ''),
            is_demo=os.getenv('QUOTEX_IS_DEMO', 'true').lower() == 'true',
            timeframe=int(os.getenv('COLLECTION_TIMEFRAME', '60')),
            collection_interval=int(os.getenv('COLLECTION_INTERVAL', '60')),
            database_path=os.getenv('DATABASE_PATH', 'otc_predictor.db')
        )
    
    def validate(self) -> bool:
        """Validate configuration"""
        if not self.email or not self.password:
            print("❌ Email and password are required")
            return False
        
        if self.timeframe <= 0:
            print("❌ Timeframe must be positive")
            return False
        
        if self.collection_interval <= 0:
            print("❌ Collection interval must be positive")
            return False
        
        if not self.trading_pairs:
            print("❌ At least one trading pair is required")
            return False
        
        return True
    
    def display_info(self):
        """Display configuration information"""
        print("📋 Data Collection Configuration:")
        print(f"  📧 Email: {self.email}")
        print(f"  🎮 Demo Mode: {'Yes' if self.is_demo else 'No'}")
        print(f"  ⏱️ Timeframe: {self.timeframe}s")
        print(f"  🔄 Collection Interval: {self.collection_interval}s")
        print(f"  💾 Database: {self.database_path}")
        print(f"  📊 Trading Pairs: {', '.join(self.trading_pairs)}")


# Default configuration
DEFAULT_CONFIG = CollectionConfig(
    email="your-email@example.com",
    password="your-password",
    is_demo=True
) 