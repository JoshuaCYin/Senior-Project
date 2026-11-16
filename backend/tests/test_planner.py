# NOTE: Test code is written by Claude

import pytest
from planner import connect, make_plan, find_conflicts, PROFILES

@pytest.fixture(scope="module")
def conn():
    with connect() as c:
        yield c

# the main one: no plan ever includes something the person is allergic to
@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p["name"])
def test_no_allergen_conflicts(conn, profile):
    plan = make_plan(conn, profile, days=2)
    assert find_conflicts(conn, profile, plan) == []

# negative control: proves the checker can actually catch a conflict,
# so the test above can't pass just because the checker is broken
def test_checker_catches_a_conflict(conn):
    fake_plan = {"slots": [{"item": {"situation": "restaurant", "name": "test",
        "id": conn.execute("""SELECT x.menu_item_id AS id FROM menu_item_allergen x
                              JOIN allergen a ON a.id = x.allergen_id
                              WHERE a.name = 'milk' LIMIT 1""").fetchone()["id"]}}]}
    assert find_conflicts(conn, {"allergens": ["milk"]}, fake_plan) != []

# each meal the user fixed to a situation gets that situation (or stays empty)
@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p["name"])
def test_fixed_slots_respected(conn, profile):
    for slot in make_plan(conn, profile)["slots"]:
        if slot["situation"] != "any" and slot["item"]:
            assert slot["item"]["situation"] == slot["situation"]

# when a situation runs out of safe items, you get a fallback instead of a crash
def test_fallback_when_nothing_safe(conn):
    profile = {"name": "every meal out", "allergens": ["milk", "wheat", "gluten", "egg"], "pantry": [],
               "slots": {"breakfast": "restaurant", "lunch": "restaurant", "dinner": "restaurant"}}
    plan = make_plan(conn, profile, days=3)  # 9 restaurant meals, far more than are safe
    assert plan["fallbacks"]

def test_misspelled_allergen_is_rejected(conn):
    with pytest.raises(ValueError):
        make_plan(conn, {"name": "typo", "allergens": ["peanuts"], "pantry": []})

@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p["name"])
def test_no_repeats(conn, profile):
    items = [(s["item"]["situation"], s["item"]["id"])
             for s in make_plan(conn, profile, days=2)["slots"] if s["item"]]
    assert len(items) == len(set(items))