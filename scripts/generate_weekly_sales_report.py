#!/usr/bin/env python3
"""
Weekly Sales Report Generator

Generates the weekly sales report and sends it to a Zapier webhook for Slack.

Usage:
    python generate_weekly_sales_report.py                    # Current week
    python generate_weekly_sales_report.py --date 2026-05-13  # Specific date's week

Environment Variables:
    HUBSPOT_TOKEN: HubSpot API token
    ZAPIER_WEBHOOK_URL: Zapier webhook URL for Slack
"""

import argparse
import json
import os
import requests
from datetime import datetime, date, timedelta

from weekly_sales_deals import (
    get_q2_closed_won,
    get_q2_pipeline_generated,
    get_mtd_closed_won,
    get_mtd_new_pipeline,
    get_weekly_closed_won,
    get_weekly_self_sourced_pipeline_by_owner,
    get_deals_to_watch,
)
from weekly_sales_activities import (
    get_activities_by_owner,
    get_memoryblue_activities,
)

# =============================================================================
# Constants
# =============================================================================

Q2_TARGET = 1_000_000
MONTHLY_TARGET = 310_000
PIPELINE_TARGET_Q2 = 3_000_000
MONTHLY_PIPELINE_TARGET = 1_000_000

# Q2 2026 date range
Q2_START = date(2026, 4, 1)
Q2_END = date(2026, 6, 30)

# Rep name mapping (HubSpot name -> display name)
REP_DISPLAY_NAMES = {
    "Sara Bollman": "Bollman",
    "Tristan Tancio": "Tristan",
    "Isaac Batman": "Batman",
    "Nate Phillips": "Batman",  # Alias
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_week_dates(reference_date: date) -> tuple:
    """Get the Monday-Sunday week containing the reference date."""
    days_since_monday = reference_date.weekday()
    week_start = reference_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def get_mtd_dates(reference_date: date) -> tuple:
    """Get month-to-date range ending at reference_date."""
    month_start = reference_date.replace(day=1)
    return month_start, reference_date


def format_currency(amount: float) -> str:
    """Format a number as currency (e.g., $123,456)."""
    return f"${amount:,.0f}"


def format_currency_short(amount: float) -> str:
    """Format large currency amounts in short form (e.g., $1.2M, $500K)."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"${amount / 1_000:.0f}K"
    else:
        return f"${amount:,.0f}"


def format_percentage(value: float, target: float) -> str:
    """Calculate and format percentage of target."""
    if target == 0:
        return "0%"
    pct = (value / target) * 100
    if pct >= 10:
        return f"{pct:.0f}%"
    else:
        return f"{pct:.1f}%"


# =============================================================================
# Report Generation
# =============================================================================

def generate_report(week_start: date, week_end: date) -> str:
    """Generate the weekly sales report."""
    mtd_start, mtd_end = get_mtd_dates(week_end)
    month_name = week_end.strftime("%B")
    week_range_str = f"{week_start.strftime('%B')} {week_start.day} - {week_end.day}"

    # Q2 Pacing Metrics
    print("Fetching Q2 closed won...")
    qtd_closed = get_q2_closed_won()
    qtd_closed_amount = qtd_closed.get("total_amount", 0)
    qtd_closed_count = qtd_closed.get("count", 0)

    print("Fetching Q2 pipeline generated...")
    qtd_pipeline = get_q2_pipeline_generated()
    qtd_pipeline_amount = qtd_pipeline.get("total_amount", 0)

    q2_pacing_pct = format_percentage(qtd_closed_amount, Q2_TARGET)
    pipeline_pacing_pct = format_percentage(qtd_pipeline_amount, PIPELINE_TARGET_Q2)

    # MTD Metrics
    print(f"Fetching {month_name} MTD closed won...")
    mtd_closed = get_mtd_closed_won(mtd_end.month, mtd_end.year)
    mtd_closed_amount = mtd_closed.get("total_amount", 0)
    mtd_closed_count = mtd_closed.get("count", 0)

    print(f"Fetching {month_name} MTD new pipeline...")
    mtd_pipeline = get_mtd_new_pipeline(mtd_end.month, mtd_end.year)
    mtd_pipeline_amount = mtd_pipeline.get("total_amount", 0)

    mtd_booked_pct = format_percentage(mtd_closed_amount, MONTHLY_TARGET)
    mtd_pipeline_pct = format_percentage(mtd_pipeline_amount, MONTHLY_PIPELINE_TARGET)

    # Weekly Closed Won by Rep
    print("Fetching weekly closed won...")
    weekly_closed = get_weekly_closed_won(week_start, week_end)
    weekly_deals = weekly_closed.get("deals", [])

    rep_closed = {}
    rep_booked = {}
    for deal in weekly_deals:
        owner = deal.get("owner", "Unknown")
        display_name = REP_DISPLAY_NAMES.get(owner, owner.split()[0] if owner else "Unknown")
        amount = deal.get("amount", 0)
        rep_closed[display_name] = rep_closed.get(display_name, 0) + 1
        rep_booked[display_name] = rep_booked.get(display_name, 0) + amount

    # Weekly Self-Sourced Pipeline by Rep
    print("Fetching weekly self-sourced pipeline by owner...")
    self_sourced_data = get_weekly_self_sourced_pipeline_by_owner(week_start, week_end)
    weekly_pipeline_by_owner = self_sourced_data.get("by_owner", {})

    rep_pipeline = {}
    for owner, amount in weekly_pipeline_by_owner.items():
        display_name = REP_DISPLAY_NAMES.get(owner, owner.split()[0] if owner else "Unknown")
        rep_pipeline[display_name] = rep_pipeline.get(display_name, 0) + amount

    # Rep Activity (Emails, Calls, Meetings)
    print("Fetching rep activities...")
    activities_by_owner = get_activities_by_owner(week_start, week_end)

    rep_activities = {}
    for owner, stats in activities_by_owner.items():
        display_name = REP_DISPLAY_NAMES.get(owner, owner.split()[0] if owner else "Unknown")
        if display_name in rep_activities:
            rep_activities[display_name]['emails'] += stats.get('emails', 0)
            rep_activities[display_name]['calls'] += stats.get('calls', 0)
            rep_activities[display_name]['meetings'] += stats.get('meetings', 0)
            rep_activities[display_name]['total'] += stats.get('total', 0)
        else:
            rep_activities[display_name] = {
                'emails': stats.get('emails', 0),
                'calls': stats.get('calls', 0),
                'meetings': stats.get('meetings', 0),
                'total': stats.get('total', 0),
            }

    # Build Rep Lines
    target_reps = ["Bollman", "Tristan", "Batman"]
    rep_lines = []

    for rep in target_reps:
        parts = []

        activity = rep_activities.get(rep, {'emails': 0, 'calls': 0, 'meetings': 0, 'total': 0})
        emails = activity.get('emails', 0)
        calls = activity.get('calls', 0)
        meetings = activity.get('meetings', 0)
        total = emails + calls + meetings
        email_str = f"{emails}E" if emails > 0 else "?E"
        parts.append(f"{rep}: {total}+ activities ({email_str} / {calls}C / {meetings}M)")

        pipeline_amt = rep_pipeline.get(rep, 0)
        if pipeline_amt > 0:
            parts.append(f"{format_currency_short(pipeline_amt)} self-sourced pipe")

        closed_count = rep_closed.get(rep, 0)
        if closed_count > 0:
            parts.append(f"{closed_count} deal{'s' if closed_count != 1 else ''} closed")

        booked_amt = rep_booked.get(rep, 0)
        if booked_amt > 0:
            parts.append(f"{format_currency(booked_amt)} booked")

        rep_lines.append(" | ".join(parts))

    # Deals to Watch
    print("Fetching deals to watch...")
    deals_to_watch = get_deals_to_watch()
    deals_to_watch_parts = []

    for deal in deals_to_watch[:5]:
        name = deal.get("dealname", "Unknown")
        amount = deal.get("amount", 0)
        stage = deal.get("dealstage", "")
        forecast = deal.get("hs_forecast_category", "")
        close_date = deal.get("closedate", "")

        deal_str = f"{name} ({format_currency_short(amount)}"
        if forecast:
            deal_str += f", {forecast.title()}"
        elif stage:
            deal_str += f", {stage}"
        if close_date:
            try:
                cd = datetime.fromisoformat(close_date.replace('Z', '+00:00'))
                deal_str += f", close {cd.strftime('%m/%d')}"
            except:
                pass
        deal_str += ")"
        deals_to_watch_parts.append(deal_str)

    deals_to_watch_str = " | ".join(deals_to_watch_parts) if deals_to_watch_parts else "No deals flagged"

    # SDR Metrics (MemoryBlue)
    print("Fetching SDR metrics (last 60 days)...")
    sdr_start = week_end - timedelta(days=60)
    sdr = get_memoryblue_activities(sdr_start, week_end)
    dials = sdr.get("total_dials", 0)
    connects = sdr.get("connects", 0)
    connect_rate = sdr.get("connect_rate", 0)

    sdr_note = "" if dials > 0 else " (data not yet imported)"

    # Build Final Report
    report_lines = [
        f"*Q2 Pacing | Where We Stand*",
        f"{format_currency(qtd_closed_amount)} closed ({q2_pacing_pct} to $1M Q2 goal) | "
        f"{format_currency_short(qtd_pipeline_amount)} pipeline generated ({pipeline_pacing_pct} to $3M coverage goal) | "
        f"{qtd_closed_count} deals closed QTD",
        "",
        f"*{month_name} MTD*",
        f"{format_currency(mtd_closed_amount)} booked ({mtd_booked_pct} to monthly goal) | "
        f"+{format_currency_short(mtd_pipeline_amount)} new pipeline ({mtd_pipeline_pct} to monthly goal) | "
        f"{mtd_closed_count} deals closed",
        "",
        f"*This Week's Activity ({week_range_str})*",
    ]

    for line in rep_lines:
        report_lines.append(line)

    report_lines.extend([
        "",
        "*Deals to Watch*",
        deals_to_watch_str,
        "",
        "*SDR Update*",
        f"{dials} dials | {connects} connects ({connect_rate:.1f}% connect rate){sdr_note}",
    ])

    return "\n".join(report_lines)


def send_to_zapier(report: str, webhook_url: str) -> bool:
    """Send the report to Zapier webhook."""
    payload = {
        "text": report,
        "channel": "#sales-squad",
        "username": "Weekly Sales Bot",
    }

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print(f"Successfully sent to Zapier webhook")
        return True
    except Exception as e:
        print(f"Error sending to Zapier: {e}")
        return False


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description="Generate weekly sales report for Slack")
    parser.add_argument("--date", type=str, default=None, help="Reference date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Don't send to webhook, just print")
    args = parser.parse_args()

    # Check for required environment variables
    hubspot_token = os.environ.get("HUBSPOT_TOKEN")
    zapier_webhook = os.environ.get("ZAPIER_WEBHOOK_URL")

    if not hubspot_token:
        print("Error: HUBSPOT_TOKEN environment variable not set")
        return 1

    if not zapier_webhook and not args.dry_run:
        print("Error: ZAPIER_WEBHOOK_URL environment variable not set")
        return 1

    # Determine reference date
    if args.date:
        try:
            reference_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.")
            return 1
    else:
        reference_date = date.today()

    # Get week boundaries
    week_start, week_end = get_week_dates(reference_date)

    print(f"Generating report for week: {week_start} to {week_end}")
    print("=" * 60)

    # Generate the report
    report = generate_report(week_start, week_end)

    print("\n" + "=" * 60)
    print("REPORT OUTPUT:")
    print("=" * 60)
    print(report)
    print("=" * 60)

    # Send to Zapier
    if not args.dry_run:
        print("\nSending to Zapier webhook...")
        success = send_to_zapier(report, zapier_webhook)
        return 0 if success else 1
    else:
        print("\n[DRY RUN] Skipping webhook send")
        return 0


if __name__ == "__main__":
    exit(main())
