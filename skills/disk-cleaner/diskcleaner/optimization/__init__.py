"""
Performance optimization module for disk-cleaner.

This module provides intelligent, layered performance optimizations:
- Concurrent scanning
- Incremental caching
- Adaptive hash computation
- Performance monitoring

All optimizations are pluggable and can be disabled via configuration.
"""

from diskcleaner.optimization.concurrency import ConcurrencyManager
from diskcleaner.optimization.hash import (
    AdaptiveHasher,
    DuplicateFinder,
    DuplicateGroup,
    FastFilter,
    HashCache,
    ParallelHasher,
)
from diskcleaner.optimization.memory import MemoryMonitor, MemoryStatus
from diskcleaner.optimization.profiler import PerformanceProfiler, PerformanceReport
from diskcleaner.optimization.scan import (
    ConcurrentScanner,
    FileInfo,
    IncrementalCache,
    QuickProfiler,
    ScanProfile,
    ScanResult,
    ScanSnapshot,
    ScanStrategy,
)

__all__ = [
    # Infrastructure
    "PerformanceProfiler",
    "PerformanceReport",
    "ConcurrencyManager",
    "MemoryMonitor",
    "MemoryStatus",
    # Scanning
    "QuickProfiler",
    "ConcurrentScanner",
    "IncrementalCache",
    "ScanStrategy",
    "ScanProfile",
    "ScanResult",
    "ScanSnapshot",
    "FileInfo",
    # Hash
    "AdaptiveHasher",
    "ParallelHasher",
    "FastFilter",
    "HashCache",
    "DuplicateFinder",
    "DuplicateGroup",
]
