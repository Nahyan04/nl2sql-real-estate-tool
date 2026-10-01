from sqlalchemy import create_engine, text

from app.services.sql_validator import validate_product_query


def test_quarterly_rent_and_gross_yield_use_matching_unit_weights():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('''CREATE TABLE rental_observations (
            source_file text, period_end date, municipality text, district text,
            property_type text, layout text, source_leased_units numeric,
            source_annual_rent numeric, source_average_sale_price_aed numeric
        )'''))
        connection.execute(text('''INSERT INTO rental_observations VALUES
            ('Residential Leases/lease_residential.xlsx','2026-06-30','Abu Dhabi City','A','apartment','1 bed',4,NULL,NULL),
            ('Residential Leases/lease_residential.xlsx','2026-06-30','Abu Dhabi City','A','apartment','1 bed',6,NULL,NULL),
            ('Residential Leases/lease_residential.xlsx','2026-06-30','Abu Dhabi City','B','apartment','1 bed',30,NULL,NULL),
            ('Residential Leases/lease_residential.xlsx','2026-06-30','Abu Dhabi City','C','apartment','1 bed',5,NULL,NULL),
            ('Residential Leases/lease_residential.xlsx','2026-03-31','Abu Dhabi City','A','apartment','1 bed',1000,NULL,NULL),
            ('Price Indices/average_sale_rent_prices_by_product_area.xlsx','2026-06-30','Abu Dhabi City','A','apartment','1 bed',NULL,100,2000),
            ('Price Indices/average_sale_rent_prices_by_product_area.xlsx','2026-06-30','Abu Dhabi City','B','apartment','1 bed',NULL,300,3000),
            ('Price Indices/average_sale_rent_prices_by_product_area.xlsx','2026-06-30','Abu Dhabi City','C','apartment','1 bed',NULL,500,0),
            ('Price Indices/average_sale_rent_prices_by_product_area.xlsx','2026-06-30','Abu Dhabi City','D','apartment','1 bed',NULL,900,900)
        '''))
        query = '''WITH units AS (
            SELECT period_end, municipality, district, property_type, layout,
                   SUM(source_leased_units) AS leased_units
            FROM rental_observations
            WHERE source_file = 'Residential Leases/lease_residential.xlsx'
              AND period_end = '2026-06-30'
            GROUP BY period_end, municipality, district, property_type, layout
        ), matched AS (
            SELECT c.source_annual_rent, c.source_average_sale_price_aed, u.leased_units
            FROM rental_observations c
            JOIN units u ON c.period_end = u.period_end
                AND c.municipality = u.municipality AND c.district = u.district
                AND c.property_type = u.property_type AND c.layout = u.layout
            WHERE c.source_file = 'Price Indices/average_sale_rent_prices_by_product_area.xlsx'
              AND c.period_end = '2026-06-30'
              AND c.source_annual_rent > 0 AND u.leased_units > 0
        )
        SELECT SUM(leased_units) AS rent_units,
               1.0 * SUM(source_annual_rent * leased_units) / NULLIF(SUM(leased_units), 0) AS weighted_annual_rent_aed,
               SUM(CASE WHEN source_average_sale_price_aed > 0 THEN leased_units ELSE 0 END) AS yield_units,
               100.0 * SUM(CASE WHEN source_average_sale_price_aed > 0
                   THEN 1.0 * source_annual_rent / source_average_sale_price_aed * leased_units ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN source_average_sale_price_aed > 0 THEN leased_units ELSE 0 END), 0)
                   AS indicative_gross_yield_pct
        FROM matched'''
        assert validate_product_query(query).is_safe
        result = connection.execute(text(query)).one()

    assert result.rent_units == 45
    assert abs(result.weighted_annual_rent_aed - (12500 / 45)) < 1e-8
    assert result.yield_units == 40
    assert abs(result.indicative_gross_yield_pct - 8.75) < 1e-8
    engine.dispose()
