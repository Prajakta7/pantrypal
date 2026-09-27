-- =============================================================================
-- 7. (Optional) Label recipes with TypeSafe AI's Jev model, in fast batches
--
-- Adapted from the Google Codelab "Using TypeSafe AI's Jev model with AlloyDB AI
-- Functions for High-Speed AI Queries" (code samples licensed Apache 2.0):
-- https://codelabs.developers.google.com/alloydb-ai-jev
--
-- Before running: scripts/03_setup_jev_secret.sh (stores your TypeSafe AI key in
-- Secret Manager), and your instance needs outbound internet access
-- (--outbound-public-ip) to reach api.typesafe.ai.
-- Replace <YOUR_PROJECT_ID> below, then run this file in AlloyDB Studio (db: pantrypal).
-- =============================================================================

-- Custom Model Endpoint Management transforms need synchronous calls
SET google_ml_integration.enable_async_operation = 'off';

-- Tell AlloyDB where the API key lives
CALL google_ml.create_sm_secret(
    secret_id   => 'jev_api_key',
    secret_path => 'projects/<YOUR_PROJECT_ID>/secrets/typesafe-jev-api-key/versions/latest'
);

-- --- Transform functions: PostgreSQL ai.* calls <-> Jev's REST format --------

-- Single prompt -> Jev request (noul = yes/no, choice = pick a label)
CREATE OR REPLACE FUNCTION public.jev_model_input_transform(
    model_id VARCHAR(100), input_text TEXT, generation_config JSON, system_instruction TEXT
) RETURNS JSON LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    full_instruction TEXT;
    enum_json JSON;
    criteria_obj JSONB := '{}'::JSONB;
    elem TEXT;
    q_obj JSON;
BEGIN
    IF system_instruction IS NOT NULL AND length(trim(system_instruction)) > 0 THEN
        full_instruction := system_instruction || E'\n\n' || input_text;
    ELSE
        full_instruction := input_text;
    END IF;
    enum_json := COALESCE(generation_config->'generationConfig'->'responseSchema'->'enum',
                          generation_config->'responseSchema'->'enum');
    IF enum_json IS NOT NULL AND json_typeof(enum_json) = 'array' THEN
        FOR elem IN SELECT json_array_elements_text(enum_json) LOOP
            criteria_obj := criteria_obj || jsonb_build_object(elem, 'Category: ' || elem);
        END LOOP;
        q_obj := json_build_object('type', 'choice', 'instructions', full_instruction, 'criteria', criteria_obj::JSON);
    ELSE
        q_obj := json_build_object('type', 'noul', 'instructions', full_instruction);
    END IF;
    RETURN json_build_object(
        'model', 'jev-latest',
        'state', COALESCE(generation_config->>'state', 'Evaluate the question accurately based on the provided text.'),
        'questions', json_build_object('q_1', q_obj));
END;
$$;

-- Jev response -> text ('true'/'false' or the chosen label)
CREATE OR REPLACE FUNCTION public.jev_model_output_transform(
    model_id VARCHAR(100), response_json JSON
) RETURNS TEXT LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    q_ans JSON := response_json->'answers'->'q_1';
    ans_type TEXT := q_ans->>'type';
BEGIN
    IF ans_type = 'choice' THEN
        RETURN q_ans->>'choice';
    ELSIF ans_type = 'noul' THEN
        RETURN CASE WHEN (q_ans->>'noul')::FLOAT >= 0.50 THEN 'true' ELSE 'false' END;
    ELSE
        RAISE EXCEPTION 'Unexpected Jev response payload: %', response_json::TEXT;
    END IF;
END;
$$;

-- Array of prompts -> ONE Jev request with questions q_1..q_N (batching)
CREATE OR REPLACE FUNCTION public.jev_model_batch_input_transform(
    model_id VARCHAR(100), prompts TEXT[], generation_config JSON, system_instructions JSON
) RETURNS JSON LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    questions_obj JSONB := '{}'::JSONB;
    enum_json JSON;
    criteria_obj JSONB := '{}'::JSONB;
    elem TEXT;
    is_choice BOOLEAN := FALSE;
    i INT;
BEGIN
    enum_json := COALESCE(
        generation_config->'generationConfig'->'responseSchema'->'items'->'enum',
        generation_config->'generationConfig'->'responseSchema'->'enum',
        generation_config->'responseSchema'->'items'->'enum',
        generation_config->'responseSchema'->'enum');
    IF enum_json IS NOT NULL AND json_typeof(enum_json) = 'array' THEN
        IF NOT (enum_json::JSONB = '["true", "false"]'::JSONB OR enum_json::JSONB = '["false", "true"]'::JSONB) THEN
            is_choice := TRUE;
            FOR elem IN SELECT json_array_elements_text(enum_json) LOOP
                criteria_obj := criteria_obj || jsonb_build_object(elem, 'Category: ' || elem);
            END LOOP;
        END IF;
    END IF;
    FOR i IN 1 .. COALESCE(array_length(prompts, 1), 0) LOOP
        IF is_choice THEN
            questions_obj := questions_obj || jsonb_build_object('q_' || i::TEXT,
                jsonb_build_object('type', 'choice', 'instructions', prompts[i], 'criteria', criteria_obj));
        ELSE
            questions_obj := questions_obj || jsonb_build_object('q_' || i::TEXT,
                jsonb_build_object('type', 'noul', 'instructions', prompts[i]));
        END IF;
    END LOOP;
    RETURN json_build_object(
        'model', 'jev-latest',
        'state', COALESCE(generation_config->>'state', 'Evaluate each question independently based on the record data.'),
        'questions', questions_obj::JSON);
END;
$$;

-- Batch response -> answers in q_1..q_N order
CREATE OR REPLACE FUNCTION public.jev_model_batch_output_transform(
    model_id VARCHAR(100), response JSON
) RETURNS TEXT[] LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    results TEXT[] := ARRAY[]::TEXT[];
    answers JSON := response->'answers';
    i INT := 1;
    q_ans JSON;
BEGIN
    LOOP
        q_ans := answers->('q_' || i::TEXT);
        EXIT WHEN q_ans IS NULL;
        IF q_ans->>'type' = 'choice' THEN
            results := array_append(results, q_ans->>'choice');
        ELSE
            results := array_append(results, CASE WHEN (q_ans->>'noul')::FLOAT >= 0.50 THEN 'true' ELSE 'false' END);
        END IF;
        i := i + 1;
    END LOOP;
    RETURN results;
END;
$$;

-- --- Register the models ------------------------------------------------------

-- jev-model: used by ai.if to label recipes (batched: one request per 25 recipes)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM google_ml.model_info_view WHERE model_id = 'jev-model') THEN
        CALL google_ml.drop_model('jev-model');
    END IF;
END $$;

CALL google_ml.create_model(
    model_id                     => 'jev-model',
    model_request_url            => 'https://api.typesafe.ai/v1/systemone',
    model_provider               => 'custom',
    model_type                   => 'llm',
    model_qualified_name         => 'jev-latest',
    model_auth_type              => 'secret_manager',
    model_auth_id                => 'jev_api_key',
    model_in_transform_fn        => 'jev_model_input_transform',
    model_out_transform_fn       => 'jev_model_output_transform',
    model_batch_in_transform_fn  => 'jev_model_batch_input_transform',
    model_batch_out_transform_fn => 'jev_model_batch_output_transform'
);

SELECT model_id, model_type, model_provider FROM google_ml.model_info_view
WHERE model_id = 'jev-model';   -- expect 1 row

-- --- Batched labeling: one Jev request answers 25 recipes at once ----------------
-- (The same pattern as the codelab: array of prompts in, array of answers out.)
-- Re-labels every recipe so you can compare Jev with the hand-written starter labels.
SET google_ml_integration.enable_async_operation = 'off';

CREATE TEMP TABLE jev_labels AS
WITH numbered AS (
    SELECT recipe_id,
           'Recipe: ' || title || '. Ingredients: ' || array_to_string(ingredients, ', ') AS facts,
           (row_number() OVER (ORDER BY recipe_id) - 1) / 25 AS batch_id
    FROM recipes
),
batched AS (
    SELECT array_agg(recipe_id ORDER BY recipe_id) AS ids,
           ai.if(prompts => array_agg(facts || ' Question: Is this recipe vegetarian in the Indian sense (no meat, poultry, fish or eggs)?' ORDER BY recipe_id),
                 model_id => 'jev-model') AS veg,
           ai.if(prompts => array_agg(facts || ' Question: Is this recipe free of meat, poultry and fish (eggs are allowed)?' ORDER BY recipe_id),
                 model_id => 'jev-model') AS egg
    FROM numbered GROUP BY batch_id
)
SELECT u.recipe_id, u.veg, u.egg
FROM batched b CROSS JOIN LATERAL unnest(b.ids, b.veg, b.egg) AS u(recipe_id, veg, egg);

-- Where does Jev disagree with the hand-written labels?
SELECT r.title, r.vegetarian AS hand_veg, j.veg AS jev_veg, r.eggetarian AS hand_egg, j.egg AS jev_egg
FROM recipes r JOIN jev_labels j USING (recipe_id)
ORDER BY (r.vegetarian IS DISTINCT FROM j.veg) OR (r.eggetarian IS DISTINCT FROM j.egg) DESC, r.title;

-- New recipes you add in the app are labeled with Jev automatically once it's registered.
