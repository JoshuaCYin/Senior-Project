insert into allergen (name) values ('milk'), ('egg'), ('wheat'), ('tree nuts'), ('peanut'), ('sesame');

insert into ingredient (name) values ('walnut'), ('flour'), ('egg'), ('banana'), ('rice');

--link ingredients to allergens (by name, so no need to guess IDs)
insert into ingredient_allergen (ingredient_id, allergen_id)
select i.id, a.id
from ingredient i, allergen a
where (i.name, a.name) in (('walnut', 'tree nuts'), ('flour', 'wheat'), ('egg', 'egg'));

insert into recipe (title) values ('Banana bread'), ('Plain rice');

insert into recipe_ingredient (recipe_id, ingredient_id, amount)
select r.id, i.id, x.amount
from (values
  ('Banana bread', 'flour',  '2 cups'),
  ('Banana bread', 'egg',    '2'),
  ('Banana bread', 'walnut', '1/2 cup'),
  ('Banana bread', 'banana', '3'),
  ('Plain rice',   'rice',   '1 cup')
) as x(recipe, ingredient, amount)
join recipe r   on r.title = x.recipe
join ingredient i on i.name = x.ingredient;
