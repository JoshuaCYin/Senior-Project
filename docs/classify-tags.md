# Instructions: classifying ingredient tags (for an AI session)

Paste this into a new Claude session opened in this repo, or say "follow docs/classify-tags.md". No API key is needed, since the session does the classifying itself.

## Goal

Label each Open Food Facts tag with the allergens it means, so the import can look tags up instead of pattern matching. Read AGENTS.md and docs/decision-log.md first for background.

## Files

- Input: data/tags_to_classify.csv. Every tag used by 5 or more products, most used first. Columns: tag (lowercase), products (how many products use it), found_in (ingredients, allergens, and/or traces), old_rule_hint (what the old pattern rules said, may be wrong), examples (two product names that use it).
- Output: backend/lookup/tag_allergen.csv. Columns: tag,allergen,level,note
  - One row per tag and allergen pair. A tag with two allergens gets two rows.
  - A tag with no allergen gets one row with allergen "none" and an empty level. Every input tag must end up in the output, so we know it was checked.
  - note is empty unless you're unsure. Then write "unsure: " and why.
- The old pattern rules are in backend/lookup/old_allergen_rules.json, for reference only.

## Allergens

Use these names exactly: milk, egg, wheat, gluten, tree nuts, peanut, sesame, soy, fish, shellfish.

Levels:
- contains: the ingredient is or is made from the allergen.
- may contain: the tag is a warning, not an ingredient ("may contain peanuts", "made in a facility that processes milk", "shared equipment with tree nuts"). Also any tag where found_in is only "traces".

## Decisions already made by the project owner

- Coconut is not a tree nut. Anything coconut gets none (unless it also names a real allergen).
- Gluten is its own allergen. Anything with wheat (including spelt, durum, semolina, farro, kamut, einkorn, emmer, triticale, bulgur, couscous, seitan) is both wheat and gluten. Barley, rye, malt (barley malt), and brewer's yeast are gluten but not wheat.
- Regular oats are gluten, may contain (they're almost always cross-contaminated). Oats labeled gluten-free are none.
- OFF's own "en:gluten" tag is gluten, not wheat. (The old rule hint says wheat for it. That's wrong now.)
- Peanut oil counts as peanut, contains, even when it says highly refined. Same goes for other refined oils of an allergen (like sesame oil or almond oil).
- Plant milks and butters (oat, soy, rice, almond, coconut, cocoa butter, shea butter, peanut butter) are not milk. Almond milk is still tree nuts and peanut butter is still peanut.
- Soy: soybeans, soya, edamame, tofu, tempeh, miso, natto, tamari, shoyu, soy sauce, soy protein, soy flour, and textured or hydrolyzed soy protein are soy, contains.
- Soybean oil and soy lecithin are soy, contains, with the note "unsure: refined soy, most soy-allergic people tolerate it". This follows the refined oil rule above, but the unsure note lets the app give it lower confidence. Lecithin with no source given (including E322) and textured vegetable protein are soy with an unsure note too.
- Plain "vegetable oil" and tocopherols (vitamin E) are none for soy. The source isn't named, and they're refined. Sunflower, canola and rapeseed lecithin are none.
- Fish: any fish species, plus fish sauce, anchovy (including in Worcestershire sauce and Caesar dressing tags), fish gelatin, fish oil, surimi, roe and caviar. Omega-3, DHA and EPA with no source given are fish with an unsure note, since they're often from fish oil but can be from algae. Algal oil and DHA algal oil are none.
- Shellfish: crustaceans (shrimp, prawn, crab, lobster, crayfish, krill) are shellfish, contains. Mollusks (clam, oyster, scallop, mussel, squid, octopus, snail) are shellfish, contains, with the note "unsure: mollusk, not a crustacean". US law only counts crustaceans, but many people with shellfish allergies avoid both.
- Shellfish is not fish, and fish is not shellfish. Surimi is fish, and imitation crab or lobster is also shellfish with an unsure note.
- Thai curry pastes (red, green, yellow, massaman) usually have shrimp paste, so they're shellfish with an unsure note. Kimchi is fish and shellfish with unsure notes. Crickets and cricket flour are shellfish with an unsure note, since people with shellfish allergies can react to insects.
- When truly unsure, choose the safer label (flag it) and add an "unsure" note.

## Watch out for

- Parent tags OFF adds on top of the real ingredient. "en:nut" is added to every peanut, so en:nut alone is none (the specific tag handles it). en:tree-nut is tree nuts, contains. en:dairy is milk, contains.
- Words hiding inside other words: parmigiano-reggiano (milk, not egg), veggie (not egg), boeuf (beef, not egg), nutmeg (not a nut), butternut squash (not milk), buckwheat (not wheat), water chestnut (not a tree nut), goat milk (milk, even though it contains "oat milk"), shellfish, crayfish and cuttlefish (not fish), catfish, monkfish and swordfish (fish), starfish and jellyfish (neither), oyster mushroom (not shellfish), artificial crab flavor and crab seasoning (none, no real crab).
- OFF spells soy as "soya" in its main tags: en:soya-oil and en:soya-lecithin, not en:soybean-oil and en:soy-lecithin.
- "free" tags: gluten-free oats (none), cage-free eggs (egg), lactose-free milk (milk, still milk), peanut-free facility (none), soy-free and fish-free (none).
- Tags in other languages: lait, leche, milch (milk), oeuf, huevo (egg), trigo, ble, weizen (wheat), amande, noisette, nuez (tree nuts), arachide, cacahuete, erdnuss (peanut), sesamo (sesame), soja, soia (soy), poisson, pescado, fisch (fish), crevette, gamba, camaron, crabe, homard (shellfish).
- The same tag can show up spelled with spaces and with dashes (en:light tuna and en:light-tuna). Label both.
- Junk tags from bad label scans (long run-on sentences, typos). Label based on what they clearly mention. If a junk tag lists several ingredients, include every allergen it names.

## How to work

1. Go in order, in chunks of about 500 rows.
2. After each chunk, append to the output file right away, so progress isn't lost.
3. If the output file already exists, skip tags already in it and continue where it left off.
4. The first 5,000 tags matter most (they cover about 96% of all tag uses). If the session is running long, finish those first and stop cleanly at a chunk boundary.
5. Don't write a script that guesses with patterns. That's what we're replacing. Look at each tag. Scripts are fine for reading and writing the files and for the checks below.

## Checks when done

1. Every tag in the input appears in the output, and every allergen and level value is one of the allowed ones.
2. These come out right: en:goat-milk milk, en:oat-milk none, en:cocoa-butter none, en:parmigiano-reggiano milk only, en:veggie-blend none, en:cage-free-eggs egg, en:buckwheat none, en:wheat-flour wheat and gluten, en:barley-malt-extract gluten only, en:oat gluten may contain, en:gluten-free-oats none, en:coconut none, en:nutmeg none, en:almondmilk tree nuts only, en:peanut-oil peanut, en:highly-refined-peanut-oil peanut, en:jalapeno-peanuts peanut, en:tahini sesame, en:may-contain-peanuts peanut may contain, en:nut none, en:soy-sauce soy (plus wheat and gluten), en:soya-oil soy unsure, en:soya-lecithin soy unsure, en:tofu soy, en:edamame soy, en:fish-sauce fish, en:anchovy fish, en:worcestershire-sauce fish, en:shrimp shellfish, en:crawfish shellfish only, en:clam shellfish unsure, en:shellfish shellfish only, en:catfish fish, en:vegetable-oil none.
3. Compare against old_rule_hint and list the tags where you disagree, with a short reason, so the project owner can review them.
4. List every "unsure" tag for the project owner to review.
5. Add a dated entry to docs/decision-log.md saying what was classified and anything surprising, and update docs/TODO.md.
