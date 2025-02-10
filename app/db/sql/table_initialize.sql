CREATE TABLE IF NOT EXISTS user_info (
    user_id UUID PRIMARY KEY,
    google_id VARCHAR(255) NOT NULL,
    user_name VARCHAR(50) NOT NULL,
    user_surname VARCHAR(50) NOT NULL,
    user_email VARCHAR(100) UNIQUE NOT NULL,
    user_type VARCHAR(20) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    picture_url VARCHAR(255),
    user_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_feedback (
    feedback_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    feedback_type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    screenshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id)
);

CREATE TABLE IF NOT EXISTS domain_info (
    user_id UUID NOT NULL,
    domain_id UUID PRIMARY KEY,
    domain_name VARCHAR(30) NOT NULL,
    domain_type INTEGER,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id)
);

CREATE TABLE IF NOT EXISTS file_info (
    user_id UUID NOT NULL,
    domain_id UUID NOT NULL,
    file_id UUID PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_modified_date DATE,
    file_upload_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id),
    FOREIGN KEY (domain_id) REFERENCES domain_info(domain_id)
);

CREATE TABLE IF NOT EXISTS file_content (
    content_id SERIAL PRIMARY KEY,
    file_id UUID NOT NULL,
    sentence TEXT NOT NULL,
    is_header BOOLEAN DEFAULT FALSE,
    is_table BOOLEAN DEFAULT FALSE,
    page_number INTEGER,
    embedding BYTEA,
    FOREIGN KEY (file_id) REFERENCES file_info(file_id)
);

CREATE TABLE IF NOT EXISTS session_info (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    session_id UUID NOT NULL,
    question_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_enterance INTEGER DEFAULT 0,
    last_enterance TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id)
);

CREATE TABLE IF NOT EXISTS default_content (
    content_id SERIAL PRIMARY KEY,
    sentence TEXT NOT NULL,
    is_header BOOLEAN DEFAULT FALSE,
    is_table BOOLEAN DEFAULT FALSE,
    page_number INTEGER,
    embedding BYTEA
);

CREATE TABLE IF NOT EXISTS user_rating (
    rating_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    rating INTEGER NOT NULL,
    user_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id)
);