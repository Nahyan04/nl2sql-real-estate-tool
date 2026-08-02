-- Reference/dimension data: geography, property taxonomy, developers.
-- Fact tables (transactions, mortgages, rental_contracts, price_indices, projects, brokers)
-- are populated by scripts/generate_dataset.py, not here.

INSERT INTO municipalities (name_en, name_ar) VALUES
  ('Abu Dhabi City', 'مدينة أبوظبي'),
  ('Al Ain City', 'مدينة العين'),
  ('Al Dhafra Region', 'منطقة الظفرة');

INSERT INTO districts (municipality_id, name_en, name_ar) VALUES
  ((SELECT id FROM municipalities WHERE name_en = 'Abu Dhabi City'), 'New Abu Dhabi Islands', 'الجزر الجديدة'),
  ((SELECT id FROM municipalities WHERE name_en = 'Abu Dhabi City'), 'Abu Dhabi Downtown', 'وسط أبوظبي'),
  ((SELECT id FROM municipalities WHERE name_en = 'Abu Dhabi City'), 'Khalifa City & Al Raha', 'مدينة خليفة والراحة'),
  ((SELECT id FROM municipalities WHERE name_en = 'Abu Dhabi City'), 'Masdar & Zayed City', 'مصدر ومدينة زايد'),
  ((SELECT id FROM municipalities WHERE name_en = 'Abu Dhabi City'), 'Mainland Suburbs', 'الضواحي'),
  ((SELECT id FROM municipalities WHERE name_en = 'Abu Dhabi City'), 'Al Mushrif & Al Karama', 'المشرف والكرامة'),
  ((SELECT id FROM municipalities WHERE name_en = 'Al Ain City'), 'Al Ain City Center', 'وسط مدينة العين'),
  ((SELECT id FROM municipalities WHERE name_en = 'Al Ain City'), 'Al Ain Outskirts', 'ضواحي العين'),
  ((SELECT id FROM municipalities WHERE name_en = 'Al Dhafra Region'), 'Al Dhafra Coastal', 'الظفرة الساحلية'),
  ((SELECT id FROM municipalities WHERE name_en = 'Al Dhafra Region'), 'Al Dhafra Interior', 'الظفرة الداخلية');

INSERT INTO communities (district_id, name_en, name_ar) VALUES
  ((SELECT id FROM districts WHERE name_en = 'New Abu Dhabi Islands'), 'Yas Island', 'جزيرة ياس'),
  ((SELECT id FROM districts WHERE name_en = 'New Abu Dhabi Islands'), 'Saadiyat Island', 'جزيرة السعديات'),
  ((SELECT id FROM districts WHERE name_en = 'New Abu Dhabi Islands'), 'Al Reem Island', 'جزيرة الريم'),
  ((SELECT id FROM districts WHERE name_en = 'New Abu Dhabi Islands'), 'Al Maryah Island', 'جزيرة الماريه'),
  ((SELECT id FROM districts WHERE name_en = 'Abu Dhabi Downtown'), 'Corniche Road', 'شارع الكورنيش'),
  ((SELECT id FROM districts WHERE name_en = 'Abu Dhabi Downtown'), 'Al Khalidiyah', 'الخالدية'),
  ((SELECT id FROM districts WHERE name_en = 'Abu Dhabi Downtown'), 'Al Bateen', 'البطين'),
  ((SELECT id FROM districts WHERE name_en = 'Abu Dhabi Downtown'), 'Al Zahiyah', 'الزاهية'),
  ((SELECT id FROM districts WHERE name_en = 'Khalifa City & Al Raha'), 'Khalifa City', 'مدينة خليفة'),
  ((SELECT id FROM districts WHERE name_en = 'Khalifa City & Al Raha'), 'Al Raha Beach', 'شاطئ الراحة'),
  ((SELECT id FROM districts WHERE name_en = 'Masdar & Zayed City'), 'Masdar City', 'مدينة مصدر'),
  ((SELECT id FROM districts WHERE name_en = 'Masdar & Zayed City'), 'Zayed City', 'مدينة زايد (إم بي زد)'),
  ((SELECT id FROM districts WHERE name_en = 'Mainland Suburbs'), 'Al Shamkha', 'الشامخة'),
  ((SELECT id FROM districts WHERE name_en = 'Mainland Suburbs'), 'Al Bahia', 'البهية'),
  ((SELECT id FROM districts WHERE name_en = 'Mainland Suburbs'), 'Baniyas', 'بني ياس'),
  ((SELECT id FROM districts WHERE name_en = 'Al Mushrif & Al Karama'), 'Al Mushrif', 'المشرف'),
  ((SELECT id FROM districts WHERE name_en = 'Al Mushrif & Al Karama'), 'Al Nahyan', 'النهيان'),
  ((SELECT id FROM districts WHERE name_en = 'Al Ain City Center'), 'Al Jimi', 'الجيمي'),
  ((SELECT id FROM districts WHERE name_en = 'Al Ain City Center'), 'Al Muwaiji', 'المويجعي'),
  ((SELECT id FROM districts WHERE name_en = 'Al Ain City Center'), 'Al Towayya', 'الطويه'),
  ((SELECT id FROM districts WHERE name_en = 'Al Ain Outskirts'), 'Al Yahar', 'اليحر'),
  ((SELECT id FROM districts WHERE name_en = 'Al Dhafra Coastal'), 'Madinat Zayed', 'مدينة زايد (الظفرة)'),
  ((SELECT id FROM districts WHERE name_en = 'Al Dhafra Coastal'), 'Ruwais', 'الرويس'),
  ((SELECT id FROM districts WHERE name_en = 'Al Dhafra Interior'), 'Liwa', 'ليوا');

INSERT INTO property_types (name) VALUES
  ('Apartment'), ('Villa'), ('Townhouse / Attached Villa'), ('Plot for Villa'),
  ('Residential Complex'), ('Duplex'), ('Office'), ('Plot for Residential Complex'),
  ('Retail'), ('Plot for Townhouse / Attached Villa'), ('Mall / Market / Retail Center'),
  ('Plot for Mall / Market / Retail Center'), ('Penthouse'), ('Office Complex'), ('Other');

INSERT INTO layouts (name, bedrooms) VALUES
  ('Studio', 0),
  ('1 Bedroom', 1),
  ('2 Bedroom', 2),
  ('3 Bedroom', 3),
  ('4 Bedroom', 4),
  ('5 Bedroom', 5),
  ('6+ Bedroom', 6),
  ('Penthouse', NULL);

INSERT INTO developers (name, license_no) VALUES
  ('Zayline Developments', 'DEV-2015-001'),
  ('Falcon Crest Properties', 'DEV-2016-014'),
  ('Marina Horizon Real Estate', 'DEV-2012-007'),
  ('Desert Pearl Developers', 'DEV-2018-022'),
  ('Corniche Star Properties', 'DEV-2011-003'),
  ('Al Noor Skyline Developers', 'DEV-2017-019'),
  ('Palm Bay Developments', 'DEV-2014-011'),
  ('Silver Dune Properties', 'DEV-2019-028'),
  ('Emerald Coast Developers', 'DEV-2013-009'),
  ('Oryx Valley Real Estate', 'DEV-2020-033'),
  ('Bright Horizon Developers', 'DEV-2016-017'),
  ('Crescent Gate Properties', 'DEV-2010-002');
