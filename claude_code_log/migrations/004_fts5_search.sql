-- Full-text search index for conversation content
-- Migration: 004
-- Description: Creates FTS5 virtual table for searching message content

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    session_id,
    role,
    text_content,
    tokenize='porter unicode61'
);
