# BRIGHT CONNECTION INTEGRATION READINESS
**Author:** Aman Pal
**Date:** 2025-06-01
**Phase:** Learn — Pre-Build Assessment
**Status:** HONEST ASSESSMENT — No fabricated availability

---

## 1. Available APIs (Confirmed vs Contract-Defined)

| System | API Availability | Basis |
|---|---|---|
| Biz Analyst | CONTRACT-DEFINED | API shape known (`https://api.bizanalyst.in/v1`), credentials not yet provided |
| Bright CRM | CONTRACT-DEFINED | OAuth2 endpoint assumed, token not yet provided |
| Bright DMS | CONTRACT-DEFINED | API key auth assumed, key not yet provided |
| Bright Inventory | CONTRACT-DEFINED | API key auth assumed, key not yet provided |
| Bright Orders | CONTRACT-DEFINED | API key auth assumed, key not yet provided |
| Bright Sales | CONTRACT-DEFINED | API key auth assumed, key not yet provided |
| Bright Collections | CONTRACT-DEFINED | API key auth assumed, key not yet provided |
| Bright Dealer | CONTRACT-DEFINED | API key auth assumed, key not yet provided |
| TallyPrime 6.1 | CONDITIONALLY AVAILABLE | XML gateway on LAN at 192.168.0.72:9000, test_mode=true currently |

**No real API credentials have been provided for any Bright Connection system.**
All connectors currently operate in stub/test mode.

---

## 2. Required Credentials

| Connector | Credential | Env Variable | Status |
|---|---|---|---|
| biz_analyst | API Key + Base URL | `SETU_BA_API_KEY`, `SETU_BA_BASE_URL` | NOT PROVIDED |
| bright_crm | OAuth2 Token | `SETU_CRM_OAUTH_TOKEN` | NOT PROVIDED |
| bright_dms | API Key | `SETU_DMS_API_KEY` | NOT PROVIDED |
| bright_inventory | API Key | `SETU_INV_API_KEY` | NOT PROVIDED |
| bright_orders | API Key | `SETU_ORDERS_API_KEY` | NOT PROVIDED |
| bright_sales | API Key | `SETU_SALES_API_KEY` | NOT PROVIDED |
| bright_collections | API Key | `SETU_COLLECTIONS_API_KEY` | NOT PROVIDED |
| bright_dealer | API Key | `SETU_DEALER_API_KEY` | NOT PROVIDED |
| tally | Host + Port | `SETU_TALLY_HOST`, `SETU_TALLY_PORT` | LAN-ONLY (192.168.0.72:9000) |

Credentials must be injected via environment variables. Never committed to Git.

---

## 3. Authentication Methods

| Connector | Method | Implementation Status |
|---|---|---|
| biz_analyst | API Key in `X-API-Key` header | Stub — real HTTP call pending credentials |
| bright_crm | Bearer token in `Authorization` header | Stub — real HTTP call pending token |
| bright_dms | API Key in `X-API-Key` header | Stub — real HTTP call pending credentials |
| bright_inventory | API Key in `X-API-Key` header | Stub — real HTTP call pending credentials |
| bright_orders | API Key in `X-API-Key` header | Stub — real HTTP call pending credentials |
| bright_sales | API Key in `X-API-Key` header | Stub — real HTTP call pending credentials |
| bright_collections | API Key in `X-API-Key` header | Stub — real HTTP call pending credentials |
| bright_dealer | API Key in `X-API-Key` header | Stub — real HTTP call pending credentials |
| tally | HTTP XML to port 9000 (no auth) | Bridge agent built, LAN-only |

---

## 4. Supported Entities (Per Connector)

| Connector | Entities |
|---|---|
| biz_analyst | order, collection, outstanding |
| bright_crm | visit, beat_plan, route_plan, display_compliance |
| bright_dms | dealer, scheme, product_catalogue |
| bright_inventory | inventory, damaged_goods |
| bright_orders | order, invoice, payment_receipt |
| bright_sales | order |
| bright_collections | collection, outstanding |
| bright_dealer | dealer |
| tally | ledger, invoice, payment, outstanding |

---

## 5. API Endpoints (Known / Assumed)

| Connector | Base URL | Source |
|---|---|---|
| biz_analyst | `https://api.bizanalyst.in/v1` | Tenant config |
| bright_crm | UNKNOWN — not yet provided | Assumption only |
| bright_dms | UNKNOWN — not yet provided | Assumption only |
| bright_inventory | UNKNOWN — not yet provided | Assumption only |
| bright_orders | UNKNOWN — not yet provided | Assumption only |
| bright_sales | UNKNOWN — not yet provided | Assumption only |
| bright_collections | UNKNOWN — not yet provided | Assumption only |
| bright_dealer | UNKNOWN — not yet provided | Assumption only |
| tally | `http://192.168.0.72:9000` | Confirmed (LAN) |

---

## 6. Known Unavailable Systems

- **All Bright Connection API endpoints**: Base URLs not provided. Cannot make real HTTP calls.
- **Real API credentials**: No keys or tokens provided for any connector.
- **Canonical MasterDB (production)**: The ecosystem's production MongoDB-backed MasterDB boundary (owned by KAVY) has not been provided. Current implementation is file-backed persistence (local SQLite/JSON) as an integration boundary placeholder.
- **InsightFlow production capability handlers**: No real capability handlers registered from the SETU ecosystem. Dispatch is proven but handlers are test stubs.
- **NIYANTRAN/SETU ERP runtime**: Not available in this environment.
- **Tally (live)**: Port 9000 is LAN-local. Bridge agent built but `test_mode=true`. Live test requires physical LAN access to 192.168.0.72.

---

## 7. Mapping Assumptions

1. All Bright Connection APIs return JSON. If any return XML or CSV, normalize() must be updated.
2. `dealer_code` is the canonical cross-system dealer identifier across all connectors.
3. `order_id`, `invoice_id`, `collection_id` are stable source-system IDs suitable for `entity_id`.
4. Currency defaults to INR unless explicitly provided.
5. Biz Analyst uses `party_code` for what other systems call `dealer_code` — mapped in normalize().
6. Bright CRM uses `crm_visit_id`, `crm_beat_id`, etc. as source IDs — mapped to canonical IDs.
7. OAuth2 token for bright_crm is assumed to be a long-lived bearer token, not a short-lived JWT requiring refresh. If refresh is needed, authenticate() must be extended.

---

## 8. Contract Dependencies

| Dependency | Owner | Status |
|---|---|---|
| MDURecord schema v1.0 | Nupur / MDU | FROZEN — no changes made |
| MasterDB integration boundary | KAVY / MDU | Placeholder implemented — awaiting canonical boundary |
| ConnectorRuntimeContract v1.0 | SETU / Rudra | FROZEN — no changes made |
| InsightFlow capability handlers | SETU ecosystem | Test stubs only — real handlers from ecosystem pending |
| Tenant config authority | Raj / Bright Connection | Config exists, credentials pending |
| Production deployment | Alay | Not yet started |
| Final regression | Rayyan | Pending live proof |

---

## 9. Known Unknowns

1. **Real API base URLs** for all Bright Connection systems except Biz Analyst.
2. **Rate limits** on any Bright Connection API — retry policy set to 3 attempts but limits unknown.
3. **Pagination** — all connectors assume flat list responses. If APIs paginate, fetch_data() must handle cursor/page params.
4. **Webhook secrets** — bright_crm and bright_orders declare `supports_webhook=True` but no webhook secret or endpoint registration process is known.
5. **OAuth2 token refresh** — if bright_crm token expires, the current authenticate() will fail silently. Refresh flow unknown.
6. **Tally company name** — TallyPrime must have an active company loaded. "Companies to load on startup" was set to None in the screenshot. This must be corrected before live Tally test.
7. **MasterDB production schema** — KAVY's canonical MasterDB may have additional required fields beyond what MDURecord provides. Schema compatibility must be verified.
8. **InsightFlow production routing rules** — which entity types trigger which capabilities in the production ecosystem is not known.

---

## 10. Integration Readiness Summary

| Area | Readiness | Blocker |
|---|---|---|
| Connector SDK | READY | None |
| MDU normalization | READY (stub data) | Real API data needed to verify field coverage |
| Authentication boundary | READY (env-var injection) | Real credentials needed |
| MasterDB persistence | READY (file-backed local) | KAVY canonical boundary needed for production |
| InsightFlow dispatch | READY | Real capability handlers from ecosystem needed |
| Replay | READY | None |
| Tenant isolation | READY | None |
| Live API connectivity | BLOCKED | API base URLs + credentials not provided |
| Tally live | BLOCKED | LAN access + active company in TallyPrime needed |
| Production deployment | BLOCKED | Alay boundary not started |

**Verdict: Framework is integration-ready. Live proof is blocked on credentials and API endpoint disclosure from Bright Connection.**
