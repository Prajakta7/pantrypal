-- =============================================================================
-- 4. AI diet labels with ai.if (AlloyDB AI functions)
-- ai.if asks a yes/no question about each row, right inside SQL, using Gemini.
-- The app runs the same kind of query when you add a recipe.
-- =============================================================================
SET google_ml_integration.enable_preview_ai_functions = 'on';

-- --- A) Label any recipe that doesn't have labels yet (e.g. ones you added) ------
UPDATE recipes SET
  vegetarian  = ai.if(prompt => 'Recipe: ' || title || '. Ingredients: ' || array_to_string(ingredients, ', ')
                                   || '. Is this recipe vegetarian in the Indian sense (no meat, poultry, fish or eggs)?'),
  eggetarian  = ai.if(prompt => 'Recipe: ' || title || '. Ingredients: ' || array_to_string(ingredients, ', ')
                                   || '. Is this recipe free of meat, poultry and fish (eggs are allowed)?'),
  non_veg     = ai.if(prompt => 'Recipe: ' || title || '. Ingredients: ' || array_to_string(ingredients, ', ')
                                   || '. Is this recipe free of all meat and fish other than chicken (chicken and eggs are allowed)?'),
  gluten_free = ai.if(prompt => 'Recipe: ' || title || '. Ingredients: ' || array_to_string(ingredients, ', ')
                                   || '. Is this recipe gluten-free as written (no wheat, atta, maida, semolina, regular pasta, bread, tortillas, regular soy sauce or hing, which is usually mixed with wheat flour)?'),
  dairy_free  = ai.if(prompt => 'Recipe: ' || title || '. Ingredients: ' || array_to_string(ingredients, ', ')
                                   || '. Is this recipe dairy-free (no milk, butter, ghee, paneer, cheese, cream or yogurt)?'),
  nut_free    = ai.if(prompt => 'Recipe: ' || title || '. Ingredients: ' || array_to_string(ingredients, ', ')
                                   || '. Is this recipe free of peanuts and tree nuts (including pesto made with nuts)?'),
  tagged_by   = 'gemini'
WHERE tagged_by IS NULL;

-- The app adds one more step: if an ingredient clearly rules a diet out (chicken, eggs,
-- hing for gluten), that label is set to false whatever the model said.

-- --- B) Check the AI against the hand-checked labels on the starter recipes -------
-- A quick "evaluation": where does the model disagree with a person? Gluten-free is a good test,
-- because the model has to know that hing is usually mixed with wheat and that ragi and jowar are millets.
WITH checked AS (
    SELECT title, gluten_free AS hand_label,
           ai.if(prompt => 'Recipe: ' || title || '. Ingredients: ' || array_to_string(ingredients, ', ')
                           || '. Is this recipe gluten-free as written (no wheat, atta, maida, semolina, regular pasta, bread, tortillas, regular soy sauce or hing, which is usually mixed with wheat flour)?') AS ai_label
    FROM recipes
    WHERE source = 'starter'
)
SELECT title, hand_label, ai_label, hand_label = ai_label AS agrees
FROM checked
ORDER BY agrees, title;     -- disagreements first
