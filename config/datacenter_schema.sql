-- datacenter_schema.sql
-- Complete database schema for multi-camera datacenter monitoring system
-- Compatible with your existing codebase

USE dc_test;

-- Drop existing tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS processing_stats;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS camera_use_cases;
DROP TABLE IF EXISTS camera_health;
DROP TABLE IF EXISTS system_performance;
DROP TABLE IF EXISTS cameras;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS users;

-- Users table for authentication
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role ENUM('admin', 'operator', 'viewer') DEFAULT 'viewer',
    status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_status (status)
);

-- Projects table for multiple datacenters
CREATE TABLE projects (
    project_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(100) DEFAULT 'datacenter_monitoring',
    location VARCHAR(255),
    status ENUM('active', 'inactive', 'maintenance') DEFAULT 'active',
    metadata JSON DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_type (type)
);

-- Cameras table (enhanced for your multi-use case system)
CREATE TABLE cameras (
    camera_id VARCHAR(50) PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    stream_url VARCHAR(500) NOT NULL,
    location VARCHAR(255),
    primary_use_case VARCHAR(100) DEFAULT 'people_counting',
    zone_configuration JSON DEFAULT NULL,
    processing_rules JSON DEFAULT NULL,
    connection_status ENUM('connected', 'disconnected', 'error') DEFAULT 'disconnected',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'inactive', 'maintenance') DEFAULT 'active',
    metadata JSON DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    INDEX idx_project_id (project_id),
    INDEX idx_status (status),
    INDEX idx_connection_status (connection_status),
    INDEX idx_primary_use_case (primary_use_case)
);

-- Camera use cases table (for flexible multi-use case per camera)
CREATE TABLE camera_use_cases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    camera_id VARCHAR(50) NOT NULL,
    use_case VARCHAR(100) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    is_enabled BOOLEAN DEFAULT TRUE,
    configuration JSON DEFAULT NULL,
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
    UNIQUE KEY unique_camera_use_case (camera_id, use_case),
    INDEX idx_camera_id (camera_id),
    INDEX idx_use_case (use_case),
    INDEX idx_enabled (is_enabled)
);

-- Events table (main events storage - matches your existing code)
CREATE TABLE events (
    event_id VARCHAR(50) PRIMARY KEY,
    camera_id VARCHAR(50) NOT NULL,
    project_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    severity ENUM('info', 'warning', 'critical') DEFAULT 'info',
    detection_data JSON DEFAULT NULL,
    local_image_path VARCHAR(500),
    gcp_image_path VARCHAR(500),
    confidence_score DECIMAL(5,4),
    status ENUM('new', 'acknowledged', 'resolved') DEFAULT 'new',
    camera_name VARCHAR(255),
    processing_time_ms INT DEFAULT NULL,
    model_version VARCHAR(50) DEFAULT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    INDEX idx_camera_id (camera_id),
    INDEX idx_project_id (project_id),
    INDEX idx_event_type (event_type),
    INDEX idx_severity (severity),
    INDEX idx_status (status),
    INDEX idx_timestamp (timestamp),
    INDEX idx_camera_event_type (camera_id, event_type),
    INDEX idx_timestamp_type (timestamp, event_type)
);

-- Processing statistics table
CREATE TABLE processing_stats (
    stat_id INT AUTO_INCREMENT PRIMARY KEY,
    camera_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    frames_processed INT DEFAULT 0,
    total_detections INT DEFAULT 0,
    people_counting_events INT DEFAULT 0,
    ppe_detection_events INT DEFAULT 0,
    tailgating_events INT DEFAULT 0,
    intrusion_events INT DEFAULT 0,
    loitering_events INT DEFAULT 0,
    processing_time_ms BIGINT DEFAULT 0,
    fps_average DECIMAL(8,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
    INDEX idx_camera_id (camera_id),
    INDEX idx_timestamp (timestamp)
);

-- Camera health monitoring table
CREATE TABLE camera_health (
    health_id INT AUTO_INCREMENT PRIMARY KEY,
    camera_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    connection_status ENUM('connected', 'disconnected', 'error') NOT NULL,
    fps DECIMAL(5,2) DEFAULT 0.00,
    frames_processed INT DEFAULT 0,
    events_detected INT DEFAULT 0,
    cpu_usage DECIMAL(5,2) DEFAULT 0.00,
    memory_usage DECIMAL(5,2) DEFAULT 0.00,
    error_message TEXT DEFAULT NULL,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
    INDEX idx_camera_timestamp (camera_id, timestamp),
    INDEX idx_connection_status (connection_status)
);

-- System performance monitoring table
CREATE TABLE system_performance (
    performance_id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_cameras INT DEFAULT 0,
    active_cameras INT DEFAULT 0,
    total_fps DECIMAL(8,2) DEFAULT 0.00,
    total_events_per_minute INT DEFAULT 0,
    cpu_usage_percent DECIMAL(5,2) DEFAULT 0.00,
    memory_usage_percent DECIMAL(5,2) DEFAULT 0.00,
    disk_usage_percent DECIMAL(5,2) DEFAULT 0.00,
    gpu_usage_percent DECIMAL(5,2) DEFAULT 0.00,
    pending_uploads INT DEFAULT 0,
    INDEX idx_timestamp (timestamp)
);

-- Insert default admin user
INSERT INTO users (user_id, username, email, password_hash, full_name, role, status) 
VALUES (
    'admin-user-001',
    'admin',
    'admin@datacenter.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYW0.WaW7.0.tKS', -- password: admin123
    'System Administrator',
    'admin',
    'active'
);

-- Insert default project for your existing system
INSERT INTO projects (project_id, user_id, name, description, type, location, status)
VALUES (
    'flexible-multi-camera-project',
    'admin-user-001',
    'Main Datacenter Monitoring',
    'Production multi-camera system with flexible use cases per camera',
    'multi_camera_production',
    'Main Facility',
    'active'
);

-- Insert your existing cameras (based on your configuration)
INSERT INTO cameras (camera_id, project_id, name, stream_url, primary_use_case, status, metadata) 
VALUES 
(
    'cam1',
    'flexible-multi-camera-project',
    'main entrance',
    'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
    'people_counting',
    'active',
    JSON_OBJECT(
        'available_use_cases', JSON_ARRAY('people_counting', 'ppe_detection', 'tailgating', 'intrusion', 'loitering'),
        'enabled_use_cases', JSON_ARRAY('people_counting', 'ppe_detection', 'tailgating', 'intrusion', 'loitering')
    )
),
(
    'cam2',
    'flexible-multi-camera-project', 
    'reception',
    'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
    'people_counting',
    'active',
    JSON_OBJECT(
        'available_use_cases', JSON_ARRAY('people_counting', 'ppe_detection', 'tailgating', 'intrusion', 'loitering'),
        'enabled_use_cases', JSON_ARRAY('people_counting', 'ppe_detection', 'tailgating', 'intrusion', 'loitering')
    )
);

-- Insert camera use cases for flexible system
INSERT INTO camera_use_cases (camera_id, use_case, is_primary, is_enabled) VALUES
('cam1', 'people_counting', TRUE, TRUE),
('cam1', 'ppe_detection', FALSE, TRUE),
('cam1', 'tailgating', FALSE, TRUE),
('cam1', 'intrusion', FALSE, TRUE),
('cam1', 'loitering', FALSE, TRUE),
('cam2', 'people_counting', TRUE, TRUE),
('cam2', 'ppe_detection', FALSE, TRUE),
('cam2', 'tailgating', FALSE, TRUE),
('cam2', 'intrusion', FALSE, TRUE),
('cam2', 'loitering', FALSE, TRUE);

-- Insert initial system performance record
INSERT INTO system_performance (
    total_cameras, active_cameras, total_fps, total_events_per_minute,
    cpu_usage_percent, memory_usage_percent, disk_usage_percent, gpu_usage_percent
) VALUES (2, 2, 0.0, 0, 0.0, 0.0, 0.0, 0.0);

-- Create views for common queries
CREATE VIEW active_cameras_view AS
SELECT 
    c.camera_id,
    c.name,
    c.stream_url,
    c.primary_use_case,
    c.connection_status,
    c.last_seen,
    p.name as project_name,
    p.location,
    GROUP_CONCAT(cuc.use_case) as enabled_use_cases
FROM cameras c
JOIN projects p ON c.project_id = p.project_id
LEFT JOIN camera_use_cases cuc ON c.camera_id = cuc.camera_id AND cuc.is_enabled = TRUE
WHERE c.status = 'active'
GROUP BY c.camera_id;

CREATE VIEW recent_events_view AS
SELECT 
    e.event_id,
    e.camera_id,
    c.name as camera_name,
    e.event_type,
    e.severity,
    e.confidence_score,
    e.timestamp,
    e.status,
    p.name as project_name
FROM events e
JOIN cameras c ON e.camera_id = c.camera_id
JOIN projects p ON e.project_id = p.project_id
WHERE e.timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY e.timestamp DESC;

-- Verification queries
SELECT 'Database schema created successfully!' AS Status;
SELECT 'Tables created:' AS Info;
SELECT TABLE_NAME, TABLE_ROWS 
FROM information_schema.tables 
WHERE table_schema = 'dc_test' 
ORDER BY TABLE_NAME;



-- -- config/multi_camera_database_setup.sql (FIXED VERSION)
-- -- MySQL compatible schema for multi-camera system

-- USE dc_test;

-- -- Add columns to cameras table (MySQL compatible way)
-- SET @sql = (SELECT IF(
--     (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
--      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cameras' AND COLUMN_NAME='primary_use_case') > 0,
--     'SELECT "Column primary_use_case already exists"',
--     'ALTER TABLE cameras ADD COLUMN primary_use_case VARCHAR(100) DEFAULT ''people_counting'''
-- ));
-- PREPARE stmt FROM @sql;
-- EXECUTE stmt;
-- DEALLOCATE PREPARE stmt;

-- SET @sql = (SELECT IF(
--     (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
--      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cameras' AND COLUMN_NAME='zone_configuration') > 0,
--     'SELECT "Column zone_configuration already exists"',
--     'ALTER TABLE cameras ADD COLUMN zone_configuration JSON DEFAULT NULL'
-- ));
-- PREPARE stmt FROM @sql;
-- EXECUTE stmt;
-- DEALLOCATE PREPARE stmt;

-- SET @sql = (SELECT IF(
--     (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
--      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cameras' AND COLUMN_NAME='processing_rules') > 0,
--     'SELECT "Column processing_rules already exists"',
--     'ALTER TABLE cameras ADD COLUMN processing_rules JSON DEFAULT NULL'
-- ));
-- PREPARE stmt FROM @sql;
-- EXECUTE stmt;
-- DEALLOCATE PREPARE stmt;

-- SET @sql = (SELECT IF(
--     (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
--      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cameras' AND COLUMN_NAME='connection_status') > 0,
--     'SELECT "Column connection_status already exists"',
--     'ALTER TABLE cameras ADD COLUMN connection_status ENUM(''connected'', ''disconnected'', ''error'') DEFAULT ''disconnected'''
-- ));
-- PREPARE stmt FROM @sql;
-- EXECUTE stmt;
-- DEALLOCATE PREPARE stmt;

-- SET @sql = (SELECT IF(
--     (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
--      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cameras' AND COLUMN_NAME='last_seen') > 0,
--     'SELECT "Column last_seen already exists"',
--     'ALTER TABLE cameras ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'
-- ));
-- PREPARE stmt FROM @sql;
-- EXECUTE stmt;
-- DEALLOCATE PREPARE stmt;

-- -- Create camera_use_cases table
-- CREATE TABLE IF NOT EXISTS camera_use_cases (
--     id INT AUTO_INCREMENT PRIMARY KEY,
--     camera_id INT NOT NULL,
--     use_case VARCHAR(100) NOT NULL,
--     is_primary BOOLEAN DEFAULT FALSE,
--     configuration JSON DEFAULT NULL,
--     status ENUM('active', 'inactive') DEFAULT 'active',
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
--     FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
--     UNIQUE KEY unique_camera_use_case (camera_id, use_case)
-- );

-- -- Create camera_health table
-- CREATE TABLE IF NOT EXISTS camera_health (
--     health_id INT AUTO_INCREMENT PRIMARY KEY,
--     camera_id INT NOT NULL,
--     timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     connection_status ENUM('connected', 'disconnected', 'error') NOT NULL,
--     fps DECIMAL(5,2) DEFAULT 0.00,
--     frames_processed INT DEFAULT 0,
--     events_detected INT DEFAULT 0,
--     cpu_usage DECIMAL(5,2) DEFAULT 0.00,
--     memory_usage DECIMAL(5,2) DEFAULT 0.00,
--     error_message TEXT DEFAULT NULL,
--     FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
--     INDEX idx_camera_timestamp (camera_id, timestamp)
-- );

-- -- Add columns to events table
-- SET @sql = (SELECT IF(
--     (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
--      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='events' AND COLUMN_NAME='camera_name') > 0,
--     'SELECT "Column camera_name already exists"',
--     'ALTER TABLE events ADD COLUMN camera_name VARCHAR(255) DEFAULT NULL'
-- ));
-- PREPARE stmt FROM @sql;
-- EXECUTE stmt;
-- DEALLOCATE PREPARE stmt;

-- SET @sql = (SELECT IF(
--     (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
--      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='events' AND COLUMN_NAME='processing_time_ms') > 0,
--     'SELECT "Column processing_time_ms already exists"',
--     'ALTER TABLE events ADD COLUMN processing_time_ms INT DEFAULT NULL'
-- ));
-- PREPARE stmt FROM @sql;
-- EXECUTE stmt;
-- DEALLOCATE PREPARE stmt;

-- SET @sql = (SELECT IF(
--     (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
--      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='events' AND COLUMN_NAME='model_version') > 0,
--     'SELECT "Column model_version already exists"',
--     'ALTER TABLE events ADD COLUMN model_version VARCHAR(50) DEFAULT NULL'
-- ));
-- PREPARE stmt FROM @sql;
-- EXECUTE stmt;
-- DEALLOCATE PREPARE stmt;

-- -- Create system_performance table
-- CREATE TABLE IF NOT EXISTS system_performance (
--     performance_id INT AUTO_INCREMENT PRIMARY KEY,
--     timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     total_cameras INT DEFAULT 0,
--     active_cameras INT DEFAULT 0,
--     total_fps DECIMAL(8,2) DEFAULT 0.00,
--     total_events_per_minute INT DEFAULT 0,
--     cpu_usage_percent DECIMAL(5,2) DEFAULT 0.00,
--     memory_usage_percent DECIMAL(5,2) DEFAULT 0.00,
--     disk_usage_percent DECIMAL(5,2) DEFAULT 0.00,
--     gpu_usage_percent DECIMAL(5,2) DEFAULT 0.00,
--     pending_uploads INT DEFAULT 0,
--     INDEX idx_timestamp (timestamp)
-- );

-- -- Update existing project for multi-camera
-- INSERT IGNORE INTO projects (project_id, user_id, name, description, type, location, status)
-- VALUES 
-- ('multi-cam-project-001', 'admin-user', 'Multi-Camera Monitoring System', 
--  'Production multi-camera system with specialized use cases per camera', 'multi_camera_production', 'Main Facility', 'active');

-- -- Insert initial system performance record
-- INSERT IGNORE INTO system_performance (
--     total_cameras, active_cameras, total_fps, total_events_per_minute,
--     cpu_usage_percent, memory_usage_percent, disk_usage_percent, gpu_usage_percent
-- ) VALUES (0, 0, 0.0, 0, 0.0, 0.0, 0.0, 0.0);

-- -- Verify the setup
-- SELECT 'Multi-Camera Database Setup Completed!' AS Status;

-- -- Show current camera table structure
-- SELECT 'Camera table structure updated successfully!' AS Info;
-- DESCRIBE cameras;

-- SELECT 'Database ready for multi-camera system!' AS Ready;