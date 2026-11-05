-- Which recipes are safe for someone allergic to tree nuts?
select r.title
from recipe r
where not exists (
  select 1
  from recipe_ingredient ri
  join ingredient_allergen ia on ia.ingredient_id = ri.ingredient_id
  join allergen a on a.id = ia.allergen_id
  where ri.recipe_id = r.id and a.name = 'tree nuts'
);