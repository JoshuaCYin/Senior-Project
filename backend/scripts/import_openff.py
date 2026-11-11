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

print("[IMPORT] Creating product allergen table...")
# These run inside Postgres, one command per postgres_execute call, in the same
# transaction as the swap above.
conn.execute("""
    CALL postgres_execute('pg', $$
        DELETE FROM public.product_allergen
    $$)
""")

# contains: matched on ingredients or OFF's allergen tags
conn.execute("""
    CALL postgres_execute('pg', $$
        INSERT INTO public.product_allergen (product_id, allergen_id, level)
        SELECT DISTINCT p.id, r.allergen_id, 'contains'
        FROM public.product p
        CROSS JOIN LATERAL UNNEST(COALESCE(p.ingredient_tags, '{}') || COALESCE(p.allergen_tags, '{}')) AS t(tag)
        JOIN public.allergen_rule r
            ON r.source = p.data_source AND r.kind = 'include' AND t.tag LIKE r.pattern
        WHERE NOT EXISTS (
            SELECT 1
            FROM public.allergen_rule x
            WHERE x.allergen_id = r.allergen_id
                AND x.source = r.source
                AND x.kind = 'exclude'
                AND t.tag LIKE x.pattern
        )
    $$)
""")

# may contain: matched on trace tag, skipped if already marked as contains
conn.execute("""
    CALL postgres_execute('pg', $$
        INSERT INTO public.product_allergen (product_id, allergen_id, level)
        SELECT DISTINCT p.id, r.allergen_id, 'may contain'
        FROM public.product p
        CROSS JOIN LATERAL UNNEST(COALESCE(p.trace_tags, '{}')) AS t(tag)
        JOIN public.allergen_rule r
            ON r.source = p.data_source AND r.kind = 'include' AND t.tag LIKE r.pattern
        WHERE NOT EXISTS (
            SELECT 1
            FROM public.allergen_rule x
            WHERE x.allergen_id = r.allergen_id
                AND x.source = r.source
                AND x.kind = 'exclude'
                AND t.tag LIKE x.pattern
        )
        ON CONFLICT (product_id, allergen_id) DO NOTHING
    $$)
""")
print("[IMPORT] Product allergen table created.")

conn.commit()
conn.sql("DROP TABLE pg.public.product_import_staging")

print(conn.execute("SELECT count(*) FROM pg.public.product").fetchone()[0], "products imported (total)")