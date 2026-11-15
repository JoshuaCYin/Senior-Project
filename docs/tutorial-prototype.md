# Tutorial: the plan prototype (Sprint 5 proof of concept)

Goal: given an allergy profile and a pantry, make a 1-day plan with 3 meals, one from each eating situation (grab a product, eat out, cook), with no allergen conflicts. Then prove it with tests.

Each step has a time box. If you go over, take the answer and move on. A working, tested prototype that's a bit rough beats a polished half. Each step says what and why, then lets you try it. The hint and answer are folded up, so try first.

Rough budget, about 3 hours:

| Step | What | Time |
|---|---|---|
| 0 | Get running | 10 min |
| 1 | Add a little data | 50 min |
| 2 | Fetch safe candidates | 35 min |
| 3 | Score them | 20 min |
| 4 | Build the plan | 30 min |
| 5 | Test it | 25 min |
| | Buffer | 10 min |

Everything goes in two new files: backend/planner.py and backend/tests/test_planner.py, plus data in supabase.

## The big idea

This is the "filter, score, pick" design from your tech stack:

    profile (allergens, pantry)
        |
        v
    filter:  one SQL query per situation, drop anything with the user's allergens
        |
        v
    score:   0.7 * confidence + 0.3 * pantry match
        |
        v
    pick:    each situation gets its best item first, fill the rest by score,
             and add a fallback message for any situation with nothing safe

Safety is decided only by the filter, never by the score. The score only ranks things that are already safe. Keep that rule and the tests in step 5 are easy to reason about.

## Step 0: get running (10 min)

1. Unpause Docker Desktop (it's paused right now), then run `npx supabase start` from the project folder.
2. Open Studio (http://127.0.0.1:54323) and check that product and product_allergen have rows. If they're empty, rerun the import from the backend folder.
3. From the backend folder, add the Postgres driver and pytest:

       uv add "psycopg[binary]"
       uv add --dev pytest

Why psycopg and not DuckDB like the import? The import moves a lot of data at once, which DuckDB is good at. The planner runs small queries with user input in them. psycopg sends the user's values as parameters (separately from the SQL text), which is what prevents SQL injection. Your tech stack lists SQLAlchemy/SQLModel for the real app; plain psycopg is enough for a prototype.

Important: don't run `npx supabase db reset` during this tutorial unless you have to. It wipes the products and you'd need to rerun the import. Steps 1a to 1c show how to add things without a reset.

## Step 1: add a little data (50 min)

You need about 10 of each so the planner has real choices. Vary the allergens on purpose: some items with milk, some with wheat, some with nuts, a few with none. If everything has milk, your tests won't show much.

Also plan for one profile where a whole situation has nothing safe (for example, every menu item has milk or wheat or egg). You need that to show the fallback.

### 1a. Hand-picked products (15 min)

Open Food Facts has hundreds of thousands of products, and most aren't a meal (candy, spices, sauces). So you'll pick 10 that are.

Gotcha: product ids change every time the import reruns (it's in your decision log). So don't save product ids. Save something that stays the same.

Try it: make a migration for a small table that remembers which products you picked, without using product.id. Apply it with `npx supabase migration up`, which runs new migrations without wiping anything.

<details><summary>Hint</summary>

What makes a product unique and survives a reimport? Look at the unique constraint in the generalize_product migration. Don't add a foreign key to product: the products get deleted and reinserted on import, and this table should survive that.

</details>

<details><summary>Answer</summary>

`npx supabase migration new add_featured_product`, then in the new file:

    -- products hand-picked for the prototype. Uses barcode, not product id,
    -- because product ids change every time the import reruns.
    create table featured_product (
        data_source text not null,
        barcode     text not null,
        primary key (data_source, barcode)
    );

</details>

Now find candidates in Studio's SQL editor. Something like this, then adjust the category tags to what you see:

    select barcode, name, data_completeness, category_tags
    from product
    where category_tags && array['en:meals', 'en:frozen-meals', 'en:sandwiches', 'en:salads']
      and data_completeness > 0.7
      and cardinality(ingredient_tags) > 0
    order by data_completeness desc
    limit 100;

(`&&` means "the two arrays share at least one item".)

Pick 10 and insert them:

    insert into featured_product (data_source, barcode) values
      ('Open Food Facts', '...'),
      ...;

Then check what allergens your picks have, so you know what the tests should do:

    select p.name, a.name as allergen, pa.level
    from featured_product f
    join product p on p.data_source = f.data_source and p.barcode = f.barcode
    left join product_allergen pa on pa.product_id = p.id
    left join allergen a on a.id = pa.allergen_id
    order by p.name;

Save your insert in seed.sql too, so a future reset brings them back. Seed runs before the import, but that's fine because there's no foreign key.

### 1b. Menu items (20 min)

Copy 10 items from one or two published allergen charts (your tech stack mentions Chipotle and Outback). Copy them yourself from the real chart. Don't let an AI fill these in from memory, since this is the data that decides safety.

- Pick meals (a bowl, a sandwich), not sides or drinks.
- Whatever the chart marks as an allergen is 'contains'. Cross-contact warnings ("prepared on shared equipment") are 'may contain'.
- Put the chart's URL in data_source and today's date in last_checked. That's your evidence of where the data came from.
- Only use allergen names that are in the allergen table ('tree nuts' not 'tree nut', 'peanut' not 'peanuts').

Try it: write the inserts for restaurant, menu_item and menu_item_allergen. Use names in the joins instead of guessing ids, like the existing recipe part of seed.sql.

<details><summary>Answer (the pattern, with placeholder names)</summary>

    insert into restaurant (name) values ('Restaurant One');

    insert into menu_item (restaurant_id, name, data_source, last_checked)
    select r.id, x.item, x.url, date '2026-11-15'
    from (values
      ('Restaurant One', 'Item A', 'https://...chart url...'),
      ('Restaurant One', 'Item B', 'https://...chart url...')
    ) as x(restaurant, item, url)
    join restaurant r on r.name = x.restaurant;

    insert into menu_item_allergen (menu_item_id, allergen_id, level)
    select m.id, a.id, x.level
    from (values
      ('Item A', 'milk',  'contains'),
      ('Item A', 'wheat', 'contains'),
      ('Item A', 'gluten','contains'),
      ('Item B', 'soy',   'may contain')
    ) as x(item, allergen, level)
    join menu_item m on m.name = x.item
    join allergen a  on a.name = x.allergen;

If an allergen name is misspelled, the join quietly drops that row. Afterwards, count rows per item to make sure nothing went missing.

</details>

Remember the gluten rule from your decision log: if the chart says wheat, add gluten too.

### 1c. Recipes (15 min)

You already have Banana bread and Plain rice. Add about 8 more simple ones. Keep ingredient names generic ('butter', 'soy sauce', 'pasta').

Two things to watch:

- The existing seed links flour to wheat only. Your gluten rule says wheat counts as gluten, so add flour to gluten too. Same for anything with wheat (pasta, bread, soy sauce, tortillas).
- Some ingredients have hidden allergens: soy sauce is soy and wheat and gluten, pesto usually has tree nuts and milk, mayo is egg.

Since 'egg', 'flour' and others already exist, add `on conflict (name) do nothing` to the ingredient insert so it doesn't fail. Use the same pattern as the existing seed for ingredient_allergen and recipe_ingredient.

To load it now without a reset: append the new SQL to seed.sql (so future resets include it), and also paste just the new part into Studio's SQL editor and run it.

Check: every recipe should show its allergens:

    select r.title, string_agg(distinct a.name, ', ') as allergens
    from recipe r
    join recipe_ingredient ri on ri.recipe_id = r.id
    left join ingredient_allergen ia on ia.ingredient_id = ri.ingredient_id
    left join allergen a on a.id = ia.allergen_id
    group by r.title;

## Step 2: fetch safe candidates (35 min)

Make backend/planner.py. A user profile is just a dict for now (user tables come in the spring):

    PROFILES = [
        {"name": "No allergies",   "allergens": [],                  "pantry": ["rice", "egg", "banana"]},
        {"name": "Milk",           "allergens": ["milk"],            "pantry": ["rice", "pasta"]},
        {"name": "Peanut and nuts","allergens": ["peanut", "tree nuts"], "pantry": ["flour", "egg"]},
        {"name": "Hard case",      "allergens": ["milk", "wheat", "gluten", "egg"], "pantry": ["rice"]},
    ]

Change "Hard case" to whatever empties out one situation in your data.

Connecting:

    import psycopg
    from psycopg.rows import dict_row

    DB_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

    def connect():
        return psycopg.connect(DB_URL, row_factory=dict_row)

`dict_row` makes each row a dict, so you can write `row["name"]` instead of `row[1]`.

### The three queries

Try it: write one query per situation that returns only items with none of the user's allergens. The user's allergen names come in as a parameter, `%(allergens)s`, which psycopg turns into a Postgres array.

- grab: products in featured_product
- eat out: menu items, plus the restaurant name
- cook: recipes, plus a list of their ingredient names (you'll need it for pantry match)

Two safety details:

1. Treat 'may contain' as unsafe too. For a prototype, strict is the right default. (Letting users allow 'may contain' at a lower confidence can come later.)
2. A product with no ingredient data has no allergen rows, so it looks safe when really nobody knows. Leave those out.

<details><summary>Hint</summary>

"Has none of these allergens" is easiest to write as NOT EXISTS: keep the item if there does NOT EXIST an allergen row for it whose name is in the user's list.

    where not exists (
        select 1
        from <item>_allergen x
        join allergen a on a.id = x.allergen_id
        where x.<item>_id = <outer item>.id
          and a.name = any(%(allergens)s::text[])
    )

The `::text[]` cast matters when the list is empty: without it Postgres can't tell what type an empty array is.

For recipes, allergens come through two joins: recipe_ingredient, then ingredient_allergen. To get the ingredient list, use `array_agg(i.name)` with `group by`.

</details>

<details><summary>Answer</summary>

    PRODUCT_SQL = """
        select p.id, p.name, p.data_completeness
        from featured_product f
        join product p on p.data_source = f.data_source and p.barcode = f.barcode
        where cardinality(p.ingredient_tags) > 0
          and not exists (
            select 1
            from product_allergen x
            join allergen a on a.id = x.allergen_id
            where x.product_id = p.id
              and a.name = any(%(allergens)s::text[])
          )
    """

    MENU_SQL = """
        select m.id, m.name, r.name as restaurant
        from menu_item m
        join restaurant r on r.id = m.restaurant_id
        where not exists (
            select 1
            from menu_item_allergen x
            join allergen a on a.id = x.allergen_id
            where x.menu_item_id = m.id
              and a.name = any(%(allergens)s::text[])
        )
    """

    RECIPE_SQL = """
        select r.id, r.title as name, array_agg(i.name) as ingredients
        from recipe r
        join recipe_ingredient ri on ri.recipe_id = r.id
        join ingredient i on i.id = ri.ingredient_id
        where not exists (
            select 1
            from recipe_ingredient ri2
            join ingredient_allergen x on x.ingredient_id = ri2.ingredient_id
            join allergen a on a.id = x.allergen_id
            where ri2.recipe_id = r.id
              and a.name = any(%(allergens)s::text[])
        )
        group by r.id, r.title
    """

</details>

### The trap: misspelled allergens

If someone passes "peanuts" instead of "peanut", nothing matches, so nothing gets filtered out, and the planner happily calls everything safe. That's the worst possible failure for this app.

Try it: write `check_allergen_names(conn, allergens)` that raises a ValueError if any name isn't in the allergen table. Then write `fetch_candidates(conn, allergens)` that checks the names, runs the three queries, and returns one list of dicts, each with: situation ("grab", "eat_out" or "cook"), id, name, and whatever that situation needs later (completeness for products, ingredients for recipes).

<details><summary>Answer</summary>

    def check_allergen_names(conn, allergens):
        known = {row["name"] for row in conn.execute("select name from allergen")}
        unknown = set(allergens) - known
        if unknown:
            raise ValueError(f"Unknown allergens {sorted(unknown)}. Use one of {sorted(known)}")

    def fetch_candidates(conn, allergens):
        check_allergen_names(conn, allergens)
        params = {"allergens": list(allergens)}
        candidates = []
        for row in conn.execute(PRODUCT_SQL, params):
            candidates.append({"situation": "grab", "id": row["id"], "name": row["name"],
                               "completeness": row["data_completeness"], "ingredients": []})
        for row in conn.execute(MENU_SQL, params):
            candidates.append({"situation": "eat_out", "id": row["id"],
                               "name": f"{row['name']} ({row['restaurant']})", "ingredients": []})
        for row in conn.execute(RECIPE_SQL, params):
            candidates.append({"situation": "cook", "id": row["id"], "name": row["name"],
                               "ingredients": row["ingredients"]})
        return candidates

</details>

Quick check: call it with `[]` and with `["milk"]` and print the counts. The milk list should be shorter.

## Step 3: score them (20 min)

score = 0.7 * confidence + 0.3 * pantry match. Both are between 0 and 1, so the score is too. Confidence gets more weight because this is an allergy app.

Confidence means "how much do we trust the allergen data for this item":

- grab: the product's data_completeness (Open Food Facts' 0 to 1 score). If it's missing, use something low like 0.3.
- eat out: a constant, like 0.9. It's the restaurant's own chart, but kitchens have cross-contact.
- cook: a constant, like 0.85. You chose the ingredients, but a store-bought ingredient's brand could still have something.

Pantry match means "how much of this do you already have": for a recipe, the share of its ingredients that are in the pantry. Products and menu items are bought, so they get 0.

Put the weights and constants as named values at the top of the file, so they're easy to find and change.

Try it: write `score(candidate, pantry)` that adds confidence, pantry_match and score to the candidate dict.

<details><summary>Answer</summary>

    W_CONFIDENCE = 0.7
    W_PANTRY = 0.3
    CONFIDENCE_EAT_OUT = 0.9
    CONFIDENCE_COOK = 0.85
    CONFIDENCE_UNKNOWN = 0.3

    def confidence(c):
        if c["situation"] == "eat_out":
            return CONFIDENCE_EAT_OUT
        if c["situation"] == "cook":
            return CONFIDENCE_COOK
        return c["completeness"] if c["completeness"] is not None else CONFIDENCE_UNKNOWN

    def pantry_match(c, pantry):
        if not c["ingredients"]:
            return 0.0
        have = sum(1 for i in c["ingredients"] if i.lower() in pantry)
        return have / len(c["ingredients"])

    def score(c, pantry):
        c["confidence"] = confidence(c)
        c["pantry_match"] = pantry_match(c, pantry)
        c["score"] = W_CONFIDENCE * c["confidence"] + W_PANTRY * c["pantry_match"]

</details>

Something to notice, and worth a sentence in your findings: because only recipes can get pantry points, recipes will usually win the "fill the rest" step. That might be fine (cheaper, and leftovers come later), but it's a bias the weights create.

## Step 4: build the plan (30 min)

The rules:

1. Day 1 is breakfast, lunch, dinner. Give each situation its best item first: grab for breakfast, eat out for lunch, cook for dinner.
2. If a situation has nothing safe, add a fallback message for it, and leave its slot open for step 3.
3. Fill any open slots with the best remaining items by score, no repeats.
4. If slots are still empty (nothing safe left), add a fallback for those too.

Let the function take `days` (default 1). With days=2, day 2's three slots are all filled by step 3. That gives you multi-day plans almost for free.

Try it: write `build_plan(candidates, days=1)` that returns `{"slots": [...], "fallbacks": [...]}`, where each slot is `{"day", "meal", "item"}`. Then write `make_plan(conn, profile, days=1)` that runs fetch, score and build, and a `__main__` block that prints a plan for each profile.

<details><summary>Hint</summary>

Sort all candidates by score once (`sorted(..., key=lambda c: c["score"], reverse=True)`). Then "the best item for a situation" is just the first one in that list with that situation: `next((c for c in ranked if c["situation"] == s), None)`.

To avoid repeats, remember the used items as `(situation, id)` pairs, since a product and a recipe can have the same id.

</details>

<details><summary>Answer</summary>

    MEALS = ["breakfast", "lunch", "dinner"]
    SITUATIONS = ["grab", "eat_out", "cook"]   # day 1's breakfast, lunch, dinner
    LABELS = {"grab": "grab-and-go", "eat_out": "eat out", "cook": "cook at home"}

    def build_plan(candidates, days=1):
        slots = [{"day": d + 1, "meal": m, "item": None} for d in range(days) for m in MEALS]
        ranked = sorted(candidates, key=lambda c: c["score"], reverse=True)
        used = set()
        fallbacks = []

        # 1. each situation gets its best item first
        for slot, situation in zip(slots, SITUATIONS):
            best = next((c for c in ranked if c["situation"] == situation), None)
            if best is None:
                fallbacks.append(f"No safe {LABELS[situation]} options for this profile.")
            else:
                slot["item"] = best
                used.add((best["situation"], best["id"]))

        # 2. fill the rest by score
        rest = [c for c in ranked if (c["situation"], c["id"]) not in used]
        for slot in slots:
            if slot["item"] is None and rest:
                slot["item"] = rest.pop(0)

        # 3. anything still empty
        for slot in slots:
            if slot["item"] is None:
                fallbacks.append(f"Day {slot['day']} {slot['meal']}: nothing safe left to suggest.")

        return {"slots": slots, "fallbacks": fallbacks}

    def make_plan(conn, profile, days=1):
        candidates = fetch_candidates(conn, profile["allergens"])
        pantry = {p.lower() for p in profile["pantry"]}
        for c in candidates:
            score(c, pantry)
        return build_plan(candidates, days)

    def print_plan(profile, plan):
        print(f"\n=== {profile['name']} (avoids: {', '.join(profile['allergens']) or 'nothing'}) ===")
        for s in plan["slots"]:
            item = s["item"]
            if item:
                print(f"Day {s['day']} {s['meal']:<9} [{LABELS[item['situation']]}] {item['name']}"
                      f"  score {item['score']:.2f} (confidence {item['confidence']:.2f}, pantry {item['pantry_match']:.2f})")
            else:
                print(f"Day {s['day']} {s['meal']:<9} (empty)")
        for f in plan["fallbacks"]:
            print(f"  Fallback: {f}")

    if __name__ == "__main__":
        with connect() as conn:
            for profile in PROFILES:
                print_plan(profile, make_plan(conn, profile))

</details>

Run it from the backend folder: `uv run planner.py`. Read the output and ask yourself whether each pick makes sense. If something looks off, it's usually the data from step 1.

## Step 5: test it (25 min)

This is your Sprint 5 evidence. The main test: for every profile, nothing in the plan contains any of that profile's allergens.

The important part: the test must check allergens a different way than the planner does. If the test reused the planner's queries, a bug in them would pass its own test. So write a small, separate function that just asks "what allergens does this one item have?" and compare.

Setup: make backend/tests/test_planner.py, and add this to backend/pyproject.toml so the tests can `import planner`:

    [tool.pytest.ini_options]
    pythonpath = ["."]

Tests to write:

1. No allergen conflicts, for every profile in PROFILES, with days=2 so the fill step gets tested too.
2. The checker actually catches a conflict (a "negative control"): take a menu item you know has milk and make sure your allergen function says milk. Without this, a broken checker that always returns nothing would pass test 1.
3. No allergies means all three situations show up and there are no fallbacks.
4. The hard case profile gets a fallback.
5. A misspelled allergen raises ValueError.
6. No item appears twice in a plan.

<details><summary>Hint</summary>

`@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p["name"])` runs one test per profile and names each one in the output. A fixture with `scope="module"` lets all tests share one database connection.

</details>

<details><summary>Answer</summary>

    import pytest
    from planner import connect, make_plan, PROFILES

    # Checks allergens a different way than the planner's filter, on purpose.
    ALLERGENS_OF = {
        "grab": """select a.name from product_allergen x
                   join allergen a on a.id = x.allergen_id where x.product_id = %s""",
        "eat_out": """select a.name from menu_item_allergen x
                      join allergen a on a.id = x.allergen_id where x.menu_item_id = %s""",
        "cook": """select a.name from recipe_ingredient ri
                   join ingredient_allergen x on x.ingredient_id = ri.ingredient_id
                   join allergen a on a.id = x.allergen_id where ri.recipe_id = %s""",
    }

    def allergens_of(conn, item):
        rows = conn.execute(ALLERGENS_OF[item["situation"]], (item["id"],)).fetchall()
        return {r["name"] for r in rows}

    @pytest.fixture(scope="module")
    def conn():
        with connect() as c:
            yield c

    @pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p["name"])
    def test_no_allergen_conflicts(conn, profile):
        plan = make_plan(conn, profile, days=2)
        for slot in plan["slots"]:
            item = slot["item"]
            if item:
                clash = allergens_of(conn, item) & set(profile["allergens"])
                assert not clash, f"{item['name']} contains {clash}"

    def test_checker_catches_a_conflict(conn):
        row = conn.execute("""select x.menu_item_id as id from menu_item_allergen x
                              join allergen a on a.id = x.allergen_id
                              where a.name = 'milk' limit 1""").fetchone()
        assert row, "need at least one menu item with milk for this test"
        assert "milk" in allergens_of(conn, {"situation": "eat_out", "id": row["id"]})

    def test_no_allergies_gets_every_situation(conn):
        plan = make_plan(conn, {"name": "none", "allergens": [], "pantry": []})
        assert {s["item"]["situation"] for s in plan["slots"]} == {"grab", "eat_out", "cook"}
        assert plan["fallbacks"] == []

    def test_hard_case_gets_a_fallback(conn):
        hard = next(p for p in PROFILES if p["name"] == "Hard case")
        assert make_plan(conn, hard)["fallbacks"]

    def test_misspelled_allergen_is_rejected(conn):
        with pytest.raises(ValueError):
            make_plan(conn, {"name": "typo", "allergens": ["peanuts"], "pantry": []})

    @pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p["name"])
    def test_no_repeats(conn, profile):
        items = [(s["item"]["situation"], s["item"]["id"])
                 for s in make_plan(conn, profile, days=2)["slots"] if s["item"]]
        assert len(items) == len(set(items))

</details>

Run `uv run pytest -v` from the backend folder.

## Evidence for the Sprint 5 report

- Screenshot or copy of `uv run planner.py` output for each profile. That's your demo.
- Screenshot of `uv run pytest -v`, all passing. That goes in the testing table (core function, expected, actual, pass/fail): one row per test.
- Commit with a clear message, and link backend/planner.py, the tests, and the migration in the report.
- Log in docs/decision-log.md: the scoring weights and confidence numbers and why, strict 'may contain', leaving out products with no ingredient data, the misspelling check, and saving picked products by barcode.

Intentionally left out (for the "reserved for spring" question): user accounts and saved plans, leftovers, matching meal type (a restaurant dinner at breakfast), a 'may contain' option, the "unsure" confidence from tag_allergen, the frontend, and an API endpoint.

## If you have time left

- Wrap make_plan in a FastAPI route, like `GET /plan?allergens=milk,peanut&days=2`, so the demo can show it in FastAPI's automatic docs page at /docs.
- Try days=3 and see how the fill step behaves when it runs out of items.
