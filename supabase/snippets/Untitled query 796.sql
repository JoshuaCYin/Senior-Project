select r.title, string_agg(distinct a.name, ', ') as allergens
from recipe r
join recipe_ingredient ri on ri.recipe_id = r.id
left join ingredient_allergen ia on ia.ingredient_id = ri.ingredient_id
left join allergen a on a.id = ia.allergen_id
group by r.title;
