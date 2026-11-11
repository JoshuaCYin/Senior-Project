-- How many products, and how big is the database now?
select count(*) from product;
select pg_size_pretty(pg_database_size('postgres'));

-- Try it out: 10 products with no peanut in their ingredients
select name, ingredient_tags
from product
where not (ingredient_tags && array['en:peanut'])   -- && means "share any item"
limit 10;