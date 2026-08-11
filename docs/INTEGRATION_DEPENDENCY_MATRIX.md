# Integration Dependency Matrix — Bright Connection

## Connector to Entity Type Matrix

| Connector | dealer | order | invoice | payment_receipt | collection | outstanding | inventory | damaged_goods | product_catalogue | scheme | visit | beat_plan | route_plan | display_compliance | ledger |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| biz_analyst | | X | | | X | X | | | | | | | | | |
| tally* | | | X | | | X | | | | | | | | | X |
| bright_crm | | | | | | | | | | | X | X | X | X | |
| bright_dms | X | | | | | | | | X | X | | | | | |
| bright_inventory | | | | | | | X | X | | | | | | | |
| bright_orders | | X | X | X | | | | | | | | | | | |
| bright_sales | | X | | | | | | | | | | | | | |
| bright_collections | | | | | X | X | | | | | | | | | |
| bright_dealer | X | | | | | | | | | | | | | | |

*Tally: contract defined, system availability depends on customer environment

---

## Entity Type to SETU Capability Matrix

| Entity Type | Dealer Mgmt | Order Mgmt | Inventory | Collections | Field Ops | Product Catalogue | Schemes | InsightFlow |
|---|---|---|---|---|---|---|---|---|
| dealer | X | | | | | | | X |
| order | | X | | | | | | X |
| invoice | | X | | X | | | | X |
| payment_receipt | | | | X | | | | X |
| collection | | | | X | | | | X |
| outstanding | | | | X | | | | X |
| inventory | | | X | | | | | X |
| damaged_goods | | | X | | X | | | X |
| product_catalogue | | | | | | X | | X |
| scheme | | | | | | | X | X |
| visit | | | | | X | | | X |
| beat_plan | | | | | X | | | X |
| route_plan | | | | | X | | | X |
| display_compliance | | | | | X | | | X |
| ledger | | | | X | | | | X |

---

## Connector Authentication Dependencies

| Connector | Auth Type | External Dependency | Availability |
|---|---|---|---|
| biz_analyst | api_key | Biz Analyst API | Required |
| tally | basic | Tally XML Gateway (localhost) | Optional |
| bright_crm | oauth2 | Bright CRM OAuth endpoint | Required |
| bright_dms | api_key | Bright DMS API | Required |
| bright_inventory | api_key | Bright Inventory API | Required |
| bright_orders | api_key | Bright Orders API | Required |
| bright_sales | api_key | Bright Sales API | Required |
| bright_collections | api_key | Bright Collections API | Required |
| bright_dealer | api_key | Bright Dealer API | Required |

---

## Sync Schedule Matrix

| Connector | Schedule | Frequency | Notes |
|---|---|---|---|
| biz_analyst | 0 */6 * * * | Every 6 hours | Financial data |
| tally | 0 2 * * * | Daily at 2am | When available |
| bright_crm | */30 * * * * | Every 30 min | Field activity |
| bright_dms | 0 1 * * * | Daily at 1am | Master data |
| bright_inventory | 0 */4 * * * | Every 4 hours | Stock levels |
| bright_orders | */15 * * * * | Every 15 min | Live orders |
| bright_sales | 0 0 * * * | Daily midnight | History |
| bright_collections | */30 * * * * | Every 30 min | Payments |
| bright_dealer | 0 1 * * * | Daily at 1am | Master data |

---

## Data Flow Dependencies

```
Bright Connection Enterprise Systems
        |
        +-- Biz Analyst API ---------> biz_analyst connector
        +-- Tally XML Gateway -------> tally connector (optional)
        +-- Bright CRM API ----------> bright_crm connector
        +-- Bright DMS API ----------> bright_dms connector
        +-- Bright Inventory API ----> bright_inventory connector
        +-- Bright Orders API -------> bright_orders connector
        +-- Bright Sales API --------> bright_sales connector
        +-- Bright Collections API --> bright_collections connector
        +-- Bright Dealer API -------> bright_dealer connector
        |
        v
  ConnectorPipeline (SETU runtime)
        |
        v
  MDURecord (canonical)
        |
        v
  MasterDB (tenant-isolated)
        |
        v
  InsightFlow (capability dispatch)
        |
        v
  ReplayEngine (deterministic replay)
```

---

## Connector Independence Matrix

Each connector can be replaced independently. Replacement requires:

| Connector | Replacement Trigger | Impact on SETU Core |
|---|---|---|
| biz_analyst | Biz Analyst API version change | None — update normalize() only |
| tally | Tally version upgrade | None — update XML parsing only |
| bright_crm | CRM platform migration | None — update field mapping only |
| bright_dms | DMS platform migration | None — update field mapping only |
| bright_inventory | Inventory system change | None — update field mapping only |
| bright_orders | Order system change | None — update field mapping only |
| bright_sales | Sales system change | None — update field mapping only |
| bright_collections | Collections system change | None — update field mapping only |
| bright_dealer | Dealer system change | None — update field mapping only |
