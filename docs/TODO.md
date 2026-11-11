# TODO

## Allergen lookup table

- Review the AI's labels: go through docs/tag-review-unsure.csv and docs/tag-review-disagreements.csv, starting with the most used tags.
- Decide on en:flour: it's none for now because OFF adds it to every flour, but plain "flour" usually means wheat.
- Decide on oat milk: oat milk, oat base and oat milk powder are none to match the rule, but oats are usually "may contain" gluten.
- Work through docs/tutorial-tag-lookup.md: add gluten, make the lookup tables, and switch the import over.
- Compare the new results to the old rules: backend/lookup/old_allergen_rules.json has the old patterns.

## Import script

- Make the data file path work from any folder: right now it only works when run from backend.
- Fix the "products imported" count: it counts every product, not just this import.
- Only clear allergen rows for the source being imported: matters once there's a second data source.

## App

- Show "no allergen found", not "safe": some products have missing or messy ingredient data.
- Let users choose if refined oils count: for now peanut oil always counts as peanut.
