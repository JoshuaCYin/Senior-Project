alter table product --"off" stands for Open Food Facts
    add column  ingredient_tags text[],
    add column  off_allergen_tags text[],
    add column  off_trace_tags text[], --for "may contain"
    add column  completeness real, --Open Food Facts' own score, 0-1
    add column  off_last_modified timestamptz; --when the product was last edited
    
--index to help reduce the time taken whenever checking if the ingredient list includes something
create index product_ingredient_tags_idx on product using gin (ingredient_tags);