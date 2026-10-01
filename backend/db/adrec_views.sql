-- Staging-only typed views. Every query must select exactly one snapshot.
CREATE OR REPLACE VIEW adrec_intake.transactions AS
SELECT snapshot_id, source_file, source_row,
 (dimensions->>'Sale Application Date')::date AS transaction_date,
 dimensions->>'Asset Class' AS asset_class,
 dimensions->>'Property Type' AS property_type,
 dimensions->>'Property Layout' AS layout,
 NULL::text AS municipality,
 dimensions->>'District' AS district,
 dimensions->>'Community' AS community,
 dimensions->>'Project Name' AS project_name,
 dimensions->>'Sale Application Type' AS sale_type,
 dimensions->>'Sale Sequence' AS market_type,
 (metrics->>'Property Sale Price (AED)')::numeric AS price_aed,
 (metrics->>'Property Sold Share')::numeric AS sold_share,
 (metrics->>'Property Sold Area (SQM)')::numeric AS sold_area_sqm,
 (metrics->>'Land Plot Ground Area (SQM)')::numeric AS plot_area_sqm,
 (metrics->>'Rate (AED per SQM)')::numeric AS source_rate_aed_sqm,
 CASE WHEN (metrics->>'Property Sold Area (SQM)')::numeric > 1
 THEN (metrics->>'Property Sale Price (AED)')::numeric / (metrics->>'Property Sold Area (SQM)')::numeric END AS calculated_rate_aed_sqm,
 quality_flags
FROM adrec_intake.observations
WHERE source_file = 'Transactions/recent_sales_2019-2026.csv';

CREATE OR REPLACE VIEW adrec_intake.price_indices AS
SELECT snapshot_id, source_file, source_row,
 (dimensions->>'Date')::date AS period_end,
 dimensions->>'Municipality' AS municipality,
 COALESCE(dimensions->>'Zone', dimensions->>'District') AS source_area_group,
 dimensions->>'Property Type' AS property_group,
 dimensions->>'App Type' AS application_type,
 CASE WHEN source_file = 'Price Indices/sale_price_index.xlsx' THEN 'sale' ELSE 'rent' END AS index_type,
 COALESCE(metrics->>'Average of sale_index_value',metrics->>'Sale Index Value')::numeric AS index_value,
 NULL::text AS base_methodology
FROM adrec_intake.observations
WHERE source_file IN ('Price Indices/sale_price_index.xlsx','Price Indices/rent_price_index.xlsx',
 'Price Indices/office_price_index.xlsx','Price Indices/retail_price_index.xlsx','Price Indices/industrial_price_index.xlsx');

CREATE OR REPLACE VIEW adrec_intake.rental_observations AS
SELECT snapshot_id, source_file, source_row,
 (dimensions->>'Date')::date AS period_end,
 dimensions->>'Period' AS period_label,
 dimensions->>'Municipality' AS municipality,
 dimensions->>'District' AS district,
 dimensions->>'Community' AS community,
 dimensions->>'Project Name' AS project_name,
 dimensions->>'Property Type' AS property_type,
 dimensions->>'Property Layout' AS layout,
 (metrics->>'Leased Units')::numeric AS source_leased_units,
 (metrics->>'Sum of active_value_aed')::numeric AS active_value_aed,
 (metrics->>'Average of rolling_average')::numeric AS source_rolling_average_aed,
 (metrics->>'Average of average_sale_price_aed')::numeric AS source_average_sale_price_aed,
 (metrics->>'Annual Rent')::numeric AS source_annual_rent
FROM adrec_intake.observations
WHERE source_file LIKE 'Residential Leases/%'
 OR source_file = 'Price Indices/average_sale_rent_prices_by_product_area.xlsx';

CREATE OR REPLACE VIEW adrec_intake.market_aggregates AS
SELECT o.snapshot_id, o.source_file, o.source_row, s.grain, s.measure,
 (dimensions->>'End of Period')::date AS period_end,
 dimensions, metrics
FROM adrec_intake.observations o
JOIN adrec_intake.sources s USING (snapshot_id, source_file)
WHERE o.source_file LIKE 'Transactions/%' AND o.source_file <> 'Transactions/recent_sales_2019-2026.csv';
