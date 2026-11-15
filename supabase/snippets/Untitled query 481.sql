SELECT allergen.name, COUNT(allergen.name), product_allergen.level
FROM allergen
JOIN product_allergen on product_allergen.allergen_id = allergen.id
GROUP BY allergen.name, product_allergen.level;