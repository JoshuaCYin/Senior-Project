select tag, count(*)
from product, unnest(ingredient_tags) as tag
where tag like '%milk%' or tag like '%whey%'   -- change these words for each allergen
group by tag order by count(*) desc limit 50;