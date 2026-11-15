import duckdb

# Database connection
print("[IMPORT] Creating DB connection...")
conn = duckdb.connect()
conn.sql("INSTALL postgres; LOAD postgres;")
conn.sql("""
    ATTACH 'dbname=postgres
            user=postgres
            password=postgres
            host=127.0.0.1
            port=54322'
    AS pg (TYPE postgres)
""")
print("[IMPORT] DB connection established.")

# DuckDB writes to Postgres with COPY, which sends NULL for any column left out
# and so bypasses product.id's identity default. Load into a staging table that
# has no id column, then let Postgres run the real INSERT and generate the ids.
print("[IMPORT] Creating Staging Table...")
conn.sql("DROP TABLE IF EXISTS pg.public.product_import_staging")
conn.sql("""
    CREATE TABLE pg.public.product_import_staging AS
    SELECT
        code AS barcode,
        name,
        'Open Food Facts' AS data_source,
        current_date AS last_checked,
        ingredients_tags AS ingredient_tags,
        allergens_tags AS allergen_tags,
        traces_tags AS trace_tags,
        categories_tags AS category_tags,
        completeness AS data_completeness,
        to_timestamp(last_modified_t) AS source_last_modified
    FROM '../data/off_us.parquet'
    WHERE name IS NOT NULL AND code IS NOT NULL
    QUALIFY row_number() OVER (PARTITION BY code ORDER BY last_modified_t DESC) = 1
""")
print("[IMPORT] Staging table created.")

# tag staging table
print("[IMPORT] Creating Tag Staging Table...")
conn.sql("DROP TABLE IF EXISTS pg.public.tag_import_staging")
conn.sql("""
    CREATE TABLE pg.public.tag_import_staging AS
    SELECT
        tag,
        allergen,
        level,
        note
    FROM 'lookup/tag_allergen.csv'
""")
print("[IMPORT] Tag staging table created.")

# ======= product Operations =======
# Swap the old import for the new one in a single transaction, so a failed insert
# can't leave the table empty. The delete also lets the script be rerun safely.
print("[IMPORT] Swapping old import for new one (so failed insert doesn't leave the table empty)...")
conn.begin()
conn.execute("""
    CALL postgres_execute('pg', $$
        DELETE FROM public.product WHERE data_source = 'Open Food Facts'
    $$)
""")
conn.execute("""
    CALL postgres_execute('pg', $$
        INSERT INTO public.product (
            barcode,
            name,
            data_source,
            last_checked,
            ingredient_tags,
            allergen_tags,
            trace_tags,
            category_tags,
            data_completeness,
            source_last_modified
        )
        SELECT
            barcode,
            name,
            data_source,
            last_checked,
            ingredient_tags,
            allergen_tags,
            trace_tags,
            category_tags,
            data_completeness,
            source_last_modified
        FROM public.product_import_staging
    $$)
""")
print("[IMPORT] Swap complete.")

# ======= tag Operations =======
# clear existing open food facts rows to avoid duplication
print("[IMPORT] Deleting Open Food Facts Rows from tag...")
conn.execute("""
    CALL postgres_execute('pg', $$
        DELETE FROM public.tag WHERE data_source = 'Open Food Facts'
    $$)
""")

conn.execute("""
    CALL postgres_execute('pg', $$
        INSERT INTO public.tag (
            data_source,
            tag_name
        )
        SELECT DISTINCT
            'Open Food Facts',
            lower(tag)
        FROM public.tag_import_staging
    $$)
""")

conn.execute("""
    CALL postgres_execute('pg', $$
        INSERT INTO public.tag_allergen ( 
            tag_id,
            allergen_id,
            level,
            is_unsure
        )
        SELECT
            t.id,
            a.id,
            s.level,
            s.note IS NOT NULL
        FROM public.tag_import_staging s
        JOIN public.tag t ON t.data_source = 'Open Food Facts' AND t.tag_name = lower(s.tag)
        JOIN public.allergen a ON s.allergen = a.name
    $$)
""")

conn.execute("""
    CALL postgres_execute('pg', $$
        ANALYZE public.product, public.tag, public.tag_allergen
    $$)
""")

# ======= product_allergen Operations =======
print("[IMPORT] Creating product allergen table...")
conn.execute("""
    CALL postgres_execute('pg', $$
        DELETE FROM public.product_allergen
    $$)
""")

# contains: matched on ingredients or OFF's allergen tags
conn.execute("""
    CALL postgres_execute('pg', $$
        INSERT INTO public.product_allergen (
            product_id,
            allergen_id,
            level
        )
        SELECT DISTINCT
            p.id,
            ta.allergen_id,
            'contains'
        FROM public.product p
        CROSS JOIN LATERAL UNNEST(COALESCE(p.ingredient_tags, '{}') || COALESCE(p.allergen_tags, '{}')) AS t(tag)
        JOIN public.tag tg ON tg.data_source = p.data_source
         AND tg.tag_name = lower(t.tag)
        JOIN public.tag_allergen ta ON ta.tag_id = tg.id
        WHERE ta.level = 'contains'
    $$)
""")

# may contain: matched on trace tag, skipped if already marked as contains
conn.execute("""
    CALL postgres_execute('pg', $$
        INSERT INTO public.product_allergen (
            product_id,
            allergen_id,
            level
        )
        SELECT DISTINCT
            p.id,
            ta.allergen_id,
            'may contain'
        FROM public.product p
        CROSS JOIN LATERAL UNNEST(COALESCE(p.ingredient_tags, '{}') || COALESCE(p.allergen_tags, '{}')) AS t(tag)
        JOIN public.tag tg ON tg.data_source = p.data_source
         AND tg.tag_name = lower(t.tag)
        JOIN public.tag_allergen ta ON ta.tag_id = tg.id
        WHERE ta.level = 'may contain'
        UNION
        SELECT DISTINCT
            p.id,
            ta.allergen_id,
            'may contain'
        FROM public.product p
        CROSS JOIN LATERAL UNNEST(COALESCE(p.trace_tags, '{}')) AS t(tag)
        JOIN public.tag tg ON tg.data_source = p.data_source
         AND tg.tag_name = lower(t.tag)
        JOIN public.tag_allergen ta ON ta.tag_id = tg.id
        ON CONFLICT (product_id, allergen_id) DO NOTHING
    $$)
""")
print("[IMPORT] Product allergen table created.")

conn.commit()
conn.sql("DROP TABLE pg.public.product_import_staging")
conn.sql("DROP TABLE pg.public.tag_import_staging")

print(conn.execute("SELECT count(*) FROM pg.public.product").fetchone()[0], "products imported (total)")