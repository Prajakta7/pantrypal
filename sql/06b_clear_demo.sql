-- Remove the demo pantry (same as the "Clear" button in the app). Your own items are kept.
DELETE FROM pantry_items WHERE source = 'demo';
