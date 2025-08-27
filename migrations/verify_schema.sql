-- Verification script to check if the database schema was created properly
-- Run this script after the database initialization to verify everything is set up correctly

-- Check if all tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Check table structures
\d users
\d dcategories  
\d events
\d event_registrations
\d user_event_registrations

-- Check if indexes were created
SELECT indexname, tablename 
FROM pg_indexes 
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- Check if triggers exist
SELECT trigger_name, event_object_table, action_timing, event_manipulation
FROM information_schema.triggers
WHERE trigger_schema = 'public'
ORDER BY event_object_table, trigger_name;

-- Check if the view exists
SELECT table_name, table_type 
FROM information_schema.views 
WHERE table_schema = 'public';

-- Count records in events table (should have sample data)
SELECT COUNT(*) as event_count FROM events;

-- Show sample events
SELECT id, title, category, location, event_date, organizer 
FROM events 
ORDER BY event_date 
LIMIT 5;

-- Check user privileges
SELECT table_name, privilege_type 
FROM information_schema.table_privileges 
WHERE grantee = 'eventuser' 
  AND table_schema = 'public'
ORDER BY table_name, privilege_type;
