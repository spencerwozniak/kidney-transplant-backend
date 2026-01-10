"""
Utility functions for API routes
"""
from datetime import datetime
from typing import Dict, Any


def convert_datetime_to_iso(data: Dict[str, Any], fields: list[str]) -> Dict[str, Any]:
    """
    Convert datetime objects to ISO strings for JSON storage
    
    Args:
        data: Dictionary to convert
        fields: List of field names to convert
    
    Returns:
        Dictionary with datetime fields converted to ISO strings
    """
    result = data.copy()
    for field in fields:
        if isinstance(result.get(field), datetime):
            result[field] = result[field].isoformat()
    return result


def convert_checklist_datetimes(checklist_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert all datetime objects in checklist data to ISO strings
    
    Handles both top-level datetime fields and datetime fields in checklist items
    """
    result = checklist_data.copy()
    
    # Convert top-level datetime fields
    result = convert_datetime_to_iso(result, ['created_at', 'updated_at'])
    
    # Convert datetime objects in checklist items
    if 'items' in result:
        items = []
        for item in result['items']:
            item_copy = item.copy()
            if isinstance(item_copy.get('completed_at'), datetime):
                item_copy['completed_at'] = item_copy['completed_at'].isoformat()
            items.append(item_copy)
        result['items'] = items
    
    return result

