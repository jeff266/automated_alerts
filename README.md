# Automated Sales Alerts

GitHub Actions-based automated sales reporting for Frontera Health.

## Weekly Sales Report

Runs every Monday at 9:00 AM PT and sends a sales report to the #sales-squad Slack channel via Zapier webhook.

### What's Included

- **Q2 Pacing**: Closed won revenue and pipeline generated vs targets
- **MTD Metrics**: Month-to-date booked revenue and new pipeline
- **Rep Activity**: Weekly calls, meetings, and self-sourced pipeline by rep
- **Deals to Watch**: Large/commit/late-stage deals
- **SDR Update**: MemoryBlue dial and connect metrics

### Setup

1. **Add GitHub Secrets** (Settings > Secrets and variables > Actions):
   - `HUBSPOT_TOKEN`: Your HubSpot private app token
   - `ZAPIER_WEBHOOK_URL`: Your Zapier webhook URL

2. **Create Zapier Zap**:
   - Trigger: Webhooks by Zapier > Catch Hook
   - Action: Slack > Send Channel Message
   - Map `text` field to the message body
   - Set channel to `#sales-squad`

### Manual Trigger

You can manually trigger the workflow from the Actions tab:
1. Go to Actions > Weekly Sales Report
2. Click "Run workflow"
3. Optionally specify a date or enable dry run mode

### Local Testing

```bash
export HUBSPOT_TOKEN="your-token"
export ZAPIER_WEBHOOK_URL="your-webhook-url"

cd scripts
python generate_weekly_sales_report.py --dry-run
```

### Report Sample

```
*Q2 Pacing | Where We Stand*
$258,090 closed (26% to $1M Q2 goal) | $1.06M pipeline generated (35% to $3M coverage goal) | 20 deals closed QTD

*May MTD*
$21,690 booked (7.0% to monthly goal) | +$335K new pipeline (33% to monthly goal) | 7 deals closed

*This Week's Activity (May 11 - 17)*
Bollman: 10+ activities (?E / 1C / 9M) | $66K self-sourced pipe | 3 deals closed | $13,320 booked
Tristan: 40+ activities (?E / 39C / 1M) | $150K self-sourced pipe
Batman: 11+ activities (?E / 7C / 4M) | $12K self-sourced pipe | 1 deal closed | $720 booked

*Deals to Watch*
Action Behavior Centers - AB ($300K, Discovery/Qualification, close 07/31) | ...

*SDR Update*
1741 dials | 29 connects (1.7% connect rate)
```

### Notes

- `?E` = Emails unavailable (requires `sales-email-read` OAuth scope)
- SDR metrics are cumulative over 60 days since MemoryBlue imports are batched
- Self-sourced pipeline excludes deals where associated contacts have MemoryBlue meetings
