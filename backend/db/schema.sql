CREATE TABLE municipalities (id serial PRIMARY KEY, name_en text NOT NULL, name_ar text NOT NULL);
CREATE TABLE districts      (id serial PRIMARY KEY, municipality_id int REFERENCES municipalities(id), name_en text NOT NULL, name_ar text NOT NULL);
CREATE TABLE communities    (id serial PRIMARY KEY, district_id int REFERENCES districts(id), name_en text NOT NULL, name_ar text NOT NULL);
CREATE TABLE developers     (id serial PRIMARY KEY, name text NOT NULL, license_no text NOT NULL);
CREATE TABLE projects       (id serial PRIMARY KEY, community_id int REFERENCES communities(id), developer_id int REFERENCES developers(id), name text NOT NULL);
CREATE TABLE property_types (id serial PRIMARY KEY, name text NOT NULL);                      -- Apartment, Villa, Land, Building, Commercial Unit
CREATE TABLE layouts        (id serial PRIMARY KEY, name text NOT NULL, bedrooms int);        -- Studio..5BR+

CREATE TABLE transactions (
  id bigserial PRIMARY KEY,
  transaction_date date NOT NULL,
  community_id int NOT NULL REFERENCES communities(id),
  project_id int REFERENCES projects(id),
  property_type_id int NOT NULL REFERENCES property_types(id),
  layout_id int REFERENCES layouts(id),
  sale_type text NOT NULL CHECK (sale_type IN ('sale','resale')),
  is_offplan boolean NOT NULL DEFAULT false,
  sold_area_sqm numeric(10,2),
  plot_area_sqm numeric(10,2),
  price_aed numeric(14,2) NOT NULL,
  rate_aed_sqm numeric(10,2),
  buyer_origin text NOT NULL CHECK (buyer_origin IN ('UAE','GCC','Foreign'))
);

CREATE TABLE mortgages (
  id bigserial PRIMARY KEY,
  mortgage_date date NOT NULL,
  community_id int NOT NULL REFERENCES communities(id),
  property_type_id int NOT NULL REFERENCES property_types(id),
  mortgage_value_aed numeric(14,2) NOT NULL,
  lender_type text NOT NULL CHECK (lender_type IN ('local_bank','international_bank','finance_company'))
);

CREATE TABLE rental_contracts (
  id bigserial PRIMARY KEY,
  contract_date date NOT NULL,
  community_id int NOT NULL REFERENCES communities(id),
  property_type_id int NOT NULL REFERENCES property_types(id),
  layout_id int REFERENCES layouts(id),
  annual_rent_aed numeric(12,2) NOT NULL,
  contract_type text NOT NULL CHECK (contract_type IN ('new','renewal'))
);

CREATE TABLE price_indices (
  id serial PRIMARY KEY,
  month date NOT NULL,
  index_type text NOT NULL CHECK (index_type IN ('sale','rent')),
  property_type_id int NOT NULL REFERENCES property_types(id),
  index_value numeric(8,2) NOT NULL              -- base 2019 = 100
);

CREATE TABLE brokers (
  id serial PRIMARY KEY,
  name text NOT NULL,                             -- generated fake names only
  kind text NOT NULL CHECK (kind IN ('individual','company')),
  license_type text NOT NULL,
  community_focus_id int REFERENCES communities(id)
);
