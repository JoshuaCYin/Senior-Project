# Tutorial: switching allergens to a lookup table

This walks you through replacing the allergen match patterns with a lookup table. Each step says what you're doing and why, then lets you try it. If you get stuck, open the hint. The answer is there too, but try first.

You'll need the classified tag file from the classifying session (backend/lookup/tag_allergen.csv) before step 4. Steps 0 to 3 can be done before it exists.

## The big idea

Right now the import asks, for every tag on every product, "does this tag match any of 328 patterns?" That's slow, and patterns are easy to get wrong (remember "oat milk" matching "goat milk").

A lookup table flips it around. Every common tag is checked once, ahead of time, and the answer is saved:

    en:whey          -> milk, contains
    en:cocoa-butter  -> (nothing)
    en:peanut-oil    -> peanut, contains
    en:may-contain-peanuts -> peanut, may contain

Then the import just looks each tag up. Looking something up in a table is one of the things databases are fastest at.

## Step 0: get the database back to a known state

Your migrations only live on your laptop (there's no linked online Supabase project), so the migration files are the source of truth. The database is just something built from them. If you're ever unsure what state it's in, rebuild it.

1. Start Docker, then run `npx supabase start` from the project folder.
2. Run `npx supabase migration list --local`. It shows each migration file and whether it's been applied.
3. To rebuild from scratch, run `npx supabase db reset`. This wipes the local database, runs every migration in order, then runs seed.sql. Your products will be gone, but the import puts them back in about 30 seconds.

A good habit for later: once a migration has been applied somewhere other people use, don't edit it. Make a new migration that changes things instead. For now, since it's only local, a reset is always safe.

## Step 1: add gluten as an allergen

You decided wheat should count as gluten, but gluten should be its own thing (barley, rye and regular oats count too). That means the allergen table needs a "gluten" row.

Try it: the allergen names come from seed.sql. Add gluten there.

<details><summary>Hint</summary>

Look at the first line of supabase/seed.sql. It's a list of values you can add one more to. Seed only runs on `db reset`, so reset after changing it.

</details>

<details><summary>Answer</summary>

    insert into allergen (name) values ('milk'), ('egg'), ('wheat'), ('gluten'), ('tree nuts'), ('peanut'), ('sesame');

</details>

## Step 2: make the lookup tables

You already know this shape. Look at ingredient and ingredient_allergen in your first migration: one table lists things, and a "join table" says which allergens each thing has. The lookup works the same way:

- tag: every tag that's been checked, even ones with no allergen. This is how you'll know "checked, nothing found" apart from "never checked".
- tag_allergen: which allergens a tag means, and at what level.

What each needs:

- tag: an id, the source (like 'Open Food Facts', since other data sources might use different tags), and the tag name. The same tag name shouldn't appear twice for the same source.
- tag_allergen: the tag's id, the allergen's id, and the level ('contains' or 'may contain'). A tag can have more than one allergen (en:milk-chocolate-peanuts is milk and peanut), but the same tag and allergen pair shouldn't appear twice.

Try it: make a new migration with `npx supabase migration new allergen_lookup`, then write both create table statements in the file it makes. Copy the style of your existing tables.

<details><summary>Hint</summary>

- "Shouldn't appear twice" means a unique constraint. For two columns together it's `unique (source, name)`.
- For tag_allergen, the pair of ids can be the primary key, like in ingredient_allergen.
- Use `on delete cascade` on the tag id, so deleting a tag also deletes its allergen rows.
- Copy the level check from product_allergen.

</details>

<details><summary>Answer</summary>

    create table tag (
        id      bigint generated always as identity primary key,
        source  text not null,                  -- 'Open Food Facts'
        name    text not null,                  -- lowercase, like 'en:whey'
        unique (source, name)
    );

    create table tag_allergen (
        tag_id      bigint not null references tag(id) on delete cascade,
        allergen_id bigint not null references allergen(id) on delete cascade,
        level       text not null check (level in ('contains', 'may contain')),
        primary key (tag_id, allergen_id)
    );

</details>

Run `npx supabase db reset` to apply it. Then check that both tables exist in Supabase Studio (http://localhost:54323).

## Step 3: get rid of allergen_rule

allergen_rule is replaced by the lookup, so it can go. Don't edit the old migration that made it. Make a new one.

Try it: make another migration that removes the table.

<details><summary>Hint</summary>

The SQL for removing a table is `drop table`. Wait until step 6 if you want to compare old and new results first.

</details>

<details><summary>Answer</summary>

    drop table allergen_rule;

</details>

## Step 4: load the lookup file in the import script

The classifying session makes backend/lookup/tag_allergen.csv. It has one row per tag and allergen pair:

    tag,allergen,level,note
    en:whey,milk,contains,
    en:cocoa-butter,none,,
    en:milk-chocolate-peanuts,milk,contains,
    en:milk-chocolate-peanuts,peanut,contains,

The import needs to put that into the tag and tag_allergen tables each time it runs, before it builds product_allergen.

Good news: you already solved the hard part. Products are loaded with a staging table (DuckDB copies the file into a plain table, then Postgres moves the rows into the real one). Do the same thing here.

Try it, in this order, inside the same transaction as the product swap:

1. Make a staging table from the CSV (DuckDB can read a CSV like `FROM 'lookup/tag_allergen.csv'`, just like it reads the parquet file).
2. Delete the old Open Food Facts rows from tag. Because of the cascade, their tag_allergen rows go too.
3. Insert each distinct tag name into tag.
4. Insert into tag_allergen by joining the staging rows to tag (to get tag ids) and to allergen (to turn the name "milk" into its id). Skip rows where allergen is 'none'.
5. Drop the staging table at the end, like the product one.

<details><summary>Hint</summary>

- Making the staging table works like the product one: `CREATE TABLE pg.public.tag_import_staging AS SELECT tag, allergen, level FROM 'lookup/tag_allergen.csv'`. The path depends on what folder you run from (another reason to fix that TODO).
- Step 3 needs `SELECT DISTINCT` because a tag with two allergens has two rows.
- Step 4 joins on two things: `t.name = s.tag AND t.source = 'Open Food Facts'`, and `a.name = s.allergen`. Joining to allergen by name drops 'none' rows on its own, since there's no allergen called 'none'.

</details>

<details><summary>Answer (the SQL for steps 2 to 4, each in its own postgres_execute call)</summary>

    DELETE FROM public.tag WHERE source = 'Open Food Facts'

    INSERT INTO public.tag (source, name)
    SELECT DISTINCT 'Open Food Facts', lower(tag) FROM public.tag_import_staging

    INSERT INTO public.tag_allergen (tag_id, allergen_id, level)
    SELECT t.id, a.id, s.level
    FROM public.tag_import_staging s
    JOIN public.tag t ON t.source = 'Open Food Facts' AND t.name = lower(s.tag)
    JOIN public.allergen a ON a.name = s.allergen

</details>

## Step 5: build product_allergen from the lookup

This replaces the two big pattern matching inserts. The idea is the same as before: split each product's tag list into one row per tag (that's what UNNEST does), then match each tag. The difference is that the match is now a plain "equals" join on the tag table, not a pattern search.

Two rules:

- If any tag says "contains", the product contains it.
- Otherwise, if any tag says "may contain", or the allergen shows up in the trace tags at all, the product may contain it.

So do it in two inserts, "contains" first, then "may contain" with `ON CONFLICT DO NOTHING` so it never overwrites a "contains". You already have that pattern in the current script.

Two things to watch:

- Tags in the lookup are lowercase, but some product tags have capitals. Compare with `lower(t.tag)`.
- Only match tags from the same source as the product: `tg.source = p.data_source`.

Try it: rewrite the two product_allergen inserts.

<details><summary>Hint</summary>

The shape of the first insert is:

    FROM public.product p
    CROSS JOIN LATERAL UNNEST(...the tag lists...) AS t(tag)
    JOIN public.tag tg ON ...
    JOIN public.tag_allergen ta ON ...
    WHERE ta.level = 'contains'

The second insert is two parts glued with UNION: ingredient and allergen tags where the level is 'may contain', plus trace tags with any level.

</details>

<details><summary>Answer</summary>

    -- contains
    INSERT INTO public.product_allergen (product_id, allergen_id, level)
    SELECT DISTINCT p.id, ta.allergen_id, 'contains'
    FROM public.product p
    CROSS JOIN LATERAL UNNEST(COALESCE(p.ingredient_tags, '{}') || COALESCE(p.allergen_tags, '{}')) AS t(tag)
    JOIN public.tag tg ON tg.source = p.data_source AND tg.name = lower(t.tag)
    JOIN public.tag_allergen ta ON ta.tag_id = tg.id
    WHERE ta.level = 'contains'

    -- may contain
    INSERT INTO public.product_allergen (product_id, allergen_id, level)
    SELECT DISTINCT p.id, ta.allergen_id, 'may contain'
    FROM public.product p
    CROSS JOIN LATERAL UNNEST(COALESCE(p.ingredient_tags, '{}') || COALESCE(p.allergen_tags, '{}')) AS t(tag)
    JOIN public.tag tg ON tg.source = p.data_source AND tg.name = lower(t.tag)
    JOIN public.tag_allergen ta ON ta.tag_id = tg.id
    WHERE ta.level = 'may contain'
    UNION
    SELECT DISTINCT p.id, ta.allergen_id, 'may contain'
    FROM public.product p
    CROSS JOIN LATERAL UNNEST(COALESCE(p.trace_tags, '{}')) AS t(tag)
    JOIN public.tag tg ON tg.source = p.data_source AND tg.name = lower(t.tag)
    JOIN public.tag_allergen ta ON ta.tag_id = tg.id
    ON CONFLICT (product_id, allergen_id) DO NOTHING

</details>

## Step 6: check your work

Run the import from the backend folder: `.venv/bin/python scripts/import_openff.py`. It should take well under a minute now, instead of about 4.

Then try these in Supabase Studio's SQL editor:

1. How many products have each allergen at each level? Group product_allergen by allergen name and level. Compare against the old numbers in the decision log (for example milk was about 137,700 contains).
2. A few spot checks. Pick products you know (a peanut butter, an almond milk, a cocoa butter chocolate bar) and see what they got.
3. How many tag uses aren't in the lookup yet? Unnest product tags, left join to tag, and count the ones with no match. It should be around 2 to 3% of all tag uses. If it ever gets bigger after a new data download, it's time to classify more tags.

<details><summary>Hint for check 3</summary>

A LEFT JOIN keeps every row from the left side even when there's no match, and fills the right side with nulls. So "not in the lookup" is `WHERE tg.id IS NULL`.

</details>

If the numbers look right, log what you did in docs/decision-log.md and cross it off docs/TODO.md.
