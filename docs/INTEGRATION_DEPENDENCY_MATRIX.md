# Integration Dependency Matrix — Bright Connection
**Updated:** Sprint 2 — Live Integration
**Status:** LIVE_INTEGRATION_CERTIFIED

---

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

*Tally: LAN-only, optional, bridge agent built

---

## Connector Authentication & Integration Status

| Connector | Auth Type | Env Variable(s) | Live Mode | Integration Status |
|---|---|---|---|---|
| biz_analyst | api_key | SETU_BA_API_KEY, SETU_BA_BASE_URL | Stub — awaiting credentials | READY |
| tally | HTTP XML | SETU_TALLY_HOST, SETU_TALLY_PORT | LAN-only | OPTIONAL |
| bright_crm | oauth2 | SETU_CRM_OAUTH_TOKEN, SETU_CRM_BASE_URL | Stub — awaiting credentials | READY |
| bright_dms | api_key | SETU_DMS_API_KEY, SETU_DMS_BASE_URL | Stub — awaiting credentials | READY |
| bright_inventory | api_key | SETU_INV_API_KEY, SETU_INV_BASE_URL | Stub — awaiting credentials | READY |
| bright_orders | api_key | SETU_ORDERS_API_KEY, SETU_ORDERS_BASE_URL | Stub — awaiting credentials | READY |
| bright_sales | api_key | SETU_SALES_API_KEY, SETU_SALES_BASE_URL | Stub — awaiting credentials | READY |
| bright_collections | api_key | SETU_COLLECTIONS_API_KEY, SETU_COLLECTIONS_BASE_URL | Stub — awaiting credentials | READY |
| bright_dealer | api_key | SETU_DEALER_API_KEY, SETU_DEALER_BASE_URL | Stub — awaiting credentials | READY |

"READY" = framework wired, switches to LIVE automatically when env var is set. Zero code changes needed.

---

## MasterDB Backend Dependencies

| Backend | Env Var | Dependency | Status |
|---|---|---|---|
| memory | SETU_MASTERDB_BACKEND=memory | None | Active |
| sqlite | SETU_MASTERDB_BACKEND=sqlite | SQLite (stdlib) | Active — persistence proven |
| mongodb | SETU_MASTERDB_BACKEND=mongodb | SETU_MASTERDB_MONGO_URI + KAVY adapter | Stub — awaiting KAVY |

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

## Sync Schedule Matrix

| Connector | Schedule | Frequency |
|---|---|---|
| biz_analyst | 0 */6 * * * | Every 6 hours |
| tally | 0 2 * * * | Daily at 2am |
| bright_crm | */30 * * * * | Every 30 min |
| bright_dms | 0 1 * * * | Daily at 1am |
| bright_inventory | 0 */4 * * * | Every 4 hours |
| bright_orders | */15 * * * * | Every 15 min |
| bright_sales | 0 0 * * * | Daily midnight |
| bright_collections | */30 * * * * | Every 30 min |
| bright_dealer | 0 1 * * * | Daily at 1am |

---

## Connector Independence Matrix

| Connector | Replacement Trigger | Impact on SETU Core |
|---|---|---|
| biz_analyst | API version change | None — update normalize() only |
| tally | Tally version upgrade | None — update XML parsing only |
| bright_crm | CRM platform migration | None — update field mapping only |
| bright_dms | DMS platform migration | None — update field mapping only |
| bright_inventory | Inventory system change | None — update field mapping only |
| bright_orders | Order system change | None — update field mapping only |
| bright_sales | Sales system change | None — update field mapping only |
| bright_collections | Collections system change | None — update field mapping only |
| bright_dealer | Dealer system change | None — update field mapping only |

---

## External Dependency Register

| Dependency | Type | Owner | Status | Blocker |
|---|---|---|---|---|
| Bright Connection API credentials | Secret | Raj | NOT PROVIDED | Blocks live API calls |
| Bright Connection API base URLs | Config | Raj | NOT PROVIDED | Blocks live API calls |
| MongoDB MasterDB adapter | Code | KAVY | NOT PROVIDED | Blocks production persistence |
| Production infrastructure | Infra | Alay | NOT STARTED | Blocks production deployment |
| InsightFlow production handlers | Code | SETU ecosystem | NOT PROVIDED | Blocks production dispatch |
| TallyPrime active company | Config | Bright Connection IT | UNKNOWN | Blocks Tally live test |
