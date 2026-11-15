
insert into restaurant (name) values ('Outback');

insert into menu_item (restaurant_id, name, data_source, last_checked)
select r.id, x.item, x.url, date '2026-11-15'
from (values
  ('Outback', 'Bloomin'' Onion', 'https://www.outback.com/allergens'),
  ('Outback', 'Aussie Cheese Fries', 'https://www.outback.com/allergens'),
  ('Outback', 'Ribeye 13oz', 'https://www.outback.com/allergens'),
  ('Outback', 'Outback Center-Cut Sirloin 5oz', 'https://www.outback.com/allergens'),
  ('Outback', 'Outback Center-Cut Sirloin 9oz', 'https://www.outback.com/allergens'),
  ('Outback', '6 oz Sirloin & 5 oz Alice Springs Chicken', 'https://www.outback.com/allergens'),
  ('Outback', 'Outback Ribs Half Rack', 'https://www.outback.com/allergens'),
  ('Outback', '6 oz Sirloin & Coconut Shrimp', 'https://www.outback.com/allergens'),
  ('Outback', 'Fresh Sydney Salad', 'https://www.outback.com/allergens'),
  ('Outback', 'Aussie Fries', 'https://www.outback.com/allergens')
) as x(restaurant, item, url)
join restaurant r on r.name = x.restaurant;

insert into menu_item_allergen (menu_item_id, allergen_id, level)
select m.id, a.id, 'contains'
from (values
  ('Bloomin'' Onion',                                   array['egg', 'milk', 'wheat', 'gluten']),
  ('Aussie Cheese Fries',                               array['egg', 'milk']),
  ('Ribeye 13oz',                                       array['milk', 'soy']),
  ('Outback Center-Cut Sirloin 5oz',                    array['milk', 'soy']),
  ('Outback Center-Cut Sirloin 9oz',                    array['milk', 'soy']),
  ('6 oz Sirloin & 5 oz Alice Springs Chicken',         array['egg', 'milk', 'soy']),
  ('6 oz Sirloin & Coconut Shrimp',                     array['milk', 'shellfish', 'soy', 'wheat', 'gluten']),
  ('Fresh Sydney Salad',                                array['milk'])
) as x(item, allergens)
cross join lateral unnest(x.allergens) as t(allergen)
join menu_item m on m.name = x.item
join allergen a  on a.name = t.allergen;
