-- =============================================================================
-- 3. Auto embeddings for recipes
-- AlloyDB embeds every recipe and keeps embeddings in sync as recipes are added
-- or edited (transactional refresh), so recipe search understands meaning:
-- "something warm and cozy" finds soups, "high protein breakfast" finds eggs.
-- =============================================================================
CALL ai.initialize_embeddings(
    model_id                 => 'text-embedding-005',
    table_name               => 'recipes',
    content_column           => 'search_text',
    embedding_column         => 'embedding',
    batch_size               => 50,
    incremental_refresh_mode => 'transactional'
);

SELECT table_name, percent_progress, status, rows_processed FROM ai.embedding_progress_view;

-- Try it: recipes closest in meaning to a craving
SELECT title, minutes
FROM recipes
ORDER BY embedding <=> ai.embedding('text-embedding-005', 'something warm and comforting for a rainy day')::vector
LIMIT 5;
