select lower(t.tag) as tag, count(*) as products
from product p
cross join lateral unnest(
    coalesce(p.ingredient_tags, '{}') ||
    coalesce(p.allergen_tags, '{}') ||
    coalesce(p.trace_tags, '{}')
) as t(tag)
left join tag tg
    on tg.data_source = p.data_source
   and tg.tag_name = lower(t.tag)
where tg.id is null
group by 1
order by 2 desc
limit 50;
