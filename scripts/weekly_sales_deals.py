"""
Weekly Sales Deals Script - HubSpot Deal Metrics

This script queries HubSpot for various deal metrics including:
- Q2 closed won deals
- Q2 pipeline generated
- Month-to-date closed won
- Month-to-date new pipeline
- Weekly closed won
- Weekly self-sourced pipeline by owner
- Deals to watch (large/important deals)
"""

import os
import requests
from datetime import datetime, date
from typing import Dict, List, Any
import calendar

# HubSpot API Configuration
HUBSPOT_TOKEN = os.environ.get("HUBSPOT_TOKEN", "")
BASE_URL = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json"
}

# Cache for stage labels and owner names
_stage_labels_cache: Dict[str, str] = {}
_owner_names_cache: Dict[str, str] = {}

# MemoryBlue SDR Owner IDs
MEMORYBLUE_OWNER_IDS = {
    "89403079": "Duncan Grant",
    "90061023": "Greg McMullan",
}


def _get_stage_labels(pipeline_id: str = "default") -> Dict[str, str]:
    """Get deal stage labels from pipeline endpoint."""
    global _stage_labels_cache

    if _stage_labels_cache:
        return _stage_labels_cache

    url = f"{BASE_URL}/crm/v3/pipelines/deals/{pipeline_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    data = response.json()
    stages = data.get("stages", [])

    _stage_labels_cache = {stage["id"]: stage["label"] for stage in stages}
    return _stage_labels_cache


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
    """Convert date to milliseconds timestamp for HubSpot API."""
    return int(datetime.combine(d, datetime.min.time()).timestamp() * 1000)


def _search_deals(filters: List[Dict], properties: List[str], limit: int = 100) -> List[Dict]:
    """Search deals with pagination support."""
    url = f"{BASE_URL}/crm/v3/objects/deals/search"
    all_deals = []
    after = None

    while True:
        payload = {
            "filterGroups": [{"filters": filters}],
            "properties": properties,
            "limit": limit
        }

        if after:
            payload["after"] = after

        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])
        all_deals.extend(results)

        paging = data.get("paging", {})
        next_page = paging.get("next", {})
        after = next_page.get("after")

        if not after:
            break

    return all_deals


def get_q2_closed_won() -> Dict[str, Any]:
    """Returns closed won deals in Q2 2026 (April 1 - June 30)."""
    q2_start = date(2026, 4, 1)
    q2_end = date(2026, 6, 30)

    filters = [
        {"propertyName": "dealstage", "operator": "EQ", "value": "closedwon"},
        {"propertyName": "closedate", "operator": "GTE", "value": _date_to_timestamp(q2_start)},
        {"propertyName": "closedate", "operator": "LTE", "value": _date_to_timestamp(q2_end)}
    ]

    properties = ["dealname", "amount", "closedate", "dealstage", "hubspot_owner_id"]
    deals = _search_deals(filters, properties)

    total_amount = sum(float(d["properties"].get("amount") or 0) for d in deals)

    deal_list = []
    for d in deals:
        props = d["properties"]
        deal_list.append({
            "id": d["id"],
            "name": props.get("dealname"),
            "amount": float(props.get("amount") or 0),
            "closedate": props.get("closedate"),
            "owner": _get_owner_name(props.get("hubspot_owner_id"))
        })

    return {"total_amount": total_amount, "count": len(deals), "deals": deal_list}


def get_q2_pipeline_generated() -> Dict[str, Any]:
    """Returns NEW pipeline generated in Q2 (deals created in Q2)."""
    q2_start = date(2026, 4, 1)
    q2_end = date(2026, 6, 30)

    filters = [
        {"propertyName": "pipeline", "operator": "EQ", "value": "default"},
        {"propertyName": "createdate", "operator": "GTE", "value": str(_date_to_timestamp(q2_start))},
        {"propertyName": "createdate", "operator": "LTE", "value": str(_date_to_timestamp(q2_end))}
    ]

    properties = ["dealname", "amount", "dealstage", "createdate"]
    deals = _search_deals(filters, properties)

    active_deals = [d for d in deals if d["properties"].get("dealstage") != "closedlost"]
    total_amount = sum(float(d["properties"].get("amount") or 0) for d in active_deals)

    return {"total_amount": total_amount, "count": len(active_deals)}


def get_mtd_closed_won(month: int, year: int) -> Dict[str, Any]:
    """Returns closed won deals for a specific month."""
    month_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)

    filters = [
        {"propertyName": "dealstage", "operator": "EQ", "value": "closedwon"},
        {"propertyName": "closedate", "operator": "GTE", "value": _date_to_timestamp(month_start)},
        {"propertyName": "closedate", "operator": "LTE", "value": _date_to_timestamp(month_end)}
    ]

    properties = ["dealname", "amount", "closedate", "dealstage", "hubspot_owner_id"]
    deals = _search_deals(filters, properties)

    total_amount = sum(float(d["properties"].get("amount") or 0) for d in deals)

    deal_list = []
    for d in deals:
        props = d["properties"]
        deal_list.append({
            "id": d["id"],
            "name": props.get("dealname"),
            "amount": float(props.get("amount") or 0),
            "closedate": props.get("closedate"),
            "owner": _get_owner_name(props.get("hubspot_owner_id"))
        })

    return {"total_amount": total_amount, "count": len(deals), "deals": deal_list}


def get_mtd_new_pipeline(month: int, year: int) -> Dict[str, Any]:
    """Returns deals created in a specific month (excluding closed lost)."""
    month_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)

    filters = [
        {"propertyName": "createdate", "operator": "GTE", "value": _date_to_timestamp(month_start)},
        {"propertyName": "createdate", "operator": "LTE", "value": _date_to_timestamp(month_end)}
    ]

    properties = ["dealname", "amount", "createdate", "dealstage"]
    deals = _search_deals(filters, properties)

    open_deals = [d for d in deals if d["properties"].get("dealstage") != "closedlost"]
    total_amount = sum(float(d["properties"].get("amount") or 0) for d in open_deals)

    return {"total_amount": total_amount, "count": len(open_deals)}


def get_weekly_closed_won(start_date: date, end_date: date) -> Dict[str, Any]:
    """Returns closed won deals in a date range."""
    filters = [
        {"propertyName": "dealstage", "operator": "EQ", "value": "closedwon"},
        {"propertyName": "closedate", "operator": "GTE", "value": _date_to_timestamp(start_date)},
        {"propertyName": "closedate", "operator": "LTE", "value": _date_to_timestamp(end_date)}
    ]

    properties = ["dealname", "amount", "closedate", "dealstage", "hubspot_owner_id"]
    deals = _search_deals(filters, properties)

    total_amount = sum(float(d["properties"].get("amount") or 0) for d in deals)

    deal_list = []
    for d in deals:
        props = d["properties"]
        deal_list.append({
            "id": d["id"],
            "name": props.get("dealname"),
            "amount": float(props.get("amount") or 0),
            "closedate": props.get("closedate"),
            "owner": _get_owner_name(props.get("hubspot_owner_id"))
        })

    return {"total_amount": total_amount, "count": len(deals), "deals": deal_list}


def _check_contact_has_memoryblue_meeting(contact_id: str) -> bool:
    """Check if a contact has any meeting booked by a MemoryBlue SDR."""
    url = f"{BASE_URL}/crm/v4/objects/contacts/{contact_id}/associations/meetings"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        meeting_ids = [r.get("toObjectId") for r in data.get("results", [])]

        for meeting_id in meeting_ids:
            meeting_url = f"{BASE_URL}/crm/v3/objects/meetings/{meeting_id}"
            meeting_resp = requests.get(meeting_url, headers=HEADERS, params={"properties": "hubspot_owner_id"})
            if meeting_resp.status_code == 200:
                meeting_data = meeting_resp.json()
                owner_id = meeting_data.get("properties", {}).get("hubspot_owner_id", "")
                if owner_id in MEMORYBLUE_OWNER_IDS:
                    return True
    except Exception:
        pass

    return False


def _get_deal_contacts(deal_id: str) -> List[str]:
    """Get contact IDs associated with a deal."""
    url = f"{BASE_URL}/crm/v4/objects/deals/{deal_id}/associations/contacts"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        return [r.get("toObjectId") for r in data.get("results", [])]
    except Exception:
        return []


def is_deal_memoryblue_sourced(deal_id: str) -> bool:
    """Determine if a deal was sourced by MemoryBlue (vs self-sourced by AE)."""
    contact_ids = _get_deal_contacts(deal_id)

    for contact_id in contact_ids:
        if _check_contact_has_memoryblue_meeting(contact_id):
            return True

    return False


def get_weekly_self_sourced_pipeline_by_owner(start_date: date, end_date: date) -> Dict[str, Any]:
    """Returns self-sourced pipeline (not MemoryBlue) grouped by owner for a date range."""
    filters = [
        {"propertyName": "createdate", "operator": "GTE", "value": _date_to_timestamp(start_date)},
        {"propertyName": "createdate", "operator": "LTE", "value": _date_to_timestamp(end_date)}
    ]

    properties = ["dealname", "amount", "createdate", "dealstage", "hubspot_owner_id"]
    deals = _search_deals(filters, properties)

    open_deals = [d for d in deals if d["properties"].get("dealstage") != "closedlost"]

    self_sourced_by_owner: Dict[str, float] = {}
    memoryblue_by_owner: Dict[str, float] = {}
    deal_details = []

    for d in open_deals:
        props = d["properties"]
        deal_id = d["id"]
        owner_id = props.get("hubspot_owner_id")
        owner_name = _get_owner_name(owner_id)
        amount = float(props.get("amount") or 0)

        is_mb = is_deal_memoryblue_sourced(deal_id)

        deal_info = {
            "id": deal_id,
            "name": props.get("dealname"),
            "amount": amount,
            "owner": owner_name,
            "is_memoryblue_sourced": is_mb,
            "source": "MemoryBlue" if is_mb else "Self-Sourced"
        }
        deal_details.append(deal_info)

        if is_mb:
            memoryblue_by_owner[owner_name] = memoryblue_by_owner.get(owner_name, 0) + amount
        else:
            self_sourced_by_owner[owner_name] = self_sourced_by_owner.get(owner_name, 0) + amount

    return {
        "by_owner": self_sourced_by_owner,
        "memoryblue_by_owner": memoryblue_by_owner,
        "deals": deal_details,
        "totals": {
            "self_sourced": sum(self_sourced_by_owner.values()),
            "memoryblue": sum(memoryblue_by_owner.values()),
        }
    }


def get_deals_to_watch() -> List[Dict[str, Any]]:
    """Returns large/important deals that need attention."""
    stage_labels = _get_stage_labels()

    late_stage_keywords = ["contract", "negotiation", "closing", "proposal", "decision"]
    late_stages = [
        stage_id for stage_id, label in stage_labels.items()
        if any(kw in label.lower() for kw in late_stage_keywords)
    ]

    properties = [
        "dealname", "amount", "dealstage", "closedate",
        "hs_forecast_category", "hubspot_owner_id"
    ]

    all_deals = []

    open_deal_filters = [{"propertyName": "pipeline", "operator": "EQ", "value": "default"}]
    all_open_deals = _search_deals(open_deal_filters, properties)

    excluded_stages = {"closedwon", "closedlost"}
    open_deals = [d for d in all_open_deals if d["properties"].get("dealstage") not in excluded_stages]

    large_deals = [d for d in open_deals if float(d["properties"].get("amount") or 0) > 100000]
    all_deals.extend(large_deals)

    commit_deals = [d for d in open_deals if d["properties"].get("hs_forecast_category") == "commit"]
    all_deals.extend(commit_deals)

    late_stage_deals = [d for d in open_deals if d["properties"].get("dealstage") in late_stages]
    all_deals.extend(late_stage_deals)

    seen_ids = set()
    unique_deals = []
    for d in all_deals:
        if d["id"] not in seen_ids:
            seen_ids.add(d["id"])
            unique_deals.append(d)

    result = []
    for d in unique_deals:
        props = d["properties"]
        stage_id = props.get("dealstage")
        stage_label = stage_labels.get(stage_id, stage_id)

        result.append({
            "id": d["id"],
            "dealname": props.get("dealname"),
            "amount": float(props.get("amount") or 0),
            "dealstage": stage_label,
            "closedate": props.get("closedate"),
            "hs_forecast_category": props.get("hs_forecast_category"),
            "owner": _get_owner_name(props.get("hubspot_owner_id"))
        })

    result.sort(key=lambda x: x["amount"], reverse=True)

    return result
