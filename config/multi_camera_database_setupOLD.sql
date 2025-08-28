-- config/multi_camera_database_setup.sql
-- Extended database schema for multi-camera system

USE dc_test;

-- Update cameras table to support multi-camera configurations
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS primary_use_case VARCHAR(100) DEFAULT 'people_counting';
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS zone_configuration JSON DEFAULT NULL;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS processing_rules JSON DEFAULT NULL;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS connection_status ENUM('connected', 'disconnected', 'error') DEFAULT 'disconnected';
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- Create camera_use_cases table for tracking which use cases are assigned to which cameras
CREATE TABLE IF NOT EXISTS camera_use_cases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    camera_id INT NOT NULL,
    use_case VARCHAR(100) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    configuration JSON DEFAULT NULL,
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
    UNIQUE KEY unique_camera_use_case (camera_id, use_case)
);

-- Create camera_health table for monitoring camera status
CREATE TABLE IF NOT EXISTS camera_health (
    health_id INT AUTO_INCREMENT PRIMARY KEY,
    camera_id INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    connection_status ENUM('connected', 'disconnected', 'error') NOT NULL,
    fps DECIMAL(5,2) DEFAULT 0.00,
    frames_processed INT DEFAULT 0,
    events_detected INT DEFAULT 0,
    cpu_usage DECIMAL(5,2) DEFAULT 0.00,
    memory_usage DECIMAL(5,2) DEFAULT 0.00,
    error_message TEXT DEFAULT NULL,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE,
    INDEX idx_camera_timestamp (camera_id, timestamp)
);

-- Update events table to include more multi-camera specific fields
ALTER TABLE events ADD COLUMN IF NOT EXISTS camera_name VARCHAR(255) DEFAULT NULL;
ALTER TABLE events ADD COLUMN IF NOT EXISTS processing_time_ms INT DEFAULT NULL;
ALTER TABLE events ADD COLUMN IF NOT EXISTS model_version VARCHAR(50) DEFAULT NULL;

-- Create system_performance table for overall system monitoring
CREATE TABLE IF NOT EXISTS system_performance (
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

-- Insert sample multi-camera configurations
INSERT IGNORE INTO projects (project_id, user_id, name, description, type, location, status)
VALUES 
('multi-cam-project-001', 'admin-user', 'Multi-Camera Monitoring System', 
 'Production multi-camera system with specialized use cases per camera', 'multi_camera_production', 'Main Facility', 'active');

-- Sample camera configurations for multi-camera setup
INSERT IGNORE INTO cameras (project_id, name, stream_url, camera_type, primary_use_case, status, metadata, zone_configuration, processing_rules)
VALUES 
-- Camera 1: People Counting at Main Entrance
('multi-cam-project-001', 'Main Entrance - People Counter', 'rtsp://admin:password@192.168.29.213:554/ch0_0.264', 
 'people_counting', 'people_counting', 'active',
 JSON_OBJECT(
    'location', 'Main Entrance',
    'description', 'Primary entrance people counting',
    'resolution', '1920x1080',
    'fps', 25
 ),
 JSON_OBJECT(
    'counting', JSON_ARRAY(
        JSON_OBJECT(
            'zone_id', 1,
            'name', 'Entry Count Zone',
            'coordinates', JSON_ARRAY(JSON_ARRAY(200, 200), JSON_ARRAY(800, 200), JSON_ARRAY(800, 600), JSON_ARRAY(200, 600))
        )
    )
 ),
 JSON_OBJECT('count_threshold', 0, 'confidence_threshold', 0.3)
),

-- Camera 2: PPE Detection in Work Area
('multi-cam-project-001', 'Work Area - PPE Monitor', 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
 'ppe_detection', 'ppe_detection', 'active',
 JSON_OBJECT(
    'location', 'Work Area',
    'description', 'PPE compliance monitoring in manufacturing area',
    'resolution', '1920x1080',
    'fps', 25
 ),
 JSON_OBJECT(
    'ppe_zone', JSON_ARRAY(
        JSON_OBJECT(
            'zone_id', 2,
            'name', 'PPE Required Area',
            'coordinates', JSON_ARRAY(JSON_ARRAY(300, 250), JSON_ARRAY(900, 250), JSON_ARRAY(900, 700), JSON_ARRAY(300, 700))
        )
    )
 ),
 JSON_OBJECT('required_ppe', JSON_ARRAY('hard_hat', 'safety_vest'), 'confidence_threshold', 0.3)
),

-- Camera 3: Tailgating Detection at Security Gate
('multi-cam-project-001', 'Security Gate - Tailgating Monitor', 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
 'tailgating_detection', 'tailgating', 'active',
 JSON_OBJECT(
    'location', 'Security Checkpoint',
    'description', 'Access control and tailgating prevention',
    'resolution', '1920x1080',
    'fps', 25
 ),
 JSON_OBJECT(
    'entry', JSON_ARRAY(
        JSON_OBJECT(
            'zone_id', 3,
            'name', 'Access Control Point',
            'coordinates', JSON_ARRAY(JSON_ARRAY(250, 300), JSON_ARRAY(750, 300), JSON_ARRAY(750, 650), JSON_ARRAY(250, 650))
        )
    )
 ),
 JSON_OBJECT('time_limit', 2.0, 'distance_threshold', 200, 'confidence_threshold', 0.3)
),

-- Camera 4: Intrusion Detection in Server Room
('multi-cam-project-001', 'Server Room - Intrusion Monitor', 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
 'intrusion_detection', 'intrusion', 'active',
 JSON_OBJECT(
    'location', 'Server Room',
    'description', 'Critical infrastructure protection',
    'resolution', '1920x1080',
    'fps', 25
 ),
 JSON_OBJECT(
    'intrusion', JSON_ARRAY(
        JSON_OBJECT(
            'zone_id', 4,
            'name', 'Restricted Server Area',
            'coordinates', JSON_ARRAY(JSON_ARRAY(500, 200), JSON_ARRAY(1200, 200), JSON_ARRAY(1200, 800), JSON_ARRAY(500, 800))
        )
    )
 ),
 JSON_OBJECT('alert_immediately', true, 'confidence_threshold', 0.3)
),

-- Camera 5: Loitering Detection in Lobby
('multi-cam-project-001', 'Lobby - Loitering Monitor', 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
 'loitering_detection', 'loitering', 'active',
 JSON_OBJECT(
    'location', 'Main Lobby',
    'description', 'Prevent unauthorized loitering in public areas',
    'resolution', '1920x1080',
    'fps', 25
 ),
 JSON_OBJECT(
    'loitering', JSON_ARRAY(
        JSON_OBJECT(
            'zone_id', 5,
            'name', 'No Loitering Zone',
            'coordinates', JSON_ARRAY(JSON_ARRAY(400, 350), JSON_ARRAY(1000, 350), JSON_ARRAY(1000, 750), JSON_ARRAY(400, 750))
        )
    )
 ),
 JSON_OBJECT('time_threshold', 300, 'movement_threshold', 20, 'confidence_threshold', 0.3)
);

-- Insert camera use case assignments
INSERT IGNORE INTO camera_use_cases (camera_id, use_case, is_primary, configuration)
SELECT 
    c.camera_id,
    c.primary_use_case,
    true,
    c.processing_rules
FROM cameras c 
WHERE c.project_id = 'multi-cam-project-001';

-- Create views for easy querying
CREATE OR REPLACE VIEW camera_status_view AS
SELECT 
    c.camera_id,
    c.name,
    c.primary_use_case,
    c.connection_status,
    c.last_seen,
    c.metadata->>'$.location' as location,
    COUNT(e.event_id) as events_today
FROM cameras c
LEFT JOIN events e ON c.camera_id = e.camera_id 
    AND DATE(e.timestamp) = CURDATE()
WHERE c.status = 'active'
GROUP BY c.camera_id, c.name, c.primary_use_case, c.connection_status, c.last_seen;

CREATE OR REPLACE VIEW system_health_view AS
SELECT 
    COUNT(*) as total_cameras,
    SUM(CASE WHEN connection_status = 'connected' THEN 1 ELSE 0 END) as connected_cameras,
    SUM(CASE WHEN connection_status = 'disconnected' THEN 1 ELSE 0 END) as disconnected_cameras,
    SUM(CASE WHEN connection_status = 'error' THEN 1 ELSE 0 END) as error_cameras,
    COUNT(DISTINCT primary_use_case) as active_use_cases
FROM cameras 
WHERE status = 'active';

-- Create stored procedures for common operations
DELIMITER //

CREATE PROCEDURE GetCameraConfigurations()
BEGIN
    SELECT 
        c.camera_id,
        c.name,
        c.stream_url,
        c.primary_use_case as use_case,
        c.zone_configuration as zones,
        c.processing_rules as rules,
        c.connection_status,
        c.status
    FROM cameras c
    WHERE c.status = 'active'
    ORDER BY c.camera_id;
END //

CREATE PROCEDURE UpdateCameraHealth(
    IN p_camera_id INT,
    IN p_connection_status VARCHAR(20),
    IN p_fps DECIMAL(5,2),
    IN p_frames_processed INT,
    IN p_events_detected INT,
    IN p_error_message TEXT
)
BEGIN
    -- Update camera status
    UPDATE cameras 
    SET 
        connection_status = p_connection_status,
        last_seen = CURRENT_TIMESTAMP
    WHERE camera_id = p_camera_id;
    
    -- Insert health record
    INSERT INTO camera_health (
        camera_id, connection_status, fps, frames_processed, 
        events_detected, error_message
    ) VALUES (
        p_camera_id, p_connection_status, p_fps, p_frames_processed,
        p_events_detected, p_error_message
    );
END //

CREATE PROCEDURE GetSystemPerformanceStats(IN hours_back INT)
BEGIN
    SELECT 
        DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') as hour,
        AVG(total_cameras) as avg_cameras,
        AVG(active_cameras) as avg_active_cameras,
        AVG(total_fps) as avg_fps,
        SUM(total_events_per_minute) as total_events,
        AVG(cpu_usage_percent) as avg_cpu,
        AVG(memory_usage_percent) as avg_memory,
        AVG(gpu_usage_percent) as avg_gpu
    FROM system_performance 
    WHERE timestamp >= DATE_SUB(NOW(), INTERVAL hours_back HOUR)
    GROUP BY DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00')
    ORDER BY hour DESC;
END //

DELIMITER ;

-- Insert initial system performance record
INSERT INTO system_performance (
    total_cameras, active_cameras, total_fps, total_events_per_minute,
    cpu_usage_percent, memory_usage_percent, disk_usage_percent, gpu_usage_percent
) VALUES (5, 0, 0.0, 0, 0.0, 0.0, 0.0, 0.0);

-- Verify the setup
SELECT 'Multi-Camera Database Setup Completed!' AS Status;

-- Show camera configurations
SELECT 'Camera Configurations:' AS Info;
SELECT camera_id, name, primary_use_case, connection_status FROM cameras WHERE status = 'active';

-- Show use case assignments
SELECT 'Use Case Assignments:' AS Info;
SELECT camera_id, use_case, is_primary FROM camera_use_cases WHERE status = 'active';

SELECT 'Database ready for multi-camera system!' AS Ready;