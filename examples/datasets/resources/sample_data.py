"""
Simple sample data resource demonstrating basic Zeeker usage.

This is a minimal example showing:
- Basic data structure
- Simple duplicate handling
- Static data loading
"""

from sqlite_utils.db import Table
from typing import Optional, List, Dict, Any


def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """
    Fetch sample data - a simple example with static data.

    This demonstrates:
    - Basic data structure
    - Proper duplicate handling
    - Type inference (int, str, float, date)

    Args:
        existing_table: sqlite-utils Table object or None

    Returns:
        List of sample data dictionaries
    """
    # Static sample data
    sample_data = [
        {
            "id": 1,
            "name": "Sample Item 1",
            "value": 100.5,
            "created_date": "2024-01-01",
        },
        {
            "id": 2,
            "name": "Sample Item 2",
            "value": 200.75,
            "created_date": "2024-01-02",
        },
        {
            "id": 3,
            "name": "Sample Item 3",
            "value": 150.25,
            "created_date": "2024-01-03",
        },
    ]

    # Handle duplicates if table exists
    if existing_table:
        existing_ids = {row["id"] for row in existing_table.rows}
        sample_data = [item for item in sample_data if item["id"] not in existing_ids]
        print(f"sample_data: Adding {len(sample_data)} new records")

    return sample_data
