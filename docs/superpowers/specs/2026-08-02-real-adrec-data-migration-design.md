# Real ADREC Data Migration — Design

**Date:** 2026-08-02
**Status:** Approved, pending implementation plan
**Target:** Aug 6 submission

## Context

The user exported ADREC's own market-data dashboard (Transactions / Residential Leases / Price Indices tabs, via the site's Export buttons) to `ADREC_DATA/` (untracked, not committed). This is real published market data, not scraped or PII-bearing — the same figures the dashboard itself renders. The question: replace the project's statistically-generated synthetic dataset with this real data, in time for the Aug 6 submission, without breaking the working pipeline (30/30 golden-question eval, EN+AR retrieval, calibration tests).

**Motivation (user's own framing):** the interview narrative "I connected this POC to ADREC's real data, and my schema follows theirs" is worth more than eliminating migration risk. The user explicitly asked not to over-engineer this — it is a graduate-program POC, not a production system, and small data-quality gaps (unreconciled totals, missing sub-fields) are acceptable if documented rather than chased.

## What's in ADREC_DATA

- `Transactions/recent_sales_2019-2026.csv` — **118,733 real row-level transactions**, 2019-01-02 → 2026-07-31, headerless but field order matches the "Recent Sales" shape already researched in plan.md: asset class, property type, date, sold area, plot area, layout, district, community, project, price AED, a `count` field (mostly 1.0, some fractional — meaning unconfirmed, treated as immaterial per user direction), rate AED/sqm, sale type (off-plan/ready/court-mandated), market type (primary/secondary).
- `Transactions/*_by_period_{monthly,quarterly,yearly}.xlsx`, `sales_by_asset_*.xlsx`, `total_transactions_*.xlsx`, `resi_sales_finance_*.xlsx` — pre-aggregated rollups (the same numbers behind the dashboard's charts). Used only to build the district→municipality lookup and as reconciliation reference, not loaded as fact data.
- `Residential Leases/lease_residential.xlsx` and `lease_price_by_period.xlsx` — 13,313 rows each, same dimensional grain (Period, Date, Property Type, Municipality, District, Layout), one carrying `Leased Units`, the other `Sum of active_value_aed`. `Community`/`Project Name` are 100% NULL in both — real rental data bottoms out at district level.
- `Price Indices/*.xlsx` — 5 files (sale, rent, office, retail, industrial), monthly, mostly citywide (no consistent per-district breakdown across all five).

**Verified finding:** the project's existing 25 curated `communities` rows (Yas Island, Al Reem Island, Khalifa City, etc.) match ADREC's real "district" field almost exactly — by exact string for several, by trivial spelling variant for the rest (`Al Rahah`/`Al Raha Beach`, `Al Shamkhah`/`Al Shamkha`). This means the existing Arabic alias map and its coverage test survive the migration untouched for those 25 — the largest risk in a 4-day real-data migration turns out not to apply.

**Known, accepted limitation:** summing `price_aed` for residential transactions in FY2025 from the raw CSV (AED 83.2bn) does not tie to the equivalent aggregate workbook or the existing `calibration.json` anchor (AED 76.1bn / 76bn, ADREC biannual report) — a ~9.3% gap. Per user direction, this is documented and not chased further; it does not block using the raw CSV as the transaction source of truth.

## Scope: Approach A

Real data for **transactions, price indices, and rentals**. Synthetic, clearly labeled, for **mortgages and brokers** (ADREC's export has no per-geography mortgage breakdown and no broker data at all). This keeps the project's sharpest differentiator — a rent-vs-price yield question, which requires joining transactions and rentals, something the dashboard's separate Transactions/Leases tabs cannot do — running on real data on both sides of the join.

## Schema changes

### `transactions`

```sql
CREATE TABLE transactions (
  id bigserial PRIMARY KEY,
  transaction_date date NOT NULL,
  community_id int NOT NULL REFERENCES communities(id),
  project_id int REFERENCES projects(id),          -- left NULL for loaded rows
  property_type_id int NOT NULL REFERENCES property_types(id),
  layout_id int REFERENCES layouts(id),
  market_type text CHECK (market_type IN ('primary','secondary')),  -- nullable: ~0.15% of real rows have no market type
  is_offplan boolean NOT NULL DEFAULT false,
  sold_area_sqm numeric(10,2),
  plot_area_sqm numeric(10,2),
  price_aed numeric(14,2) NOT NULL,
  rate_aed_sqm numeric(10,2)
);
```

Changes from current schema: `buyer_origin` column removed. The existing `sale_type` column (invented `sale`/`resale` values) is replaced by two real ADREC fields, which are genuinely distinct: `market_type` (real `primary`/`secondary`, nullable) and `is_offplan` (derived from the real off-plan/ready/court-mandated field — `off-plan` → `true`, `ready` and `court-mandated` → `false`; court-mandated sales are a rare edge case, ~0.7% of rows, folded into `is_offplan = false` rather than modeled separately).

**Load filter:** `asset_class IN ('residential', 'commercial')` only — drops agricultural/educational/healthcare/industrial/religious/recreational/infrastructural rows (~5% of the CSV), out of scope for an urban real-estate analytics tool.

### `property_types`

Expands from the current 5 generic buckets to ADREC's real categories: Apartment, Villa, Townhouse/Attached Villa, Plot for Villa, Residential Complex, Duplex, Penthouse, Office, Retail, Mall/Market/Retail Center, Office Complex, plus an `Other` bucket for the long tail (each remaining real category is <0.5% of rows).

### `communities` / `districts` / `municipalities`

`name_ar` becomes nullable on all three geography tables (currently `NOT NULL`). The 25 curated communities keep their existing rows and Arabic names unchanged. For the ~108 additional real districts: one new `districts` row per real district (English name, parent municipality resolved via a lookup built from the Municipality+District pairs already present in the aggregate workbooks), and one same-named `communities` row under it — real data gives no finer split for these, so district and community are deliberately degenerate (1:1) for the non-curated set. These load English-only; Arabic retrieval for them is a documented POC limitation, not a bug to fix before Aug 6.

### `price_indices`

Shape unchanged (`month`, `index_type`, `property_type_id`, `index_value`, no geography column) — this already matches how the real index files are published (citywide). `property_type_id` values expand to the real index categories (all-property-types, Apartment, Villa, Office, Retail, Industrial). Direct load from the 5 real workbooks.

### `rental_contracts` → `rental_market_stats`

Table renamed and regrained from event-level to aggregate-cell-level, because ADREC does not publish per-lease records:

```sql
CREATE TABLE rental_market_stats (
  id bigserial PRIMARY KEY,
  period_end date NOT NULL,
  community_id int NOT NULL REFERENCES communities(id),
  property_type_id int NOT NULL REFERENCES property_types(id),
  layout_id int REFERENCES layouts(id),
  leased_units int NOT NULL,
  total_annual_rent_aed numeric(16,2) NOT NULL
);
```

Average annual rent per unit = `total_annual_rent_aed / leased_units`, computed at query time. Sourced by joining `lease_residential.xlsx` (leased units) and `lease_price_by_period.xlsx` (value) on their shared dimensional grain (Period, Date, Property Type, Municipality, District, Layout) — this 1:1 join needs to be verified during implementation, not assumed.

**Cost:** any question phrased as "how many rental contracts" changes meaning (it's now leased-unit counts per aggregate cell, not individual contract rows). Prompt guidance and any affected golden question need to reflect the new grain.

### `mortgages`, `brokers`

Unchanged — both remain the existing synthetic generator output. Documented in the submission as: *"transaction, price-index, and rental data are ADREC's real published figures; mortgage distribution and broker records are modeled, because that level of detail isn't part of ADREC's public export."*

## Data mapping summary

| Real field | Target |
|---|---|
| `asset_class` (filtered to residential/commercial) | scope filter, not stored |
| `property_type` | `property_types` (expanded categories + Other) |
| `date` | `transaction_date` |
| `sold_area_sqm`, `plot_area_sqm` | direct copy |
| `layout` ("4 beds", "unclassified") | `layouts` (direct match; unclassified → NULL) |
| `district` | `communities.name_en` (existing 25 curated + ~108 new) |
| `community`, `project` (fine-grained real fields) | dropped — too granular for the POC, `project_id` stays NULL |
| `price_aed`, `rate_aed_sqm` | direct copy (raw `price_aed`, not `× count`) |
| `sale_type` (off-plan/ready/court-mandated) | `is_offplan` boolean (court-mandated folds into `false`) |
| `market_type` (primary/secondary) | `market_type` (new nullable column, replaces `buyer_origin`) |

## Eval, prompt, and alias impact

- **Golden questions:** remove `en-foreign-buyer-value-2025`, `ar-foreign-buyer-value-2025` (`backend/tests/eval/golden_questions.json`); remove `en-foreign-share` example chip (`backend/app/resources/examples.json`). Replace with `market_type`-based equivalents in both languages (e.g., share of primary vs. secondary market transactions). Any rental-related golden question's reference SQL is rewritten for the new `rental_market_stats` grain.
- **`schema_aliases.json`:** drop buyer-origin/FDI phrases (EN + AR); add EN/AR phrases for `market_type` and the expanded `property_types` list.
- **`calibration.json`:** remove `fdi_value_ytd2026` and `foreign_growth_share_fy2025` anchors (no real basis once `buyer_origin` is gone). Remaining anchors (transaction value/volume, price indices, rented units) become regression checks against the real loaded data rather than "did the sampler hit its calibration target" checks.
- **`test_calibration.py`:** reworked accordingly — assertions shift from statistical-target tolerance to sanity bounds on the real loaded data.
- Full 30-question golden eval (`RUN_GOLDEN_EVAL=1 pytest tests/eval`) re-run after migration; must be clean (or any regressions understood and accepted) before calling the chunk done.

## Migration approach

A new data-loading script (parsing `ADREC_DATA/` exports, applying the mapping rules above, bulk-inserting) replaces the statistical-sampling logic in `backend/scripts/generate_dataset.py` for `transactions`, `price_indices`, and `rental_market_stats`. The existing mortgage/broker generation code is untouched. Schema migration (`backend/db/schema.sql`, `backend/db/reference_seed.sql`) adds the new columns/tables and the ~108 additional geography rows before the loader runs. `important-findings.md` gets an entry recording the mapping decisions and known limitations (the CSV/aggregate reconciliation gap, Arabic coverage bounded to the curated 25) so they're traceable without being re-litigated.

`ADREC_DATA/` itself stays untracked — the loader script reads from it locally but nothing under that path is ever committed.

## Out of scope for this migration

- Reconciling the 9.3% CSV-vs-aggregate-workbook gap in FY2025 transaction value.
- Arabic aliases for the ~108 non-curated districts.
- Real per-geography mortgage data (none exists in the export).
- Any broker data (none exists in the export).
- Terms-of-use review of the export — the site's own disclaimer already covers accuracy/liability for this kind of derived-data use; not re-litigated here.
