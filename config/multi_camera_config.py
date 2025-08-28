# config/multi_camera_config.py - NEW FILE
# Extended configuration for multi-camera support

import os
from typing import List, Dict, Any
from .config import Config

class MultiCameraConfig(Config):
    """Extended configuration for multi-camera system"""
    
    # Multi-camera specific settings
    MULTI_CAMERA_MODE = True
    MAX_CONCURRENT_CAMERAS = int(os.getenv('MAX_CONCURRENT_CAMERAS', '5'))
    
    # Processing settings per camera
    FRAMES_PER_CAMERA_PER_SECOND = int(os.getenv('FRAMES_PER_CAMERA_PER_SECOND', '5'))
    MAX_PROCESSING_THREADS = int(os.getenv('MAX_PROCESSING_THREADS', '10'))
    EVENT_QUEUE_SIZE = int(os.getenv('EVENT_QUEUE_SIZE', '100'))
    
    # Camera connection settings
    CAMERA_CONNECTION_TIMEOUT = int(os.getenv('CAMERA_CONNECTION_TIMEOUT', '10'))
    CAMERA_RECONNECT_ATTEMPTS = int(os.getenv('CAMERA_RECONNECT_ATTEMPTS', '3'))
    CAMERA_HEALTH_CHECK_INTERVAL = int(os.getenv('CAMERA_HEALTH_CHECK_INTERVAL', '30'))
    
    # Resource management
    SHARED_MODEL_BATCH_SIZE = int(os.getenv('SHARED_MODEL_BATCH_SIZE', '1'))
    MEMORY_USAGE_LIMIT_MB = int(os.getenv('MEMORY_USAGE_LIMIT_MB', '2048'))
    
    # User interface settings
    CAMERA_SELECTION_INTERFACE = os.getenv('CAMERA_SELECTION_INTERFACE', 'web')  # 'web', 'cli', 'config'
    
    @staticmethod
    def load_camera_configurations_from_database(db_handler) -> List[Dict[str, Any]]:
        """Load camera configurations from database"""
        query = """
            SELECT 
                c.camera_id, 
                c.name, 
                c.stream_url, 
                c.metadata,
                c.status
            FROM cameras c 
            WHERE c.status = 'active'
            ORDER BY c.camera_id
        """
        
        try:
            results = db_handler.execute_query(query)
            camera_configs = []
            
            for row in results:
                # Parse metadata to extract use case and zones
                metadata = row.get('metadata', {})
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)
                
                config = {
                    'camera_id': str(row['camera_id']),
                    'name': row['name'],
                    'stream_url': row['stream_url'],
                    'use_case': metadata.get('primary_use_case', 'people_counting'),
                    'zones': metadata.get('zones', {}),
                    'rules': metadata.get('rules', {}),
                    'status': row['status']
                }
                
                camera_configs.append(config)
            
            return camera_configs
            
        except Exception as e:
            print(f"Error loading camera configurations: {e}")
            return []
    
    @staticmethod
    def create_default_camera_configurations() -> List[Dict[str, Any]]:
        """Create default camera configurations for testing"""
        return [
            {
                'camera_id': 'cam_001',
                'name': 'Main Entrance - People Counter',
                'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
                'use_case': 'people_counting',
                'zones': {
                    'counting': [{
                        'zone_id': 1,
                        'name': 'Entry Count Zone',
                        'coordinates': [[200, 200], [800, 200], [800, 600], [200, 600]]
                    }]
                },
                'rules': {
                    'count_threshold': 0,
                    'confidence_threshold': 0.3
                }
            },
            {
                'camera_id': 'cam_002',
                'name': 'Work Area - PPE Monitor',
                'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
                'use_case': 'ppe_detection',
                'zones': {
                    'ppe_zone': [{
                        'zone_id': 2,
                        'name': 'PPE Required Area',
                        'coordinates': [[300, 250], [900, 250], [900, 700], [300, 700]]
                    }]
                },
                'rules': {
                    'required_ppe': ['hard_hat', 'safety_vest'],
                    'confidence_threshold': 0.3
                }
            },
            {
                'camera_id': 'cam_003',
                'name': 'Security Gate - Tailgating Detection',
                'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
                'use_case': 'tailgating',
                'zones': {
                    'entry': [{
                        'zone_id': 3,
                        'name': 'Access Control Point',
                        'coordinates': [[250, 300], [750, 300], [750, 650], [250, 650]]
                    }]
                },
                'rules': {
                    'time_limit': 2.0,
                    'distance_threshold': 200,
                    'confidence_threshold': 0.3
                }
            },
            {
                'camera_id': 'cam_004',
                'name': 'Server Room - Intrusion Detection',
                'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
                'use_case': 'intrusion',
                'zones': {
                    'intrusion': [{
                        'zone_id': 4,
                        'name': 'Restricted Server Area',
                        'coordinates': [[500, 200], [1200, 200], [1200, 800], [500, 800]]
                    }]
                },
                'rules': {
                    'alert_immediately': True,
                    'confidence_threshold': 0.3
                }
            },
            {
                'camera_id': 'cam_005',
                'name': 'Lobby - Loitering Detection',
                'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
                'use_case': 'loitering',
                'zones': {
                    'loitering': [{
                        'zone_id': 5,
                        'name': 'No Loitering Zone',
                        'coordinates': [[400, 350], [1000, 350], [1000, 750], [400, 750]]
                    }]
                },
                'rules': {
                    'time_threshold': 300,  # 5 minutes
                    'movement_threshold': 20,
                    'confidence_threshold': 0.3
                }
            }
        ]