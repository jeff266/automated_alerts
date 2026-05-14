"""
Weekly Sales Activities Script - HubSpot Activity Metrics

This script queries HubSpot for activity metrics including:
- Emails, calls, and meetings per rep
- MemoryBlue SDR dial/connect metrics
"""

import os
import requests
from datetime import datetime, date
from typing import Dict, List, Any

# HubSpot API Configuration
HUBSPOT_TOKEN = os.environ.get("HUBSPOT_TOKEN", "")
BASE_URL = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# Owner name cache
_owner_names_cache: Dict[str, str] = {}

# MemoryBlue SDR Owner IDs
MEMORYBLUE_OWNER_IDS = ["89403079", "90061023"]

# Connect disposition GUIDs (from HubSpot /calling/v1/dispositions)
CONNECT_DISPOSITIONS = [
    "f240bbac-87c9-4f6e-bf70-924b57d47db7",  # Connected
    "a4c4c377-d246-4b32-a13b-75a56a4cd0ff",  # Live conversation
]


def _get_owner_name(owner_id: str) -> str:
    """Get owner name from owner ID."""
    global _owner_names_cache

    if not owner_id:
        return "Unassigned"

    if owner_id in _owner_names_cache:
        return _owner_names_cache[owner_id]

    url = f"{BASE_URL}/crm/v3/owners/{owner_id}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        name = f"{data.get('firstName', '')} {data.get('lastName', '')}".strip()
        if not name:
            name = data.get("email", f"Owner {owner_id}")
        _owner_names_cache[owner_id] = name
        return name
    except Exception:
        _owner_names_cache[owner_id] = f"Owner {owner_id}"
        return _owner_names_cache[owner_id]


def _date_to_timestamp(d: date) -> int:
    """Convert date to milliseconds timestamp."""
    return int(datetime.combine(d, datetime.min.time()).timestamp() * 1000)


def _search_engagements(object_type: str, filters: List[Dict], properties: List[str]) -> List[Dict]:
    """Search engagements (calls, meetings, emails) with pagination."""
    url = f"{BASE_URL}/crm/v3/objects/{object_type}/search"
    all_results = []
    after = None

    while True:
        payload = {
            "filterGroups": [{"filters": filters}],
            "properties": properties,
            "limit": 100
        }

        if after:
            payload["after"] = after

        try:
            response = requests.post(url, headers=HEADERS, json=payload)
            if response.status_code == 403:
                print(f"  Warning: No permission to access {object_type} (403 Forbidden)")
                return []
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            all_results.extend(results)

            paging = data.get("paging", {})
            next_page = paging.get("next", {})
            after = next_page.get("after")

            if not after:
                break
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"  Warning: No permission to access {object_type} (403 Forbidden)")
                return []
            raise

    return all_results


def get_activities_by_owner(start_date: date, end_date: date) -> Dict[str, Dict[str, int]]:
    """
    Get activity counts (emails, calls, meetings) grouped by owner.

    Returns:
        Dict mapping owner name to activity counts
    """
    start_ms = _date_to_timestamp(start_date)
    end_ms = _date_to_timestamp(end_date) + (24 * 60 * 60 * 1000 - 1)

    result: Dict[str, Dict[str, int]] = {}

    # Emails (may fail with 403 if no sales-email-read scope)
    print("  Fetching emails...")
    email_filters = [
        {"propertyName": "hs_timestamp", "operator": "GTE", "value": str(start_ms)},
        {"propertyName": "hs_timestamp", "operator": "LTE", "value": str(end_ms)},
    ]
    emails = _search_engagements("emails", email_filters, ["hs_timestamp", "hubspot_owner_id"])
    print(f"    Found {len(emails)} emails")

    for email in emails:
        owner_id = email["properties"].get("hubspot_owner_id")
        owner_name = _get_owner_name(owner_id)
        if owner_name not in result:
            result[owner_name] = {"emails": 0, "calls": 0, "meetings": 0, "total": 0}
        result[owner_name]["emails"] += 1
        result[owner_name]["total"] += 1

    # Calls (exclude MemoryBlue SDRs)
    print("  Fetching calls...")
    call_filters = [
        {"propertyName": "hs_timestamp", "operator": "GTE", "value": str(start_ms)},
        {"propertyName": "hs_timestamp", "operator": "LTE", "value": str(end_ms)},
    ]
    calls = _search_engagements("calls", call_filters, ["hs_timestamp", "hubspot_owner_id", "hs_object_source"])

    # Filter out MemoryBlue calls (imported)
    ae_calls = [c for c in calls if c["properties"].get("hs_object_source") != "IMPORT"]
    print(f"    Found {len(ae_calls)} calls")

    for call in ae_calls:
        owner_id = call["properties"].get("hubspot_owner_id")
        owner_name = _get_owner_name(owner_id)
        if owner_name not in result:
            result[owner_name] = {"emails": 0, "calls": 0, "meetings": 0, "total": 0}
        result[owner_name]["calls"] += 1
        result[owner_name]["total"] += 1

    # Meetings
    print("  Fetching meetings...")
    meeting_filters = [
        {"propertyName": "hs_timestamp", "operator": "GTE", "value": str(start_ms)},
        {"propertyName": "hs_timestamp", "operator": "LTE", "value": str(end_ms)},
    ]
    meetings = _search_engagements("meetings", meeting_filters, ["hs_timestamp", "hubspot_owner_id"])
    print(f"    Found {len(meetings)} meetings")

    for meeting in meetings:
        owner_id = meeting["properties"].get("hubspot_owner_id")
        owner_name = _get_owner_name(owner_id)
        if owner_name not in result:
            result[owner_name] = {"emails": 0, "calls": 0, "meetings": 0, "total": 0}
        result[owner_name]["meetings"] += 1
        result[owner_name]["total"] += 1

    return result


def get_memoryblue_activities(start_date: date, end_date: date) -> Dict[str, Any]:
    """
    Get MemoryBlue SDR metrics (dials, connects, connect rate).

    Uses hs_createdate for imported calls since that's when they were imported.

    Returns:
        Dict with total_dials, connects, connect_rate
    """
    start_ms = _date_to_timestamp(start_date)
    end_ms = _date_to_timestamp(end_date) + (24 * 60 * 60 * 1000 - 1)

    print("  Fetching MemoryBlue calls (imported)...")

    # Query using hs_createdate for imports
    filters = [
        {"propertyName": "hs_createdate", "operator": "GTE", "value": str(start_ms)},
        {"propertyName": "hs_createdate", "operator": "LTE", "value": str(end_ms)},
        {"propertyName": "hs_object_source", "operator": "EQ", "value": "IMPORT"},
    ]

    properties = ["hs_createdate", "hs_call_disposition", "hubspot_owner_id"]
    calls = _search_engagements("calls", filters, properties)
    print(f"    Found {len(calls)} imported calls")

    total_dials = len(calls)
    connects = 0

    for call in calls:
        disposition = call["properties"].get("hs_call_disposition", "")
        if disposition in CONNECT_DISPOSITIONS:
            connects += 1

    connect_rate = (connects / total_dials * 100) if total_dials > 0 else 0

    return {
        "total_dials": total_dials,
        "connects": connects,
        "connect_rate": connect_rate
    }
