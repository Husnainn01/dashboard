#!/usr/bin/env python3

import sys
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.append('../')

from database.mongodb_models import CandleData

async def test():
    # Create a test candle
    c = CandleData(
        trading_pair='TEST/USD',
        timestamp=datetime.now(),
        open_price=100.0,
        high_price=101.0,
        low_price=99.0,
        close_price=100.5,
        volume=1000
    )
    
    # Test the property getters
    print(f'Created candle: {c.trading_pair}')
    print(f'Open: {c.open}, Close: {c.close}')
    print(f'High: {c.high}, Low: {c.low}')
    print(f'Direction: {c.direction}, Change: {c.change}')

if __name__ == '__main__':
    asyncio.run(test())