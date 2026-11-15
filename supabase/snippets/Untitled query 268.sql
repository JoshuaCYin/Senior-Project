select
    count(*) as total_tag_uses,
    count(*) filter (where tg.id is null) as not_in_lookup,
    round(100.0 * count(*) filter (where tg.id is null) / count(*), 2) as percent_missing
from product p
cross join lateral unnest(
    coalesce(p.ingredient_tags, '{}') ||
    coalesce(p.allergen_tags, '{}') ||
    coalesce(p.trace_tags, '{}')
) as t(tag)
left join tag tg
    on tg.data_source = p.data_source
   and tg.tag_name = lower(t.tag);
