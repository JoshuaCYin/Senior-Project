select barcode, name, data_completeness, category_tags
from product
where category_tags && array['en:meals', 'en:sandwiches', 'en:salads']
  and data_completeness > 0.7
  and cardinality(ingredient_tags) > 0
order by data_completeness desc
limit 1000;
