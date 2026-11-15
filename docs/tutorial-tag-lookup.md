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
- tag_allergen: the tag's id, the allergen's id, the level ('contains' or 'may contain'), and whether the label is unsure. A tag can have more than one allergen (en:milk-chocolate-peanuts is milk and peanut), but the same tag and allergen pair shouldn't appear twice.

About "unsure": some tags don't say what they're made of, like en:crust or en:flour. Those are flagged with the likely allergen, but marked unsure, so later the app can show a lower confidence instead of hiding the product completely. Most tags aren't unsure, so it should default to false.

Try it: make a new migration with `npx supabase migration new allergen_lookup`, then write both create table statements in the file it makes. Copy the style of your existing tables.

<details><summary>Hint</summary>

- "Shouldn't appear twice" means a unique constraint. For two columns together it's `unique (source, name)`.
- For tag_allergen, the pair of ids can be the primary key, like in ingredient_allergen.
- Use `on delete cascade` on the tag id, so deleting a tag also deletes its allergen rows.
- Copy the level check from product_allergen.
- A yes/no column is a `boolean`. `default false` fills it in when you don't give a value.

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
        unsure      boolean not null default false,
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

Before you start: steps 2 and 3 need to be applied. Run `npx supabase migration list --local` from the project folder and check that your allergen_lookup migration is there. In Supabase Studio, the tag and tag_allergen tables should exist (empty is fine).

### What this step is for

The classifying session made backend/lookup/tag_allergen.csv. It has one row per tag and allergen pair:

    tag,allergen,level,note
    en:whey,milk,contains,
    en:cocoa-butter,none,,
    en:milk-chocolate-peanuts,milk,contains,
    en:milk-chocolate-peanuts,peanut,contains,
    en:crust,wheat,contains,"unsure: crust type not named; usually wheat (pizza, pie)"

A row is unsure when its note is filled in. The note is for people to read, so the database only needs the yes/no.

Right now that's just a file. Step 5 builds product_allergen by joining products to the tag and tag_allergen tables, so those tables need to be filled from the file first. That's all this step does: copy the CSV into those two tables, every time the import runs.

### The trick you already know

You load products in two moves:

1. DuckDB copies the file into a plain staging table in Postgres (product_import_staging).
2. Postgres moves the rows from staging into the real table (product), inside the transaction.

The lookup works exactly the same way. The only difference is there are two real tables to fill instead of one.

### Where each piece goes

Your script is in this order right now. The NEW lines are what you add in this step:

    connect to the database

    -- staging tables (before conn.begin())
    drop + create product_import_staging         (already there)
    drop + create tag_import_staging             NEW, piece 1

    conn.begin()
    delete + insert products                     (already there)
    delete old Open Food Facts tags              NEW, piece 2
    insert tags                                  NEW, piece 3
    insert tag_allergen                          NEW, piece 4
    delete + insert product_allergen             (step 5 rewrites these)
    conn.commit()

    -- clean up
    drop product_import_staging                  (already there)
    drop tag_import_staging                      NEW, piece 5

Why this order:

- Staging goes before conn.begin(), just like the product staging table. Making it is DuckDB copying a file, not a change to your real data. If the import crashes, the leftover staging table doesn't hurt anything, since the "drop table if exists" at the start clears it next time.
- Pieces 2 to 4 go inside the transaction, after the products and before product_allergen. Inside the transaction means a crash can't leave you with an empty lookup. Before product_allergen, because step 5 needs the lookup filled to work.
- Piece 5 goes after commit, next to the product staging drop.

### Try it

1. Piece 1: copy your two product staging lines (the DROP TABLE IF EXISTS and the CREATE TABLE ... AS SELECT) and change them to make tag_import_staging from the CSV. You only need the columns tag, allergen, level and note.
2. Piece 2: delete the Open Food Facts rows from tag. Because of the "on delete cascade" you wrote in step 2, their tag_allergen rows are deleted too, so you don't need a second delete.
3. Piece 3: insert each tag name from staging into tag, with source 'Open Food Facts'.
4. Piece 4: insert into tag_allergen. Each staging row needs two ids: the tag's id (from the tag table you just filled) and the allergen's id (from the allergen table). Skip rows where allergen is 'none'.
5. Piece 5: drop tag_import_staging.

Pieces 2 to 4 are Postgres SQL, so each one goes in its own conn.execute("""CALL postgres_execute('pg', $$ ... $$)"""), the same wrapper as your product delete and insert.

<details><summary>Hint</summary>

- Path: you run the script from the backend folder. The parquet path starts with ../ because data is one folder up. The lookup folder is inside backend, so its path is just 'lookup/tag_allergen.csv'.
- Piece 3 needs SELECT DISTINCT, because a tag with two allergens has two rows in the file but should only be in tag once.
- Piece 4 is an INSERT ... SELECT with two joins: staging to tag on the tag name and source, and staging to allergen on the allergen name. A join only keeps rows that match on both sides, and there's no allergen named 'none', so the none rows drop out on their own.
- DuckDB reads an empty note as NULL, so unsure is just `s.note IS NOT NULL`, which gives true or false.

</details>

<details><summary>Answer</summary>

Piece 1, right after the product staging table is created:

    conn.sql("DROP TABLE IF EXISTS pg.public.tag_import_staging")
    conn.sql("""
        CREATE TABLE pg.public.tag_import_staging AS
        SELECT tag, allergen, level, note
        FROM 'lookup/tag_allergen.csv'
    """)

Pieces 2 to 4, after the product insert and before the product_allergen delete:

    conn.execute("""
        CALL postgres_execute('pg', $$
            DELETE FROM public.tag WHERE source = 'Open Food Facts'
        $$)
    """)
    conn.execute("""
        CALL postgres_execute('pg', $$
            INSERT INTO public.tag (source, name)
            SELECT DISTINCT 'Open Food Facts', lower(tag)
            FROM public.tag_import_staging
        $$)
    """)
    conn.execute("""
        CALL postgres_execute('pg', $$
            INSERT INTO public.tag_allergen (tag_id, allergen_id, level, unsure)
            SELECT t.id, a.id, s.level, s.note IS NOT NULL
            FROM public.tag_import_staging s
            JOIN public.tag t ON t.source = 'Open Food Facts' AND t.name = lower(s.tag)
            JOIN public.allergen a ON a.name = s.allergen
        $$)
    """)

Piece 5, after conn.commit(), next to the product staging drop:

    conn.sql("DROP TABLE pg.public.tag_import_staging")

</details>

### Check it

Don't run the full import yet: the product_allergen part still uses allergen_rule, which you dropped in step 3, so it will fail. That's expected, and step 5 fixes it. If you want to test this step alone first, temporarily comment out the product_allergen delete and the two inserts, run the script, and look in Studio:

- tag should have about 23,343 rows.
- tag_allergen should have about 6,400 rows (every row in the file that isn't 'none').
- `select count(*) from tag_allergen where unsure` should be about 1,300.

Then uncomment them and move on to step 5.

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
