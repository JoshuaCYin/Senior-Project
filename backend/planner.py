import psycopg
from psycopg.rows import dict_row

# confidence weights
W_CONFIDENCE = 0.7
W_PANTRY = 0.3
CONFIDENCE_RESTAURANT = 0.9
CONFIDENCE_COOK = 0.85
CONFIDENCE_UNKNOWN = 0.3

# plan structure items
MEALS = ["breakfast", "lunch", "dinner"]
SITUATIONS = ["product", "restaurant", "cook"]
LABELS = {"product": "buy", "restaurant": "eat out", "cook": "cook at home"}

# products (for the prototype)
FEATURED_BARCODES = [
    "0041000003240",
    "0096619505456",
    "0021000010875",
    "0041390030666",
    "0639123000019",
    "0037600070607",
    "0851702007176",
    "3270190174356",
    "0074956182639",
    "0860997002605"
]

# example users
PROFILES = [
    {"name": "No allergies",   "allergens": [],                                 "pantry": ["rice", "egg", "banana"], "slots": {"breakfast": "any", "lunch": "any", "dinner": "any"}},
    {"name": "Milk",           "allergens": ["milk"],                           "pantry": ["rice", "pasta"],         "slots": {"breakfast": "restaurant", "lunch": "product", "dinner": "cook"}},
    {"name": "Peanut and nuts","allergens": ["peanut", "tree nuts"],            "pantry": ["flour", "egg"],          "slots": {"breakfast": "product", "lunch": "any", "dinner": "any"}},
    {"name": "Many",           "allergens": ["milk", "wheat", "gluten", "egg"], "pantry": ["rice"],                  "slots": {"breakfast": "cook", "lunch": "product", "dinner": "any"}}
]

PRODUCT_QUERY = """
    SELECT
        p.id,
        p.name,
        p.data_completeness
    FROM
        product p
    WHERE p.data_source = 'Open Food Facts'
      AND p.barcode = any(%(barcodes)s::text[])
      AND cardinality(p.ingredient_tags) > 0 --avoid empty tag arrays
      AND NOT EXISTS (
        SELECT 1
        FROM product_allergen x
        JOIN allergen a on a.id = x.allergen_id
        WHERE x.product_id = p.id
        AND a.name = any(%(allergens)s::text[])
    )
"""

MENU_QUERY = """
    SELECT
        m.id,
        m.name,
        r.name AS restaurant
    FROM menu_item m
    JOIN restaurant r ON r.id = m.restaurant_id
    WHERE NOT EXISTS (
        SELECT 1
        FROM menu_item_allergen x
        JOIN allergen a ON a.id = x.allergen_id
        WHERE x.menu_item_id = m.id
          AND a.name = any(%(allergens)s::text[])
    )
"""

RECIPE_QUERY = """
    SELECT
        r.id,
        r.title AS name,
        ARRAY_AGG(i.name) AS ingredients
    FROM recipe r
    JOIN recipe_ingredient ri ON ri.recipe_id = r.id
    JOIN ingredient i ON i.id = ri.ingredient_id
    WHERE NOT EXISTS (
        SELECT 1
        FROM recipe_ingredient ri2
        JOIN ingredient_allergen x ON x.ingredient_id = ri2.ingredient_id
        JOIN allergen a ON a.id = x.allergen_id
        WHERE ri2.recipe_id = r.id
          AND a.name = any(%(allergens)s::text[])
    )
    GROUP BY r.id, r.title
"""

DB_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

def connect():
    return psycopg.connect(DB_URL, row_factory = dict_row) # makes each row a dict so we can access it using the key names

# checks if there are misspelled/differently-named allergens
def check_allergen_names(conn, allergens):
    known = {
        row["name"] for row in conn.execute("SELECT name FROM allergen")
    }
    unknown = set(allergens) - known
    if unknown:
        raise ValueError(
            f"Unknown allergens detected: {sorted(unknown)}. \
            \nUse one of the known allergens: {sorted(known)}"
)

# gets a list of candidate items from each eating situation, filtering out items with the user's allergens
def fetch_candidates(conn, allergens):
    check_allergen_names(conn, allergens)
    params = {"allergens": list(allergens), "barcodes": FEATURED_BARCODES}
    candidates = []
    for row in conn.execute(PRODUCT_QUERY, params):
        candidates.append({
            "situation": "product",
            "id": row["id"],
            "name": row["name"],
            "completeness": row["data_completeness"],
            "ingredients": []
        })
    for row in conn.execute(MENU_QUERY, params):
        candidates.append({
            "situation": "restaurant",
            "id": row["id"],
            "name": f"{row['name']} ({row['restaurant']})",
            "ingredients": []
        })
    for row in conn.execute(RECIPE_QUERY, params):
        candidates.append({
            "situation": "cook",
            "id": row["id"],
            "name": row["name"],
            "ingredients": row["ingredients"]
        })
    return candidates

# assign confidence based on eating situation
def confidence(candidate):
    if candidate["situation"] == "restaurant":
        return CONFIDENCE_RESTAURANT
    if candidate["situation"] == "cook":
        return CONFIDENCE_COOK
    return candidate["completeness"] if candidate["completeness"] is not None else CONFIDENCE_UNKNOWN

# how much of the ingredient they already have
def pantry_match(candidate, pantry):
    if not candidate["ingredients"]: # products and menu items do not have ingredients
        return 0.0 # product and menu items get a 0 because they are bought
    have = sum(1 for i in candidate["ingredients"] if i.lower() in pantry)
    return have / len(candidate["ingredients"])

# add a score to each item on the candidate list
def score(candidate, pantry):
    candidate["confidence"] = confidence(candidate) # add a confidence value to the candidate item
    candidate["pantry_match"] = pantry_match(candidate, pantry)
    candidate["score"] = (W_CONFIDENCE * candidate["confidence"]) + (W_PANTRY * candidate["pantry_match"])

# builds a plan for a specified number of days, using the candidate list
def build_plan(candidate_list, slot_choices, days = 1):
    slots = [{"day": d + 1,
              "meal": m,
              "situation": slot_choices.get(m, "any"),
              "item": None}
              for d in range(days) for m in MEALS]
    ranked = sorted(candidate_list, key = lambda c: c["score"], reverse = True) # compare using scores, highest first
    used = set()
    fallbacks = []

    # returns the best unused item for a situation ("any" means any situation)
    def take(situation):
        for candidate in ranked:
            key = (candidate["situation"], candidate["id"])
            if key not in used and situation in ("any", candidate["situation"]):
                used.add(key)
                return candidate
        return None

    # Step 1: handle meals, based on the situation the user picked
    for slot in slots:
        if slot["situation"] != "any":
            slot["item"] = take(slot["situation"])
            if slot["item"] is None:
                fallbacks.append(f"Day {slot['day']} {slot['meal']}: no safe {LABELS[slot['situation']]} "
                                 f"options left. Try a different situation for this meal.")

    # Step 2: handle "any": "any" meals get the best of whatever is left
    for slot in slots:
        if slot["situation"] == "any":
            slot["item"] = take("any")
            if slot["item"] is None:
                fallbacks.append(f"Day {slot['day']} {slot['meal']}: nothing safe left to suggest.")
    
    return {
        "slots": slots,
        "fallbacks": fallbacks
    }

# create a complete plan for the specified number of days and user's allergens
def make_plan(conn, profile, days = 1):
    candidates = fetch_candidates(conn, profile["allergens"])
    pantry = {p.lower() for p in profile["pantry"]}
    for candidate in candidates:
        score(candidate, pantry)
    return build_plan(candidates, profile.get("slots", {}), days)

def print_plan(profile, plan):
    print(f"\n======= {profile['name']} (avoids: {', '.join(profile['allergens']) or 'nothing'}) Preferences: {', '.join([profile['slots']['breakfast'], profile['slots']['lunch'], profile['slots']['dinner']])} =======")
    for slot in plan["slots"]:
        item = slot["item"]
        if item:
            print(f"Day {slot['day']} | {slot['meal']:<9} | [{LABELS[item['situation']]:<13}] {item['name']:<30}"
                  f" | score {item['score']:.2f} (confidence {item['confidence']:.2f}, pantry {item['pantry_match']:.2f})")
        else:
            print(f"Day {slot['day']} {slot['meal']:<9} (empty)")
    for fallback in plan["fallbacks"]:
        print(f"  Fallback: {fallback}")

# ======= TESTS =======
# looks up allergens a different way than the filter queries, so a bug there can't hide itself
ALLERGENS_OF = {
    "product": """SELECT a.name FROM product_allergen x
                  JOIN allergen a ON a.id = x.allergen_id WHERE x.product_id = %s""",
    "restaurant": """SELECT a.name FROM menu_item_allergen x
                     JOIN allergen a ON a.id = x.allergen_id WHERE x.menu_item_id = %s""",
    "cook": """SELECT a.name FROM recipe_ingredient ri
               JOIN ingredient_allergen x ON x.ingredient_id = ri.ingredient_id
               JOIN allergen a ON a.id = x.allergen_id WHERE ri.recipe_id = %s""",
}

def find_conflicts(conn, profile, plan):
    problems = []
    for slot in plan["slots"]:
        item = slot["item"]
        if item:
            rows = conn.execute(ALLERGENS_OF[item["situation"]], (item["id"],)).fetchall()
            clash = {r["name"] for r in rows} & set(profile["allergens"])
            if clash:
                problems.append(f"{item['name']} contains {sorted(clash)}")
    return problems



if __name__ == "__main__":
    with connect() as conn:
        for profile in PROFILES:
            plan = make_plan(conn, profile, days = 1)
            print_plan(profile, plan)
            problems = find_conflicts(conn, profile, plan)
            print("  PASS: no allergen conflicts" if not problems else f"  FAIL: {problems}")