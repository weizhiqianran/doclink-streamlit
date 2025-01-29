-- drop_all_tables.sql

-- Disable foreign key checks to avoid dependency issues
SET session_replication_role = 'replica';

-- Drop all tables in the public schema
DO $$ 
DECLARE 
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END $$;

-- Re-enable foreign key checks
SET session_replication_role = 'origin';

-- Optionally, you can also drop sequences if you have any
DO $$ 
DECLARE 
    r RECORD;
BEGIN
    FOR r IN (SELECT sequencename FROM pg_sequences WHERE schemaname = 'public') LOOP
        EXECUTE 'DROP SEQUENCE IF EXISTS ' || quote_ident(r.sequencename) || ' CASCADE';
    END LOOP;
END $$;

-- If you want to reset the primary key sequences for all tables, you can add this:
-- (Note: Only necessary if you've inserted data and want to reset auto-incrementing ids)
DO $$ 
DECLARE 
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'ALTER TABLE ' || quote_ident(r.tablename) || ' ALTER COLUMN id RESTART WITH 1;';
    END LOOP;
END $$;