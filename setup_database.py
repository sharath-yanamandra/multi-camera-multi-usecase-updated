
#!/usr/bin/env python3
# fix_database.py - Direct fix for your database issue
# This creates just the essential tables to fix the "events table doesn't exist" error

import os
import sys
import mysql.connector
from mysql.connector import Error
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_essential_tables():
    """Create the essential tables your system needs"""
    
    # Essential table definitions (minimal but functional)
    table_definitions = {
        'users': """
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(50) PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                role ENUM('admin', 'operator', 'viewer') DEFAULT 'viewer',
                status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL
            )
        """,
        
        'projects': """
            CREATE TABLE IF NOT EXISTS projects (
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
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """,
        
        'cameras': """
            CREATE TABLE IF NOT EXISTS cameras (
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
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
            )
        """,
        
        'events': """
            CREATE TABLE IF NOT EXISTS events (
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
                INDEX idx_event_type (event_type),
                INDEX idx_timestamp (timestamp)
            )
        """,
        
        'processing_stats': """
            CREATE TABLE IF NOT EXISTS processing_stats (
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
                FOREIGN KEY (camera_id) REFERENCES cameras(camera_id) ON DELETE CASCADE
            )
        """
    }
    
    # Sample data
    sample_data = {
        'users': """
            INSERT IGNORE INTO users (user_id, username, email, password_hash, full_name, role, status) 
            VALUES (
                'admin-user-001',
                'admin',
                'admin@datacenter.local',
                '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYW0.WaW7.0.tKS',
                'System Administrator',
                'admin',
                'active'
            )
        """,
        
        'projects': """
            INSERT IGNORE INTO projects (project_id, user_id, name, description, type, location, status)
            VALUES (
                'flexible-multi-camera-project',
                'admin-user-001',
                'Main Datacenter Monitoring',
                'Production multi-camera system with flexible use cases per camera',
                'multi_camera_production',
                'Main Facility',
                'active'
            )
        """,
        
        'cameras': [
            """
            INSERT IGNORE INTO cameras (camera_id, project_id, name, stream_url, primary_use_case, status, metadata) 
            VALUES (
                'cam1',
                'flexible-multi-camera-project',
                'main entrance',
                'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
                'people_counting',
                'active',
                '{"available_use_cases": ["people_counting", "ppe_detection", "tailgating", "intrusion", "loitering"]}'
            )
            """,
            """
            INSERT IGNORE INTO cameras (camera_id, project_id, name, stream_url, primary_use_case, status, metadata) 
            VALUES (
                'cam2',
                'flexible-multi-camera-project', 
                'reception',
                'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
                'people_counting',
                'active',
                '{"available_use_cases": ["people_counting", "ppe_detection", "tailgating", "intrusion", "loitering"]}'
            )
            """
        ]
    }
    
    try:
        from config.config import Config
        
        print(f"Connecting to database: {Config.MYSQL_DATABASE}")
        
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            port=Config.MYSQL_PORT,
            charset='utf8mb4',
            autocommit=True
        )
        
        if not connection.is_connected():
            print("Failed to connect to database")
            return False
        
        print("Connected successfully")
        cursor = connection.cursor()
        
        # Create tables in order (respecting foreign key dependencies)
        table_order = ['users', 'projects', 'cameras', 'events', 'processing_stats']
        
        print("Creating tables...")
        for table_name in table_order:
            print(f"  Creating {table_name}...")
            cursor.execute(table_definitions[table_name])
            print(f"  ✓ {table_name} created")
        
        # Insert sample data
        print("Inserting sample data...")
        
        # Users
        cursor.execute(sample_data['users'])
        print("  ✓ Admin user added")
        
        # Projects
        cursor.execute(sample_data['projects'])
        print("  ✓ Default project added")
        
        # Cameras
        for camera_sql in sample_data['cameras']:
            cursor.execute(camera_sql)
        print("  ✓ Cameras added")
        
        # Verify tables
        print("Verifying tables...")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        if tables:
            print(f"Found {len(tables)} tables:")
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  ✓ {table_name}: {count} rows")
        else:
            print("No tables found!")
            cursor.close()
            connection.close()
            return False
        
        # Test the specific events table that was failing
        print("Testing events table...")
        cursor.execute("SELECT COUNT(*) FROM events")
        event_count = cursor.fetchone()[0]
        print(f"✓ Events table working: {event_count} events")
        
        cursor.close()
        connection.close()
        
        print("Database setup completed successfully!")
        return True
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you have config/config.py")
        return False
    except Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Setup failed: {e}")
        return False

def test_event_saving():
    """Test event saving with your existing database_handler.py"""
    try:
        print("Testing event saving...")
        
        from core.database_handler import DatabaseHandler
        from config.config import Config
        
        db = DatabaseHandler({
            'host': Config.MYSQL_HOST,
            'user': Config.MYSQL_USER,
            'password': Config.MYSQL_PASSWORD,
            'database': Config.MYSQL_DATABASE,
            'port': Config.MYSQL_PORT
        })
        
        if db.connect():
            print("✓ Connected with existing database_handler.py")
            
            # Test the exact save_event method that was failing
            event_id = db.save_event(
                camera_id='cam1',
                project_id='flexible-multi-camera-project',
                event_type='test_detection',
                detection_data={'test': True, 'fix_verification': True},
                local_path=None,
                gcp_path=None,
                confidence=0.95
            )
            
            if event_id:
                print(f"✓ Event saved successfully: {event_id}")
                print("  This should fix your database errors!")
                
                # Verify the event was saved
                events = db.execute_query("SELECT * FROM events WHERE event_id = %s", (event_id,))
                if events:
                    print(f"✓ Event verified in database: {events[0]['event_type']}")
                
                # Clean up
                db.execute_query("DELETE FROM events WHERE event_id = %s", (event_id,))
                print("✓ Test event cleaned up")
            else:
                print("Event saving failed")
                db.disconnect()
                return False
            
            db.disconnect()
            return True
        else:
            print("Failed to connect with database_handler.py")
            return False
            
    except Exception as e:
        print(f"Event saving test failed: {e}")
        return False

def main():
    """Main function"""
    print("Direct Database Fix for Multi-Camera System")
    print("=" * 50)
    print("This will create the missing tables that are causing errors in your system.")
    print("")
    
    # Check config file exists
    if not Path("config/config.py").exists():
        print("Error: config/config.py not found")
        return False
    
    # Create essential tables
    if not create_essential_tables():
        print("Failed to create tables")
        return False
    
    print("\n" + "=" * 30)
    
    # Test event saving
    if not test_event_saving():
        print("Event saving test failed")
        return False
    
    print("\n" + "=" * 50)
    print("SUCCESS: Database fix completed!")
    print("")
    print("What was fixed:")
    print("• Created missing 'events' table")
    print("• Created all required supporting tables")
    print("• Added your existing cameras to database")
    print("• Verified event saving works")
    print("")
    print("Your system should now run without database errors:")
    print("  ERROR:core.database_handler: Table 'dc_test.events' doesn't exist")
    print("  ^^ This error should be gone now")
    print("")
    print("Next: Run your multi-camera system and check the logs!")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nFix failed: {e}")
        sys.exit(1)