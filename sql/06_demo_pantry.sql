-- =============================================================================
-- 6. (Optional) Demo pantry: an Indian kitchen with a spice rack, millets, dry fruits and seeds
-- Expiry dates are relative to today. Every demo row is marked source = 'demo'.
-- The app shows a "Demo pantry" badge and removes them with one click (or run
-- 06b_clear_demo.sql). Names mix English and Hindi, like a real kitchen:
-- "Haldi" matches "turmeric" in recipes, "Curd" matches "yogurt".
-- No brand names are used, so recall checks only show "check the brand" matches.
-- =============================================================================
INSERT INTO pantry_items (name, category, quantity, unit, expires_on, source) VALUES
  -- produce
  ('Spinach (palak)',   'Produce',          1,   'bunch',  current_date + 2,   'demo'),
  ('Cilantro',          'Produce',          1,   'bunch',  current_date + 1,   'demo'),
  ('Tomatoes',          'Produce',          6,   NULL,     current_date + 4,   'demo'),
  ('Onions',            'Produce',          1,   'kg',     current_date + 30,  'demo'),
  ('Potatoes',          'Produce',          1,   'kg',     current_date + 25,  'demo'),
  ('Garlic',            'Produce',          1,   'head',   current_date + 40,  'demo'),
  ('Ginger',            'Produce',          1,   'piece',  current_date + 14,  'demo'),
  ('Green chilies',     'Produce',          10,  NULL,     current_date + 6,   'demo'),
  ('Curry leaves',      'Produce',          1,   'bunch',  current_date + 5,   'demo'),
  ('Okra (bhindi)',     'Produce',          250, 'g',      current_date + 2,   'demo'),
  ('Lemons',            'Produce',          3,   NULL,     current_date + 10,  'demo'),
  ('Mushrooms',         'Produce',          200, 'g',      current_date + 2,   'demo'),
  ('Broccoli',          'Produce',          1,   'head',   current_date + 4,   'demo'),
  ('Asparagus',         'Produce',          1,   'bunch',  current_date + 3,   'demo'),
  ('Carrots',           'Produce',          500, 'g',      current_date + 14,  'demo'),
  ('Cucumber',          'Produce',          2,   NULL,     current_date + 5,   'demo'),
  ('Pudina',            'Produce',          1,   'bunch',  current_date + 3,   'demo'),
  ('Drumsticks',        'Produce',          4,   NULL,     current_date + 5,   'demo'),
  ('Kiwis',             'Produce',          4,   NULL,     current_date + 6,   'demo'),
  ('Pomegranate',       'Produce',          1,   NULL,     current_date + 10,  'demo'),
  ('Blueberries',       'Produce',          125, 'g',      current_date + 3,   'demo'),
  -- dairy & eggs
  ('Paneer',            'Dairy & eggs',     200, 'g',      current_date + 3,   'demo'),
  ('Curd (dahi)',       'Dairy & eggs',     1,   'tub',    current_date + 4,   'demo'),
  ('Milk',              'Dairy & eggs',     1,   'litre',  current_date + 3,   'demo'),
  ('Fresh cream',       'Dairy & eggs',     1,   'pack',   current_date - 1,   'demo'),
  ('Eggs',              'Dairy & eggs',     12,  NULL,     current_date + 12,  'demo'),
  ('Ghee',              'Dairy & eggs',     1,   'jar',    current_date + 180, 'demo'),
  -- meat
  ('Chicken thighs',    'Meat & fish',      500, 'g',      current_date + 1,   'demo'),
  -- grains, dals
  ('Basmati rice',      'Grains & bread',   5,   'kg',     current_date + 300, 'demo'),
  ('Atta',              'Grains & bread',   5,   'kg',     current_date + 90,  'demo'),
  ('Poha',              'Grains & bread',   500, 'g',      current_date + 120, 'demo'),
  ('Brown rice',        'Grains & bread',   1,   'kg',     current_date + 200, 'demo'),
  ('Quinoa',            'Grains & bread',   500, 'g',      current_date + 300, 'demo'),
  ('Ragi flour',        'Grains & bread',   1,   'kg',     current_date + 90,  'demo'),
  ('Jowar atta',        'Grains & bread',   1,   'kg',     current_date + 90,  'demo'),
  ('Rolled oats',       'Grains & bread',   500, 'g',      current_date + 180, 'demo'),
  ('Sourdough bread',   'Grains & bread',   1,   'loaf',   current_date + 3,   'demo'),
  ('Toor dal',          'Dals & lentils',   1,   'kg',     current_date + 300, 'demo'),
  ('Moong dal',         'Dals & lentils',   500, 'g',      current_date + 300, 'demo'),
  ('Besan',             'Dals & lentils',   500, 'g',      current_date + 120, 'demo'),
  ('Green moong',       'Dals & lentils',   500, 'g',      current_date + 300, 'demo'),
  ('Soya chunks',       'Dals & lentils',   200, 'g',      current_date + 240, 'demo'),
  -- spice rack (Hindi and English names both work)
  ('Haldi',             'Spices & masalas', 1,   'box',    current_date + 200, 'demo'),
  ('Jeera',             'Spices & masalas', 1,   'box',    current_date + 240, 'demo'),
  ('Red chilli powder', 'Spices & masalas', 1,   'box',    current_date + 150, 'demo'),
  ('Dhania powder',     'Spices & masalas', 1,   'box',    current_date + 20,  'demo'),
  ('Garam masala',      'Spices & masalas', 1,   'box',    current_date + 160, 'demo'),
  ('Rai',               'Spices & masalas', 1,   'box',    current_date + 300, 'demo'),
  ('Hing',              'Spices & masalas', 1,   'box',    current_date + 365, 'demo'),
  ('Elaichi',           'Spices & masalas', 1,   'box',    current_date + 300, 'demo'),
  ('Black pepper',      'Spices & masalas', 1,   'jar',    current_date + 400, 'demo'),
  ('Saunf',             'Spices & masalas', 1,   'box',    current_date + 300, 'demo'),
  ('Ajwain',            'Spices & masalas', 1,   'box',    current_date + 300, 'demo'),
  ('Dhania seeds',      'Spices & masalas', 1,   'box',    current_date + 300, 'demo'),
  -- dry fruits & seeds (from the daily meal plan: soaked nuts, flaxseed, chia)
  ('Walnuts',           'Dry fruits & seeds', 250, 'g',    current_date + 150, 'demo'),
  ('Almonds',           'Dry fruits & seeds', 250, 'g',    current_date + 200, 'demo'),
  ('Black raisins',     'Dry fruits & seeds', 200, 'g',    current_date + 180, 'demo'),
  ('Brazil nuts',       'Dry fruits & seeds', 100, 'g',    current_date + 150, 'demo'),
  ('Flaxseed powder',   'Dry fruits & seeds', 200, 'g',    current_date + 60,  'demo'),
  ('Chia seeds',        'Dry fruits & seeds', 200, 'g',    current_date + 300, 'demo'),
  ('Pumpkin seeds',     'Dry fruits & seeds', 100, 'g',    current_date + 120, 'demo'),
  ('Makhana',           'Dry fruits & seeds', 100, 'g',    current_date + 150, 'demo'),
  ('Roasted chana',     'Dry fruits & seeds', 250, 'g',    current_date + 90,  'demo'),
  -- the rest
  ('Tofu',              'Other',            200, 'g',      current_date + 5,   'demo'),
  ('Hummus',            'Condiments',       1,   'tub',    current_date + 6,   'demo'),
  ('Canned chickpeas',  'Canned & jarred',  2,   'cans',   current_date + 600, 'demo'),
  ('Frozen peas',       'Frozen',           1,   'bag',    current_date + 120, 'demo'),
  ('Peanuts',           'Snacks',           200, 'g',      current_date + 90,  'demo');
