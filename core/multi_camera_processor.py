# core/multi_camera_processor.py - NEW FILE
# Extension of your existing single camera system to support multiple cameras

import os
import sys
import threading
import time
import asyncio
import json
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple
from functools import partial
from collections import defaultdict
from datetime import datetime
import queue

# Import your existing components (no changes needed!)
from camera_models.people_count_monitoring import PeopleCountingMonitor
from camera_models.ppe_kit_monitoring import PPEDetector
from camera_models.tailgating_zone_monitoring import TailgatingZoneMonitor
from camera_models.intrusion_zone_monitoring import IntrusionZoneMonitor
from camera_models.loitering_zone_monitoring import LoiteringZoneMonitor

from core.database_handler import DatabaseHandler
from core.gcp_uploader import GCPUploader
from ultralytics import YOLO

# Your existing camera model mapping (unchanged)
CAMERA_MODEL_MAPPING = {
    'people_counting': PeopleCountingMonitor,
    'ppe_detection': PPEDetector, 
    'tailgating': TailgatingZoneMonitor,
    'intrusion': IntrusionZoneMonitor,
    'loitering': LoiteringZoneMonitor,
}

class CameraStream:
    """Individual camera stream handler"""
    
    def __init__(self, camera_config: Dict[str, Any], shared_model: YOLO):
        self.camera_id = camera_config['camera_id']
        self.camera_name = camera_config['name']
        self.stream_url = camera_config['stream_url']
        self.use_case = camera_config['use_case']
        self.zones = camera_config.get('zones', {})
        self.rules = camera_config.get('rules', {})
        
        # Shared YOLO model (memory efficient)
        self.shared_model = shared_model
        
        # Camera-specific model instance
        self.camera_model = None
        self.cap = None
        
        # Processing state
        self.running = False
        self.frame_count = 0
        self.last_processed_time = 0
        
        # Statistics
        self.stats = {
            'frames_processed': 0,
            'events_detected': 0,
            'last_fps': 0,
            'connection_status': 'disconnected'
        }
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Logger
        import logging
        self.logger = logging.getLogger(f'camera_{self.camera_id}')
    
    def initialize(self, db_handler: DatabaseHandler, gcp_uploader: GCPUploader):
        """Initialize camera stream and model"""
        try:
            # Initialize camera model for the selected use case
            if self.use_case in CAMERA_MODEL_MAPPING:
                model_class = CAMERA_MODEL_MAPPING[self.use_case]
                
                settings = {
                    'use_case': self.use_case,
                    'shared_model': self.shared_model,
                    'multi_camera_mode': True
                }
                
                self.camera_model = model_class(
                    camera_id=self.camera_id,
                    zones=self.zones,
                    rules=self.rules,
                    settings=settings,
                    db=db_handler,
                    db_writer=None,
                    frames_base_dir=f'outputs/frames/camera_{self.camera_id}'
                )
                
                # Enable individual events
                if hasattr(self.camera_model, 'set_individual_events_enabled'):
                    self.camera_model.set_individual_events_enabled(True)
                
                self.logger.info(f"Initialized {self.use_case} model for camera {self.camera_id}")
                return True
            else:
                self.logger.error(f"Unknown use case: {self.use_case}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize camera {self.camera_id}: {e}")
            return False
    
    def connect(self) -> bool:
        """Connect to camera stream"""
        try:
            self.cap = cv2.VideoCapture(self.stream_url)
            if self.cap.isOpened():
                self.stats['connection_status'] = 'connected'
                self.logger.info(f"Camera {self.camera_id} connected: {self.stream_url}")
                return True
            else:
                self.stats['connection_status'] = 'failed'
                self.logger.error(f"Failed to connect camera {self.camera_id}")
                return False
        except Exception as e:
            self.stats['connection_status'] = 'error'
            self.logger.error(f"Camera {self.camera_id} connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect camera stream"""
        if self.cap:
            self.cap.release()
            self.stats['connection_status'] = 'disconnected'
            self.logger.info(f"Camera {self.camera_id} disconnected")
    
    def process_frame(self) -> Tuple[bool, Optional[Dict]]:
        """Process a single frame from this camera"""
        try:
            if not self.cap or not self.cap.isOpened():
                return False, None
            
            ret, frame = self.cap.read()
            if not ret:
                self.logger.warning(f"Failed to read frame from camera {self.camera_id}")
                return False, None
            
            self.frame_count += 1
            
            # Run YOLO detection (shared model)
            detection_result = self.shared_model(frame, verbose=False)
            
            # Process with camera-specific model
            annotated_frame, detections = self.camera_model.process_frame(
                frame, 
                datetime.now(),
                detection_result
            )
            
            # Update statistics
            with self.lock:
                self.stats['frames_processed'] += 1
                current_time = time.time()
                if current_time - self.last_processed_time > 0:
                    self.stats['last_fps'] = 1.0 / (current_time - self.last_processed_time)
                self.last_processed_time = current_time
            
            # Return processing result
            result = {
                'camera_id': self.camera_id,
                'camera_name': self.camera_name,
                'use_case': self.use_case,
                'frame_count': self.frame_count,
                'annotated_frame': annotated_frame,
                'detections': detections,
                'timestamp': datetime.now(),
                'has_events': bool(detections)
            }
            
            return True, result
            
        except Exception as e:
            self.logger.error(f"Frame processing error for camera {self.camera_id}: {e}")
            return False, None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get camera statistics"""
        with self.lock:
            return {
                'camera_id': self.camera_id,
                'camera_name': self.camera_name,
                'use_case': self.use_case,
                'connection_status': self.stats['connection_status'],
                'frames_processed': self.stats['frames_processed'],
                'events_detected': self.stats['events_detected'],
                'current_fps': self.stats['last_fps'],
                'frame_count': self.frame_count
            }


class MultiCameraProcessor:
    """
    Multi-camera video processor
    Extends your existing single camera system to handle multiple cameras
    """
    
    def __init__(self, config):
        self.config = config
        
        # Setup logging
        import logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize shared components (reuse your existing code)
        self.db_handler = DatabaseHandler({
            'host': config.MYSQL_HOST,
            'user': config.MYSQL_USER,
            'password': config.MYSQL_PASSWORD,
            'database': config.MYSQL_DATABASE,
            'port': config.MYSQL_PORT
        })
        
        self.gcp_uploader = GCPUploader(
            config.GCP_CREDENTIALS_PATH,
            config.GCP_BUCKET_NAME,
            config.GCP_PROJECT_ID
        )
        
        # Load shared YOLO model (memory efficient - one model for all cameras)
        self.shared_model = YOLO(config.DETECTION_MODEL_PATH)
        self.logger.info(f"Loaded shared YOLO model: {config.DETECTION_MODEL_PATH}")
        
        # Camera streams
        self.camera_streams = {}  # {camera_id: CameraStream}
        self.camera_configs = []
        
        # Processing control
        self.running = False
        self.processing_threads = {}
        self.event_queue = queue.Queue()
        
        # Statistics
        self.global_stats = {
            'total_cameras': 0,
            'active_cameras': 0,
            'total_events': 0,
            'events_by_camera': defaultdict(int),
            'events_by_use_case': defaultdict(int)
        }
    
    def load_camera_configurations(self, camera_configs: List[Dict[str, Any]]):
        """
        Load camera configurations
        
        Expected format:
        [
            {
                'camera_id': 'cam_001',
                'name': 'Front Entrance',
                'stream_url': 'rtsp://...',
                'use_case': 'people_counting',
                'zones': {...},
                'rules': {...}
            },
            ...
        ]
        """
        self.camera_configs = camera_configs
        self.global_stats['total_cameras'] = len(camera_configs)
        
        self.logger.info(f"Loaded {len(camera_configs)} camera configurations")
        
        # Create camera stream instances
        for config in camera_configs:
            camera_stream = CameraStream(config, self.shared_model)
            self.camera_streams[config['camera_id']] = camera_stream
            
            self.logger.info(f"Camera {config['camera_id']}: {config['name']} -> {config['use_case']}")
    
    def initialize(self):
        """Initialize the multi-camera processor"""
        self.logger.info("Initializing Multi-Camera Processor")
        
        # Connect to database
        if not self.db_handler.connect():
            raise RuntimeError("Failed to connect to database")
        
        # Initialize each camera stream
        initialized_cameras = 0
        for camera_id, camera_stream in self.camera_streams.items():
            if camera_stream.initialize(self.db_handler, self.gcp_uploader):
                if camera_stream.connect():
                    initialized_cameras += 1
                    self.logger.info(f"Camera {camera_id} initialized and connected")
                else:
                    self.logger.error(f"Camera {camera_id} failed to connect")
            else:
                self.logger.error(f"Camera {camera_id} failed to initialize")
        
        self.global_stats['active_cameras'] = initialized_cameras
        
        # Test GCP connection
        if self.gcp_uploader.test_connection():
            self.logger.info("GCP storage connection successful")
        else:
            self.logger.warning("GCP storage connection failed")
        
        self.logger.info(f"Multi-Camera Processor initialized: {initialized_cameras}/{len(self.camera_streams)} cameras active")
    
    def _camera_processing_worker(self, camera_id: str):
        """Worker thread for processing individual camera"""
        camera_stream = self.camera_streams[camera_id]
        self.logger.info(f"Started processing worker for camera {camera_id}")
        
        while self.running:
            try:
                # Process frame
                success, result = camera_stream.process_frame()
                
                if success and result and result['has_events']:
                    # Queue events for saving
                    self.event_queue.put(result)
                    
                    # Update global statistics
                    self.global_stats['total_events'] += 1
                    self.global_stats['events_by_camera'][camera_id] += 1
                    self.global_stats['events_by_use_case'][result['use_case']] += 1
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)  # ~100 FPS max per camera
                
            except Exception as e:
                self.logger.error(f"Error in camera {camera_id} worker: {e}")
                time.sleep(1)  # Longer delay on error
        
        # Cleanup
        camera_stream.disconnect()
        self.logger.info(f"Stopped processing worker for camera {camera_id}")
    
    def _event_saving_worker(self):
        """Worker thread for saving events to database and GCP"""
        self.logger.info("Started event saving worker")
        
        while self.running or not self.event_queue.empty():
            try:
                # Get event from queue (with timeout)
                result = self.event_queue.get(timeout=1.0)
                
                # Save event using your existing logic
                self._save_camera_event(result)
                
                # Mark task as done
                self.event_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error saving event: {e}")
        
        self.logger.info("Stopped event saving worker")
    
    def _save_camera_event(self, result: Dict[str, Any]):
        """Save camera event (reuses your existing save logic)"""
        try:
            camera_id = result['camera_id']
            use_case = result['use_case']
            annotated_frame = result['annotated_frame']
            detections = result['detections']
            
            # Make data JSON serializable (your existing function)
            json_safe_data = self._make_json_serializable({
                'camera_id': camera_id,
                'camera_name': result['camera_name'],
                'use_case': use_case,
                'detections': detections,
                'timestamp': result['timestamp'].isoformat(),
                'frame_count': result['frame_count']
            })
            
            # Save to GCP (your existing logic)
            local_path, gcp_path = self.gcp_uploader.save_and_upload_event(
                annotated_frame,
                use_case,
                camera_id,
                json_safe_data
            )
            
            # Save to database (your existing logic)
            event_id = self.db_handler.save_event(
                camera_id=camera_id,
                project_id='multi-camera-project',
                event_type=use_case,
                detection_data=json_safe_data,
                local_path=local_path,
                gcp_path=gcp_path,
                confidence=0.75
            )
            
            if event_id:
                self.logger.info(f"Event saved: Camera {camera_id} -> {use_case} -> {event_id}")
            
        except Exception as e:
            self.logger.error(f"Error saving camera event: {e}")
    
    def _make_json_serializable(self, obj):
        """Make object JSON serializable (your existing function)"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        else:
            return obj
    
    def start_processing(self):
        """Start multi-camera processing"""
        self.logger.info("Starting multi-camera processing...")
        
        # Initialize
        self.initialize()
        
        self.running = True
        
        # Start event saving worker
        event_worker = threading.Thread(target=self._event_saving_worker, daemon=True)
        event_worker.start()
        
        # Start processing worker for each camera
        for camera_id in self.camera_streams.keys():
            worker_thread = threading.Thread(
                target=self._camera_processing_worker, 
                args=(camera_id,),
                daemon=True
            )
            worker_thread.start()
            self.processing_threads[camera_id] = worker_thread
        
        self.logger.info(f"Started processing {len(self.processing_threads)} cameras")
        
        # Main monitoring loop
        try:
            last_stats_time = time.time()
            
            while self.running:
                # Print statistics every 10 seconds
                if time.time() - last_stats_time > 10:
                    self._print_global_stats()
                    last_stats_time = time.time()
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        
        # Cleanup
        self.stop()
    
    def stop(self):
        """Stop multi-camera processing"""
        self.logger.info("Stopping multi-camera processing...")
        
        # Stop processing
        self.running = False
        
        # Wait for worker threads to finish
        for camera_id, thread in self.processing_threads.items():
            self.logger.info(f"Waiting for camera {camera_id} worker to finish...")
            thread.join(timeout=5.0)
        
        # Wait for event queue to empty
        self.logger.info("Waiting for pending events to be saved...")
        self.event_queue.join()
        
        # Cleanup resources
        self.gcp_uploader.stop()
        self.db_handler.disconnect()
        
        self.logger.info("Multi-camera processing stopped")
    
    def _print_global_stats(self):
        """Print global statistics"""
        print("\n" + "="*80)
        print(f" MULTI-CAMERA PROCESSING STATS")
        print("="*80)
        print(f" Active cameras: {self.global_stats['active_cameras']}/{self.global_stats['total_cameras']}")
        print(f" Total events: {self.global_stats['total_events']}")
        print(f" Pending events: {self.event_queue.qsize()}")
        
        print("\n Events by camera:")
        for camera_id, count in self.global_stats['events_by_camera'].items():
            camera_name = self.camera_streams[camera_id].camera_name
            use_case = self.camera_streams[camera_id].use_case
            print(f"   {camera_id} ({camera_name}): {count} {use_case} events")
        
        print("\n Events by use case:")
        for use_case, count in self.global_stats['events_by_use_case'].items():
            print(f"   {use_case}: {count}")
        
        print("\n Camera status:")
        for camera_id, camera_stream in self.camera_streams.items():
            stats = camera_stream.get_stats()
            print(f"   {camera_id}: {stats['connection_status']} | FPS: {stats['current_fps']:.1f} | Events: {stats['events_detected']}")
        
        print("="*80)
    
    def get_camera_stats(self) -> Dict[str, Any]:
        """Get detailed statistics for all cameras"""
        camera_stats = {}
        for camera_id, camera_stream in self.camera_streams.items():
            camera_stats[camera_id] = camera_stream.get_stats()
        
        return {
            'global_stats': self.global_stats,
            'camera_stats': camera_stats,
            'gcp_stats': self.gcp_uploader.get_upload_stats()
        }


# Usage example
def create_sample_camera_config():
    """Create sample camera configuration for 5 cameras"""
    return [
        {
            'camera_id': 'cam_001',
            'name': 'Front Entrance',
            'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
            'use_case': 'people_counting',
            'zones': {'counting': [{'name': 'Entry Zone', 'coordinates': [[100, 100], [500, 100], [500, 400], [100, 400]]}]},
            'rules': {'count_threshold': 10}
        },
        {
            'camera_id': 'cam_002', 
            'name': 'PPE Check Area',
            'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
            'use_case': 'ppe_detection',
            'zones': {'ppe_zone': [{'name': 'PPE Required', 'coordinates': [[200, 200], [600, 200], [600, 500], [200, 500]]}]},
            'rules': {'required_ppe': ['hard_hat', 'safety_vest']}
        },
        {
            'camera_id': 'cam_003',
            'name': 'Secure Entry',
            'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264', 
            'use_case': 'tailgating',
            'zones': {'entry': [{'name': 'Access Control', 'coordinates': [[150, 150], [550, 150], [550, 450], [150, 450]]}]},
            'rules': {'time_limit': 2.0}
        },
        {
            'camera_id': 'cam_004',
            'name': 'Restricted Zone',
            'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
            'use_case': 'intrusion', 
            'zones': {'intrusion': [{'name': 'No Entry Zone', 'coordinates': [[300, 300], [700, 300], [700, 600], [300, 600]]}]},
            'rules': {'alert_immediately': True}
        },
        {
            'camera_id': 'cam_005',
            'name': 'Waiting Area',
            'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
            'use_case': 'loitering',
            'zones': {'loitering': [{'name': 'No Loitering', 'coordinates': [[250, 250], [650, 250], [650, 550], [250, 550]]}]},
            'rules': {'time_threshold': 300}  # 5 minutes
        }
    ]


# Test function
def test_multi_camera_system():
    """Test the multi-camera system"""
    from config.config import Config
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Create processor
    processor = MultiCameraProcessor(Config)
    
    # Load camera configurations
    camera_configs = create_sample_camera_config()
    processor.load_camera_configurations(camera_configs)
    
    # Start processing
    processor.start_processing()


if __name__ == "__main__":
    test_multi_camera_system()