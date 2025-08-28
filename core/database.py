# core/database.py
# Enhanced database handler for multi-camera datacenter monitoring system
# Replaces the existing database_handler.py with full functionality

import mysql.connector
from mysql.connector import Error, pooling
import json
import uuid
import hashlib
import bcrypt
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any, List, Tuple
import threading
import time
from contextlib import contextmanager

class DatabaseManager:
    """Enhanced database manager for datacenter monitoring system"""
    
    def __init__(self, db_config: Dict[str, Any], pool_size: int = 10):
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
        self.connection_pool = None
        self.lock = threading.Lock()
        
        # Initialize connection pool
        self._init_connection_pool(pool_size)
        
        # Cache for frequently accessed data
        self._cache = {}
        self._cache_lock = threading.Lock()
        self._cache_ttl = 300  # 5 minutes
        
    def _init_connection_pool(self, pool_size: int):
        """Initialize MySQL connection pool"""
        try:
            pool_config = self.db_config.copy()
            pool_config.update({
                'pool_name': 'datacenter_pool',
                'pool_size': pool_size,
                'pool_reset_session': True,
                'autocommit': True
            })
            
            self.connection_pool = pooling.MySQLConnectionPool(**pool_config)
            self.logger.info(f"Database connection pool initialized with {pool_size} connections")
            
        except Error as e:
            self.logger.error(f"Failed to create connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool with proper cleanup"""
        connection = None
        try:
            connection = self.connection_pool.get_connection()
            yield connection
        except Error as e:
            self.logger.error(f"Database connection error: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[List[Dict]]:
        """Execute query with connection pooling"""
        try:
            with self.get_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(query, params)
                
                if fetch or query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    cursor.close()
                    return result
                else:
                    connection.commit()
                    affected_rows = cursor.rowcount
                    cursor.close()
                    return [{'affected_rows': affected_rows}]
                    
        except Error as e:
            self.logger.error(f"Query execution error: {e}")
            return None
    
    def execute_many(self, query: str, params_list: List[tuple]) -> bool:
        """Execute multiple queries in batch"""
        try:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.executemany(query, params_list)
                connection.commit()
                cursor.close()
                return True
        except Error as e:
            self.logger.error(f"Batch execution error: {e}")
            return False
    
    # USER MANAGEMENT
    def create_user(self, username: str, email: str, password: str, 
                   full_name: str = None, role: str = 'viewer') -> Optional[str]:
        """Create new user"""
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        query = """
            INSERT INTO users (user_id, username, email, password_hash, full_name, role)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (user_id, username, email, password_hash, full_name, role)
        
        result = self.execute_query(query, params)
        if result:
            self.logger.info(f"User created: {username} ({user_id})")
            return user_id
        return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user credentials"""
        query = """
            SELECT user_id, username, email, password_hash, full_name, role, status
            FROM users 
            WHERE username = %s AND status = 'active'
        """
        
        result = self.execute_query(query, (username,), fetch=True)
        if result and len(result) > 0:
            user = result[0]
            if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                # Update last login
                self.execute_query(
                    "UPDATE users SET last_login = NOW() WHERE user_id = %s",
                    (user['user_id'],)
                )
                
                # Remove password hash from return value
                del user['password_hash']
                return user
        
        return None
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        query = """
            SELECT user_id, username, email, full_name, role, status, 
                   created_at, updated_at, last_login
            FROM users WHERE user_id = %s
        """
        result = self.execute_query(query, (user_id,), fetch=True)
        return result[0] if result else None
    
    # PROJECT MANAGEMENT
    def create_project(self, user_id: str, name: str, description: str = None,
                      project_type: str = 'datacenter_monitoring', 
                      location: str = None) -> Optional[str]:
        """Create new project"""
        project_id = f"proj-{uuid.uuid4().hex[:12]}"
        
        query = """
            INSERT INTO projects (project_id, user_id, name, description, type, location)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (project_id, user_id, name, description, project_type, location)
        
        result = self.execute_query(query, params)
        if result:
            self.logger.info(f"Project created: {name} ({project_id})")
            return project_id
        return None
    
    def get_projects(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Get projects for user or all projects"""
        if user_id:
            query = """
                SELECT p.*, u.username, u.full_name
                FROM projects p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.user_id = %s AND p.status = 'active'
                ORDER BY p.created_at DESC
            """
            params = (user_id,)
        else:
            query = """
                SELECT p.*, u.username, u.full_name
                FROM projects p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.status = 'active'
                ORDER BY p.created_at DESC
            """
            params = None
        
        return self.execute_query(query, params, fetch=True) or []
    
    # CAMERA MANAGEMENT
    def add_camera(self, camera_id: str, project_id: str, name: str, stream_url: str,
                  primary_use_case: str = 'people_counting', location: str = None,
                  zone_configuration: Dict = None, processing_rules: Dict = None) -> bool:
        """Add new camera"""
        query = """
            INSERT INTO cameras (camera_id, project_id, name, stream_url, location,
                               primary_use_case, zone_configuration, processing_rules)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            camera_id, project_id, name, stream_url, location, primary_use_case,
            json.dumps(zone_configuration) if zone_configuration else None,
            json.dumps(processing_rules) if processing_rules else None
        )
        
        result = self.execute_query(query, params)
        if result:
            self.logger.info(f"Camera added: {name} ({camera_id})")
            return True
        return False
    
    def get_cameras(self, project_id: str = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get cameras for project or all cameras"""
        base_query = """
            SELECT c.*, p.name as project_name, p.location as project_location
            FROM cameras c
            JOIN projects p ON c.project_id = p.project_id
        """
        
        conditions = []
        params = []
        
        if active_only:
            conditions.append("c.status = 'active'")
        
        if project_id:
            conditions.append("c.project_id = %s")
            params.append(project_id)
        
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        
        base_query += " ORDER BY c.name"
        
        result = self.execute_query(base_query, tuple(params) if params else None, fetch=True) or []
        
        # Parse JSON fields
        for camera in result:
            if camera.get('zone_configuration'):
                camera['zone_configuration'] = json.loads(camera['zone_configuration'])
            if camera.get('processing_rules'):
                camera['processing_rules'] = json.loads(camera['processing_rules'])
            if camera.get('metadata'):
                camera['metadata'] = json.loads(camera['metadata'])
        
        return result
    
    def update_camera_status(self, camera_id: str, status: str = None, 
                           connection_status: str = None) -> bool:
        """Update camera status and connection status"""
        updates = []
        params = []
        
        if status:
            updates.append("status = %s")
            params.append(status)
        
        if connection_status:
            updates.append("connection_status = %s")
            params.append(connection_status)
        
        if not updates:
            return False
        
        updates.append("last_seen = NOW()")
        params.append(camera_id)
        
        query = f"UPDATE cameras SET {', '.join(updates)} WHERE camera_id = %s"
        
        result = self.execute_query(query, tuple(params))
        return result is not None
    
    # CAMERA USE CASES MANAGEMENT (for flexible multi-use case system)
    def add_camera_use_case(self, camera_id: str, use_case: str, 
                           is_primary: bool = False, is_enabled: bool = True,
                           configuration: Dict = None) -> bool:
        """Add use case to camera"""
        query = """
            INSERT INTO camera_use_cases (camera_id, use_case, is_primary, is_enabled, configuration)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                is_primary = VALUES(is_primary),
                is_enabled = VALUES(is_enabled),
                configuration = VALUES(configuration)
        """
        params = (
            camera_id, use_case, is_primary, is_enabled,
            json.dumps(configuration) if configuration else None
        )
        
        return self.execute_query(query, params) is not None
    
    def get_camera_use_cases(self, camera_id: str) -> List[Dict[str, Any]]:
        """Get all use cases for a camera"""
        query = """
            SELECT * FROM camera_use_cases 
            WHERE camera_id = %s 
            ORDER BY is_primary DESC, use_case
        """
        
        result = self.execute_query(query, (camera_id,), fetch=True) or []
        
        # Parse JSON configuration
        for use_case in result:
            if use_case.get('configuration'):
                use_case['configuration'] = json.loads(use_case['configuration'])
        
        return result
    
    def toggle_camera_use_case(self, camera_id: str, use_case: str, enabled: bool) -> bool:
        """Enable/disable a specific use case for camera"""
        query = """
            UPDATE camera_use_cases 
            SET is_enabled = %s 
            WHERE camera_id = %s AND use_case = %s
        """
        
        result = self.execute_query(query, (enabled, camera_id, use_case))
        if result:
            action = "enabled" if enabled else "disabled"
            self.logger.info(f"Camera {camera_id} use case {use_case} {action}")
            return True
        return False
    
    # EVENT MANAGEMENT
    def save_event(self, camera_id: str, project_id: str, event_type: str,
                  detection_data: Dict[str, Any], local_path: str = None,
                  gcp_path: str = None, confidence: float = None,
                  severity: str = 'info') -> str:
        """Save detection event to database"""
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        
        # Get camera name for better logging
        camera_name = self._get_camera_name(camera_id)
        
        query = """
            INSERT INTO events (
                event_id, camera_id, project_id, event_type, severity,
                detection_data, local_image_path, gcp_image_path, 
                confidence_score, camera_name, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'new')
        """
        
        params = (
            event_id, camera_id, project_id, event_type, severity,
            json.dumps(detection_data) if detection_data else None,
            local_path, gcp_path, confidence, camera_name
        )
        
        result = self.execute_query(query, params)
        if result:
            self.logger.info(f"Event saved: {event_type} -> {event_id}")
            return event_id
        else:
            self.logger.error(f"Failed to save event: {event_type}")
            return None
    
    def get_events(self, camera_id: str = None, project_id: str = None,
                  event_type: str = None, hours: int = 24, 
                  limit: int = 1000) -> List[Dict[str, Any]]:
        """Get events with filters"""
        conditions = []
        params = []
        
        conditions.append("timestamp >= %s")
        params.append(datetime.now() - timedelta(hours=hours))
        
        if camera_id:
            conditions.append("camera_id = %s")
            params.append(camera_id)
        
        if project_id:
            conditions.append("project_id = %s")
            params.append(project_id)
        
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        
        query = f"""
            SELECT e.*, c.name as camera_name, p.name as project_name
            FROM events e
            JOIN cameras c ON e.camera_id = c.camera_id
            JOIN projects p ON e.project_id = p.project_id
            WHERE {' AND '.join(conditions)}
            ORDER BY e.timestamp DESC
            LIMIT {limit}
        """
        
        result = self.execute_query(query, tuple(params), fetch=True) or []
        
        # Parse detection_data JSON
        for event in result:
            if event.get('detection_data'):
                try:
                    event['detection_data'] = json.loads(event['detection_data'])
                except json.JSONDecodeError:
                    event['detection_data'] = {}
        
        return result
    
    def get_event_stats(self, camera_id: str = None, hours: int = 24) -> Dict[str, Any]:
        """Get event statistics"""
        conditions = []
        params = []
        
        conditions.append("timestamp >= %s")
        params.append(datetime.now() - timedelta(hours=hours))
        
        if camera_id:
            conditions.append("camera_id = %s")
            params.append(camera_id)
        
        query = f"""
            SELECT 
                event_type,
                severity,
                COUNT(*) as count,
                AVG(confidence_score) as avg_confidence,
                MAX(timestamp) as latest_event
            FROM events 
            WHERE {' AND '.join(conditions)}
            GROUP BY event_type, severity
            ORDER BY count DESC
        """
        
        result = self.execute_query(query, tuple(params), fetch=True) or []
        
        stats = {
            'total_events': sum(row['count'] for row in result),
            'by_type': {},
            'by_severity': {},
            'latest_event': None
        }
        
        for row in result:
            event_type = row['event_type']
            severity = row['severity']
            count = row['count']
            
            stats['by_type'][event_type] = stats['by_type'].get(event_type, 0) + count
            stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + count
            
            if not stats['latest_event'] or row['latest_event'] > stats['latest_event']:
                stats['latest_event'] = row['latest_event']
        
        return stats
    
    # PROCESSING STATISTICS
    def update_processing_stats(self, camera_id: str, stats: Dict[str, int]):
        """Update processing statistics"""
        # Check if stats record exists for today
        check_query = """
            SELECT stat_id FROM processing_stats 
            WHERE camera_id = %s AND DATE(timestamp) = CURDATE()
            ORDER BY timestamp DESC LIMIT 1
        """
        existing = self.execute_query(check_query, (camera_id,), fetch=True)
        
        if existing:
            # Update existing record
            update_query = """
                UPDATE processing_stats SET
                    frames_processed = frames_processed + %s,
                    total_detections = total_detections + %s,
                    people_counting_events = people_counting_events + %s,
                    ppe_detection_events = ppe_detection_events + %s,
                    tailgating_events = tailgating_events + %s,
                    intrusion_events = intrusion_events + %s,
                    loitering_events = loitering_events + %s,
                    processing_time_ms = processing_time_ms + %s,
                    timestamp = NOW()
                WHERE stat_id = %s
            """
            
            params = (
                stats.get('frames_processed', 0),
                stats.get('total_detections', 0),
                stats.get('people_counting_events', 0),
                stats.get('ppe_detection_events', 0),
                stats.get('tailgating_events', 0),
                stats.get('intrusion_events', 0),
                stats.get('loitering_events', 0),
                stats.get('processing_time_ms', 0),
                existing[0]['stat_id']
            )
            
            self.execute_query(update_query, params)
        else:
            # Create new record
            insert_query = """
                INSERT INTO processing_stats (
                    camera_id, frames_processed, total_detections,
                    people_counting_events, ppe_detection_events, tailgating_events,
                    intrusion_events, loitering_events, processing_time_ms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                camera_id,
                stats.get('frames_processed', 0),
                stats.get('total_detections', 0),
                stats.get('people_counting_events', 0),
                stats.get('ppe_detection_events', 0),
                stats.get('tailgating_events', 0),
                stats.get('intrusion_events', 0),
                stats.get('loitering_events', 0),
                stats.get('processing_time_ms', 0)
            )
            
            self.execute_query(insert_query, params)
    
    def get_processing_stats(self, camera_id: str = None, days: int = 7) -> List[Dict[str, Any]]:
        """Get processing statistics"""
        conditions = []
        params = []
        
        conditions.append("timestamp >= %s")
        params.append(datetime.now() - timedelta(days=days))
        
        if camera_id:
            conditions.append("camera_id = %s")
            params.append(camera_id)
        
        query = f"""
            SELECT ps.*, c.name as camera_name
            FROM processing_stats ps
            JOIN cameras c ON ps.camera_id = c.camera_id
            WHERE {' AND '.join(conditions)}
            ORDER BY ps.timestamp DESC
        """
        
        return self.execute_query(query, tuple(params), fetch=True) or []
    
    # CAMERA HEALTH MONITORING
    def log_camera_health(self, camera_id: str, connection_status: str,
                         fps: float = 0.0, frames_processed: int = 0,
                         events_detected: int = 0, cpu_usage: float = 0.0,
                         memory_usage: float = 0.0, error_message: str = None):
        """Log camera health metrics"""
        query = """
            INSERT INTO camera_health 
            (camera_id, connection_status, fps, frames_processed, events_detected,
             cpu_usage, memory_usage, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (camera_id, connection_status, fps, frames_processed, 
                 events_detected, cpu_usage, memory_usage, error_message)
        
        return self.execute_query(query, params) is not None
    
    def get_camera_health(self, camera_id: str = None, hours: int = 24) -> List[Dict[str, Any]]:
        """Get camera health data"""
        conditions = []
        params = []
        
        conditions.append("timestamp >= %s")
        params.append(datetime.now() - timedelta(hours=hours))
        
        if camera_id:
            conditions.append("camera_id = %s")
            params.append(camera_id)
        
        query = f"""
            SELECT ch.*, c.name as camera_name
            FROM camera_health ch
            JOIN cameras c ON ch.camera_id = c.camera_id
            WHERE {' AND '.join(conditions)}
            ORDER BY ch.timestamp DESC
        """
        
        return self.execute_query(query, tuple(params), fetch=True) or []
    
    # SYSTEM PERFORMANCE MONITORING
    def log_system_performance(self, total_cameras: int, active_cameras: int,
                             total_fps: float, events_per_minute: int,
                             cpu_usage: float = 0.0, memory_usage: float = 0.0,
                             disk_usage: float = 0.0, gpu_usage: float = 0.0,
                             pending_uploads: int = 0):
        """Log system performance metrics"""
        query = """
            INSERT INTO system_performance 
            (total_cameras, active_cameras, total_fps, total_events_per_minute,
             cpu_usage_percent, memory_usage_percent, disk_usage_percent, 
             gpu_usage_percent, pending_uploads)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (total_cameras, active_cameras, total_fps, events_per_minute,
                 cpu_usage, memory_usage, disk_usage, gpu_usage, pending_uploads)
        
        return self.execute_query(query, params) is not None
    
    def get_system_performance(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get system performance data"""
        query = """
            SELECT * FROM system_performance 
            WHERE timestamp >= %s
            ORDER BY timestamp DESC
        """
        
        params = (datetime.now() - timedelta(hours=hours),)
        return self.execute_query(query, params, fetch=True) or []
    
    # UTILITY METHODS
    def _get_camera_name(self, camera_id: str) -> Optional[str]:
        """Get camera name with caching"""
        cache_key = f"camera_name_{camera_id}"
        
        with self._cache_lock:
            # Check cache
            if cache_key in self._cache:
                cached_data = self._cache[cache_key]
                if time.time() - cached_data['timestamp'] < self._cache_ttl:
                    return cached_data['value']
        
        # Query database
        query = "SELECT name FROM cameras WHERE camera_id = %s"
        result = self.execute_query(query, (camera_id,), fetch=True)
        
        name = result[0]['name'] if result else None
        
        # Cache result
        with self._cache_lock:
            self._cache[cache_key] = {
                'value': name,
                'timestamp': time.time()
            }
        
        return name
    
    def initialize_database(self) -> bool:
        """Initialize database with schema from SQL file"""
        try:
            # Read SQL file
            sql_file = "config/datacenter_schema.sql"
            with open(sql_file, 'r', encoding='utf-8') as file:
                sql_content = file.read()
            
            # Split into individual statements
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            with self.get_connection() as connection:
                cursor = connection.cursor()
                
                for statement in statements:
                    if statement and not statement.startswith('--'):
                        try:
                            cursor.execute(statement)
                            connection.commit()
                        except Error as e:
                            self.logger.warning(f"Statement execution warning: {e}")
                
                cursor.close()
            
            self.logger.info("Database initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Database initialization error: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                cursor.close()
                return result is not None
        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics"""
        info = {}
        
        try:
            # Database version
            version_result = self.execute_query("SELECT VERSION()", fetch=True)
            info['version'] = version_result[0]['VERSION()'] if version_result else 'Unknown'
            
            # Table statistics
            tables_query = """
                SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH
                FROM information_schema.tables 
                WHERE table_schema = %s
                ORDER BY TABLE_NAME
            """
            tables_result = self.execute_query(tables_query, (self.db_config['database'],), fetch=True) or []
            info['tables'] = tables_result
            
            # Connection pool status
            info['connection_pool'] = {
                'pool_name': self.connection_pool.pool_name,
                'pool_size': self.connection_pool.pool_size
            }
            
        except Exception as e:
            self.logger.error(f"Error getting database info: {e}")
            info['error'] = str(e)
        
        return info
    
    def cleanup_old_data(self, days: int = 30):
        """Cleanup old data to maintain performance"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Cleanup old events (keep events for specified days)
            events_deleted = self.execute_query(
                "DELETE FROM events WHERE timestamp < %s",
                (cutoff_date,)
            )
            
            # Cleanup old health records
            health_deleted = self.execute_query(
                "DELETE FROM camera_health WHERE timestamp < %s",
                (cutoff_date,)
            )
            
            # Cleanup old performance records
            perf_deleted = self.execute_query(
                "DELETE FROM system_performance WHERE timestamp < %s",
                (cutoff_date,)
            )
            
            self.logger.info(f"Cleanup completed: {events_deleted} events, {health_deleted} health records, {perf_deleted} performance records")
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def close_pool(self):
        """Close connection pool"""
        try:
            if self.connection_pool:
                # Close all connections in pool
                self.connection_pool._remove_connections()
                self.logger.info("Database connection pool closed")
        except Exception as e:
            self.logger.error(f"Error closing connection pool: {e}")


# Backward compatibility - DatabaseHandler class
class DatabaseHandler(DatabaseManager):
    """Backward compatibility wrapper"""
    
    def __init__(self, db_config: Dict[str, Any]):
        # Convert old config format to new format if needed
        if 'host' in db_config and 'user' in db_config:
            new_config = {
                'host': db_config['host'],
                'user': db_config['user'],
                'password': db_config['password'],
                'database': db_config['database'],
                'port': db_config.get('port', 3306),
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci',
                'autocommit': True
            }
        else:
            new_config = db_config
        
        super().__init__(new_config, pool_size=5)
        
        # Add backward compatibility methods
        self.db = self  # For compatibility with existing code
    
    def connect(self) -> bool:
        """Backward compatibility - test connection"""
        return self.test_connection()
    
    def disconnect(self):
        """Backward compatibility - close pool"""
        self.close_pool()
    
    def get_camera_info(self) -> Optional[Dict[str, Any]]:
        """Backward compatibility - get first camera info"""
        cameras = self.get_cameras()
        return cameras[0] if cameras else None


# Test function
def test_database():
    """Test database functionality"""
    from config.config import Config
    
    logging.basicConfig(level=logging.INFO)
    
    db_config = {
        'host': Config.MYSQL_HOST,
        'user': Config.MYSQL_USER,
        'password': Config.MYSQL_PASSWORD,
        'database': Config.MYSQL_DATABASE,
        'port': Config.MYSQL_PORT
    }
    
    db = DatabaseManager(db_config)
    
    if db.test_connection():
        print("✅ Database connection successful")
        
        # Test user creation
        user_id = db.create_user("testuser", "test@example.com", "password123", "Test User", "viewer")
        if user_id:
            print(f"✅ User created: {user_id}")
            
            # Test authentication
            user = db.authenticate_user("testuser", "password123")
            if user:
                print(f"✅ Authentication successful: {user['username']}")
        
        # Test project creation
        project_id = db.create_project(user_id or "admin-user-001", "Test Project", "Test Description")
        if project_id:
            print(f"✅ Project created: {project_id}")
        
        # Get database info
        info = db.get_database_info()
        print(f"✅ Database info: {info['version']}")
        print(f"✅ Tables: {len(info['tables'])}")
        
        db.close_pool()
    else:
        print("❌ Database connection failed")


if __name__ == "__main__":
    test_database()