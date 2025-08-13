"""
Timezone utilities for the prediction service
Handles proper timezone conversion and candle alignment
"""

from datetime import datetime, timedelta, timezone
import pytz
import logging

logger = logging.getLogger(__name__)

# Market timezone (Bangkok/UTC+7)
MARKET_TIMEZONE = pytz.timezone("Asia/Bangkok")
# System timezone (UTC)
SYSTEM_TIMEZONE = pytz.UTC

def get_current_market_time():
    """
    Get the current time in market timezone (UTC+7)
    """
    utc_now = datetime.now(SYSTEM_TIMEZONE)
    market_now = utc_now.astimezone(MARKET_TIMEZONE)
    return market_now

def get_current_candle_time(timeframe_minutes=1):
    """
    Get the timestamp of the current candle based on market time
    For example, at 10:01:45, the current 1-minute candle is 10:01:00
    """
    market_now = get_current_market_time()
    # Round down to the nearest timeframe interval
    minutes_to_subtract = market_now.minute % timeframe_minutes
    seconds_to_subtract = market_now.second
    microseconds_to_subtract = market_now.microsecond
    
    current_candle = market_now - timedelta(
        minutes=minutes_to_subtract,
        seconds=seconds_to_subtract,
        microseconds=microseconds_to_subtract
    )
    
    logger.debug(f"Current market time: {market_now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.debug(f"Current {timeframe_minutes}-minute candle: {current_candle.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return current_candle

def get_previous_candle_time(timeframe_minutes=1):
    """
    Get the timestamp of the previous completed candle
    """
    current_candle = get_current_candle_time(timeframe_minutes)
    previous_candle = current_candle - timedelta(minutes=timeframe_minutes)
    return previous_candle

def get_next_candle_time(timeframe_minutes=1):
    """
    Get the timestamp of the next candle
    """
    current_candle = get_current_candle_time(timeframe_minutes)
    next_candle = current_candle + timedelta(minutes=timeframe_minutes)
    return next_candle

def seconds_until_next_candle(timeframe_minutes=1, buffer_seconds=3):
    """
    Calculate seconds until the next candle starts, plus an optional buffer
    to ensure the candle data is available
    """
    market_now = get_current_market_time()
    next_candle = get_next_candle_time(timeframe_minutes)
    
    # Add buffer to ensure candle data is available
    next_candle_with_buffer = next_candle + timedelta(seconds=buffer_seconds)
    
    # Calculate seconds until next candle with buffer
    seconds_to_wait = (next_candle_with_buffer - market_now).total_seconds()
    
    # Ensure we always wait at least 1 second
    return max(1, seconds_to_wait)

def format_for_logging(dt):
    """Format a datetime object for logging"""
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

def get_candle_schedule_info(timeframe_minutes=1, buffer_seconds=3):
    """
    Get detailed information about current candle timing for logging
    """
    market_now = get_current_market_time()
    current_candle = get_current_candle_time(timeframe_minutes)
    next_candle = get_next_candle_time(timeframe_minutes)
    wait_seconds = seconds_until_next_candle(timeframe_minutes, buffer_seconds)
    
    return {
        "current_time": format_for_logging(market_now),
        "current_candle": format_for_logging(current_candle),
        "next_candle": format_for_logging(next_candle),
        "wait_seconds": wait_seconds,
        "next_prediction_at": format_for_logging(market_now + timedelta(seconds=wait_seconds))
    }
