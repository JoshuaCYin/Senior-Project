# TODO

## Allergen lookup table

- Spot check the AI's labels when there's time: docs/tag-review-unsure.csv and docs/tag-review-disagreements.csv, most used tags first. Not blocking.
- Work through docs/tutorial-tag-lookup.md: add gluten, make the lookup tables, and switch the import over.
- Compare the new results to the old rules: backend/lookup/old_allergen_rules.json has the old patterns.
- Carry "unsure" through to products: a product's allergen should be low confidence when only unsure tags flagged it. Needs a column on product_allergen and a change to the step 5 inserts.
- Add soy, fish and shellfish to seed.sql: the lookup file already has rows for them, so the import may fail or skip them until the allergen table has these names.
- Spot check the soy, fish and shellfish unsure tags: docs/tag-review-unsure-new.csv, most used first. Not blocking.

## Import script

- Make the data file path work from any folder: right now it only works when run from backend.
- Fix the "products imported" count: it counts every product, not just this import.
- Only clear allergen rows for the source being imported: matters once there's a second data source.

## App

- Show "no allergen found", not "safe": some products have missing or messy ingredient data.
- Let users choose if refined oils count: for now peanut oil always counts as peanut.
- Let users avoid a specific ingredient: for things that aren't one of the main allergens, like coconut, mustard or cilantro. The app would check product tags directly against the tag table.

## Plan prototype (Sprint 5)

- Build the plan prototype: follow docs/tutorial-prototype.md (data, safe candidate queries, scoring, plan, tests).
