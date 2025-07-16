-- Vexor Search Engine Database Schema
-- This file contains the complete database schema for the Vexor search engine
-- including tables for file metadata, content indexing, and search analytics
-- 
-- Author: AI Assistant
-- Version: 2.1.0
-- Database: PostgreSQL 14+
-- License: MIT

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create custom types
CREATE TYPE file_status AS ENUM ('pending', 'indexed', 'failed', 'deleted');
CREATE TYPE search_type AS ENUM ('semantic', 'keyword', 'hybrid');

-- Files table to store file metadata
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_path TEXT NOT NULL UNIQUE,
    filename VARCHAR(255) NOT NULL,
    file_extension VARCHAR(50),
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    content_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accessed_at TIMESTAMP WITH TIME ZONE,
    indexed_at TIMESTAMP WITH TIME ZONE,
    status file_status DEFAULT 'pending',
    error_message TEXT,
    parent_directory TEXT,
    metadata JSONB,
    
    -- Indexes for performance
    CONSTRAINT files_file_size_positive CHECK (file_size >= 0)
);

-- Content chunks table for storing text chunks with embeddings
CREATE TABLE content_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    chunk_hash VARCHAR(64) NOT NULL,
    start_position INTEGER,
    end_position INTEGER,
    embedding_vector FLOAT4[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure chunk index is unique per file
    UNIQUE(file_id, chunk_index),
    
    -- Constraints
    CONSTRAINT content_chunks_chunk_index_positive CHECK (chunk_index >= 0),
    CONSTRAINT content_chunks_content_length_positive CHECK (content_length > 0),
    CONSTRAINT content_chunks_positions_valid CHECK (
        start_position IS NULL OR end_position IS NULL OR start_position <= end_position
    )
);

-- Search queries table for analytics and caching
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64) NOT NULL,
    search_type search_type NOT NULL,
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    results_count INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB,
    
    -- Index for performance
    CONSTRAINT search_queries_results_count_positive CHECK (results_count >= 0),
    CONSTRAINT search_queries_response_time_positive CHECK (response_time_ms IS NULL OR response_time_ms >= 0)
);

-- Search results table for caching and analytics
CREATE TABLE search_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES content_chunks(id) ON DELETE CASCADE,
    relevance_score FLOAT NOT NULL,
    rank_position INTEGER NOT NULL,
    snippet TEXT,
    highlight_positions INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure unique ranking per query
    UNIQUE(query_id, rank_position),
    
    -- Constraints
    CONSTRAINT search_results_relevance_score_valid CHECK (relevance_score >= 0 AND relevance_score <= 1),
    CONSTRAINT search_results_rank_position_positive CHECK (rank_position > 0)
);

-- Index configurations table
CREATE TABLE index_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    embedding_model VARCHAR(100) NOT NULL,
    chunk_size INTEGER NOT NULL DEFAULT 1000,
    chunk_overlap INTEGER NOT NULL DEFAULT 200,
    batch_size INTEGER NOT NULL DEFAULT 100,
    file_size_limit BIGINT NOT NULL DEFAULT 10485760, -- 10MB
    supported_extensions TEXT[] NOT NULL,
    exclude_patterns TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    config_data JSONB,
    
    -- Constraints
    CONSTRAINT index_config_chunk_size_positive CHECK (chunk_size > 0),
    CONSTRAINT index_config_chunk_overlap_valid CHECK (chunk_overlap >= 0 AND chunk_overlap < chunk_size),
    CONSTRAINT index_config_batch_size_positive CHECK (batch_size > 0),
    CONSTRAINT index_config_file_size_limit_positive CHECK (file_size_limit > 0)
);

-- Indexing jobs table for tracking background processing
CREATE TABLE indexing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_name VARCHAR(100) NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    target_path TEXT NOT NULL,
    config_id UUID REFERENCES index_configurations(id),
    status VARCHAR(20) DEFAULT 'pending',
    progress_percentage INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    files_total INTEGER,
    files_failed INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_by VARCHAR(100),
    metadata JSONB,
    
    -- Constraints
    CONSTRAINT indexing_jobs_progress_valid CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    CONSTRAINT indexing_jobs_files_processed_valid CHECK (files_processed >= 0),
    CONSTRAINT indexing_jobs_files_failed_valid CHECK (files_failed >= 0),
    CONSTRAINT indexing_jobs_status_valid CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);

-- User preferences table
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL UNIQUE,
    preferred_file_types TEXT[],
    search_history_limit INTEGER DEFAULT 100,
    default_search_type search_type DEFAULT 'hybrid',
    enable_search_suggestions BOOLEAN DEFAULT TRUE,
    enable_search_analytics BOOLEAN DEFAULT TRUE,
    theme_preference VARCHAR(20) DEFAULT 'auto',
    language_preference VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    preferences_data JSONB,
    
    -- Constraints
    CONSTRAINT user_preferences_search_history_limit_positive CHECK (search_history_limit > 0),
    CONSTRAINT user_preferences_theme_valid CHECK (theme_preference IN ('light', 'dark', 'auto'))
);

-- System metrics table for monitoring
CREATE TABLE system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_unit VARCHAR(20),
    metric_tags JSONB,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Index for time-based queries
    INDEX idx_system_metrics_recorded_at ON system_metrics(recorded_at)
);

-- Create indexes for optimal performance
CREATE INDEX idx_files_status ON files(status);
CREATE INDEX idx_files_file_extension ON files(file_extension);
CREATE INDEX idx_files_modified_at ON files(modified_at);
CREATE INDEX idx_files_indexed_at ON files(indexed_at);
CREATE INDEX idx_files_file_path_trgm ON files USING gin(file_path gin_trgm_ops);
CREATE INDEX idx_files_filename_trgm ON files USING gin(filename gin_trgm_ops);

CREATE INDEX idx_content_chunks_file_id ON content_chunks(file_id);
CREATE INDEX idx_content_chunks_chunk_hash ON content_chunks(chunk_hash);
CREATE INDEX idx_content_chunks_content_trgm ON content_chunks USING gin(content gin_trgm_ops);

CREATE INDEX idx_search_queries_query_hash ON search_queries(query_hash);
CREATE INDEX idx_search_queries_created_at ON search_queries(created_at);
CREATE INDEX idx_search_queries_user_id ON search_queries(user_id);
CREATE INDEX idx_search_queries_query_text_trgm ON search_queries USING gin(query_text gin_trgm_ops);

CREATE INDEX idx_search_results_query_id ON search_results(query_id);
CREATE INDEX idx_search_results_file_id ON search_results(file_id);
CREATE INDEX idx_search_results_relevance_score ON search_results(relevance_score DESC);

CREATE INDEX idx_indexing_jobs_status ON indexing_jobs(status);
CREATE INDEX idx_indexing_jobs_started_at ON indexing_jobs(started_at);

-- Insert default configuration
INSERT INTO index_configurations (
    name, 
    description, 
    embedding_model, 
    chunk_size, 
    chunk_overlap, 
    batch_size,
    file_size_limit,
    supported_extensions,
    exclude_patterns,
    config_data
) VALUES (
    'default_config',
    'Default indexing configuration for Vexor search engine',
    'all-MiniLM-L6-v2',
    1000,
    200,
    100,
    10485760,
    ARRAY['.txt', '.md', '.html', '.py', '.js', '.json', '.pdf', '.docx'],
    ARRAY['.git/**', 'node_modules/**', '__pycache__/**', '*.pyc'],
    '{
        "preprocessing": {
            "normalize_whitespace": true,
            "remove_duplicates": true,
            "extract_metadata": true
        },
        "embedding": {
            "model_name": "all-MiniLM-L6-v2",
            "dimension": 384,
            "normalize": true
        }
    }'::jsonb
);

-- Useful queries and views

-- View for file statistics
CREATE VIEW file_statistics AS
SELECT 
    COUNT(*) as total_files,
    COUNT(*) FILTER (WHERE status = 'indexed') as indexed_files,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_files,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_files,
    SUM(file_size) as total_size,
    AVG(file_size) as average_size,
    COUNT(DISTINCT file_extension) as unique_extensions,
    MAX(modified_at) as latest_modification,
    MIN(created_at) as earliest_creation
FROM files;

-- View for search analytics
CREATE VIEW search_analytics AS
SELECT 
    DATE_TRUNC('day', created_at) as search_date,
    COUNT(*) as total_searches,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(response_time_ms) as avg_response_time,
    AVG(results_count) as avg_results_count,
    search_type,
    COUNT(*) FILTER (WHERE results_count = 0) as zero_result_searches
FROM search_queries
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY search_date, search_type
ORDER BY search_date DESC;

-- Function to calculate file indexing progress
CREATE OR REPLACE FUNCTION get_indexing_progress()
RETURNS TABLE(
    total_files BIGINT,
    indexed_files BIGINT,
    progress_percentage NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_files,
        COUNT(*) FILTER (WHERE status = 'indexed') as indexed_files,
        ROUND(
            (COUNT(*) FILTER (WHERE status = 'indexed')::NUMERIC / 
             NULLIF(COUNT(*), 0) * 100), 2
        ) as progress_percentage
    FROM files;
END;
$$ LANGUAGE plpgsql;

-- Function to get popular search terms
CREATE OR REPLACE FUNCTION get_popular_search_terms(
    days_back INTEGER DEFAULT 7,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE(
    query_text TEXT,
    search_count BIGINT,
    avg_results NUMERIC,
    last_searched TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sq.query_text,
        COUNT(*) as search_count,
        ROUND(AVG(sq.results_count), 2) as avg_results,
        MAX(sq.created_at) as last_searched
    FROM search_queries sq
    WHERE sq.created_at >= NOW() - (days_back || ' days')::INTERVAL
    GROUP BY sq.query_text
    HAVING COUNT(*) > 1
    ORDER BY search_count DESC, last_searched DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup old search queries
CREATE OR REPLACE FUNCTION cleanup_old_search_queries(
    retention_days INTEGER DEFAULT 90
)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM search_queries 
    WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Log the cleanup operation
    INSERT INTO system_metrics (metric_name, metric_value, metric_unit, metric_tags)
    VALUES (
        'cleanup_search_queries',
        deleted_count,
        'count',
        json_build_object('retention_days', retention_days)::jsonb
    );
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update file modified timestamp
CREATE OR REPLACE FUNCTION update_file_modified_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER trigger_update_user_preferences_timestamp
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_file_modified_timestamp();

CREATE TRIGGER trigger_update_index_config_timestamp
    BEFORE UPDATE ON index_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_file_modified_timestamp();

-- Create a procedure for full-text search
CREATE OR REPLACE FUNCTION search_content(
    search_query TEXT,
    file_types TEXT[] DEFAULT NULL,
    limit_results INTEGER DEFAULT 10,
    offset_results INTEGER DEFAULT 0
)
RETURNS TABLE(
    file_id UUID,
    file_path TEXT,
    filename VARCHAR(255),
    chunk_content TEXT,
    relevance_score REAL,
    snippet TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        f.id as file_id,
        f.file_path,
        f.filename,
        cc.content as chunk_content,
        ts_rank(to_tsvector('english', cc.content), plainto_tsquery('english', search_query)) as relevance_score,
        ts_headline('english', cc.content, plainto_tsquery('english', search_query), 
                   'MaxWords=30, MinWords=10, ShortWord=3, HighlightAll=false') as snippet
    FROM files f
    JOIN content_chunks cc ON f.id = cc.file_id
    WHERE 
        to_tsvector('english', cc.content) @@ plainto_tsquery('english', search_query)
        AND f.status = 'indexed'
        AND (file_types IS NULL OR f.file_extension = ANY(file_types))
    ORDER BY relevance_score DESC
    LIMIT limit_results
    OFFSET offset_results;
END;
$$ LANGUAGE plpgsql;

-- Create materialized view for file type statistics
CREATE MATERIALIZED VIEW file_type_statistics AS
SELECT 
    COALESCE(file_extension, 'no_extension') as extension,
    COUNT(*) as file_count,
    SUM(file_size) as total_size,
    AVG(file_size) as average_size,
    MIN(file_size) as min_size,
    MAX(file_size) as max_size,
    COUNT(*) FILTER (WHERE status = 'indexed') as indexed_count,
    ROUND(
        (COUNT(*) FILTER (WHERE status = 'indexed')::NUMERIC / COUNT(*) * 100), 2
    ) as indexed_percentage
FROM files
GROUP BY file_extension
ORDER BY file_count DESC;

-- Create index on materialized view
CREATE UNIQUE INDEX idx_file_type_stats_extension ON file_type_statistics(extension);

-- Refresh the materialized view (should be done periodically)
REFRESH MATERIALIZED VIEW file_type_statistics;

-- Grant permissions (adjust based on your user requirements)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Sample data for testing (uncomment to use)
/*
INSERT INTO files (file_path, filename, file_extension, file_size, mime_type, content_hash, modified_at, status) VALUES
('test/sample.txt', 'sample.txt', '.txt', 1024, 'text/plain', 'abc123', NOW(), 'indexed'),
('test/document.pdf', 'document.pdf', '.pdf', 5120, 'application/pdf', 'def456', NOW(), 'indexed'),
('src/main.py', 'main.py', '.py', 2048, 'text/x-python', 'ghi789', NOW(), 'indexed');

INSERT INTO content_chunks (file_id, chunk_index, content, content_length, chunk_hash, start_position, end_position) 
SELECT 
    id, 
    0, 
    'This is sample content for testing the search functionality.',
    50,
    'chunk_' || substr(content_hash, 1, 8),
    0,
    50
FROM files WHERE status = 'indexed';
*/

-- Comments for maintenance
-- Run this query periodically to refresh statistics:
-- REFRESH MATERIALIZED VIEW file_type_statistics;

-- Run this to cleanup old search queries (adjust retention as needed):
-- SELECT cleanup_old_search_queries(90);

-- Monitor indexing progress:
-- SELECT * FROM get_indexing_progress();

-- Get popular search terms:
-- SELECT * FROM get_popular_search_terms(30, 20); 