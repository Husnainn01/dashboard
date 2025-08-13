"""
Parallel Processing Utility for OTC Predictor
Handles concurrent execution of predictions for multiple trading pairs
"""

import asyncio
import logging
from typing import Dict, Any, List, Callable, Coroutine, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ParallelProcessor:
    """
    Handles parallel processing of tasks with concurrency control
    """
    def __init__(self, max_concurrency: int = 3):
        """
        Initialize the parallel processor
        
        Args:
            max_concurrency: Maximum number of tasks to run in parallel
        """
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.stats = {
            "total_tasks_processed": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "current_tasks": 0,
            "max_concurrent_tasks": 0
        }
    
    async def process_item(self, 
                          func: Callable[..., Coroutine[Any, Any, T]], 
                          *args, 
                          item_id: str = None,
                          **kwargs) -> Optional[T]:
        """
        Process a single item with semaphore control
        
        Args:
            func: Async function to execute
            item_id: Identifier for the item being processed (for logging)
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result of the function or None if an error occurred
        """
        async with self.semaphore:
            self.stats["current_tasks"] += 1
            self.stats["total_tasks_processed"] += 1
            self.stats["max_concurrent_tasks"] = max(
                self.stats["max_concurrent_tasks"], 
                self.stats["current_tasks"]
            )
            
            item_name = item_id if item_id else f"Task-{self.stats['total_tasks_processed']}"
            
            try:
                logger.info(f"🔄 Starting parallel processing of {item_name}")
                result = await func(*args, **kwargs)
                self.stats["successful_tasks"] += 1
                logger.info(f"✅ Completed parallel processing of {item_name}")
                return result
            except Exception as e:
                self.stats["failed_tasks"] += 1
                logger.error(f"❌ Error processing {item_name}: {str(e)}")
                return None
            finally:
                self.stats["current_tasks"] -= 1
    
    async def process_batch(self, 
                           items: List[Dict[str, Any]], 
                           func: Callable[..., Coroutine[Any, Any, T]],
                           id_key: str = "id") -> Dict[str, Optional[T]]:
        """
        Process a batch of items in parallel with controlled concurrency
        
        Args:
            items: List of item dictionaries to process
            func: Async function to execute for each item
            id_key: Key in the item dictionary to use as the identifier
            
        Returns:
            Dictionary mapping item IDs to results
        """
        tasks = []
        for item in items:
            item_id = item.get(id_key, f"Item-{len(tasks)}")
            # Create task for each item
            task = self.process_item(
                func, 
                **item,  # Pass item dictionary as kwargs
                item_id=item_id
            )
            tasks.append((item_id, asyncio.create_task(task)))
        
        # Wait for all tasks to complete
        results = {}
        for item_id, task in tasks:
            try:
                results[item_id] = await task
            except Exception as e:
                logger.error(f"❌ Task for {item_id} failed: {str(e)}")
                results[item_id] = None
        
        return results
    
    async def process_trading_pairs(self, 
                                   trading_pairs: List[str],
                                   func: Callable[[str], Coroutine[Any, Any, T]],
                                   priority_pair: str = None) -> Dict[str, Optional[T]]:
        """
        Process multiple trading pairs in parallel with priority handling
        
        Args:
            trading_pairs: List of trading pairs to process
            func: Async function to execute for each trading pair
            priority_pair: Trading pair to prioritize (will be processed first)
            
        Returns:
            Dictionary mapping trading pairs to results
        """
        results = {}
        
        # Process priority pair first if specified
        if priority_pair and priority_pair in trading_pairs:
            logger.info(f"🔝 Processing priority pair {priority_pair}")
            try:
                results[priority_pair] = await func(priority_pair)
                self.stats["successful_tasks"] += 1
                self.stats["total_tasks_processed"] += 1
            except Exception as e:
                logger.error(f"❌ Error processing priority pair {priority_pair}: {str(e)}")
                results[priority_pair] = None
                self.stats["failed_tasks"] += 1
                self.stats["total_tasks_processed"] += 1
        
        # Process remaining pairs in parallel
        remaining_pairs = [p for p in trading_pairs if p != priority_pair]
        if not remaining_pairs:
            return results
        
        # Create tasks for remaining pairs
        tasks = []
        for pair in remaining_pairs:
            task = self.process_item(func, pair, item_id=pair)
            tasks.append((pair, asyncio.create_task(task)))
        
        # Wait for all tasks to complete
        for pair, task in tasks:
            try:
                results[pair] = await task
            except Exception as e:
                logger.error(f"❌ Task for {pair} failed: {str(e)}")
                results[pair] = None
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        return self.stats
