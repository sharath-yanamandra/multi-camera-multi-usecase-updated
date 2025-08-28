# core/flexible_multi_camera_processor.py - NEW FLEXIBLE VERSION
# Supports multiple use cases per camera with easy enable/disable

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

class FlexibleCameraStream:
    """Camera stream that can run multiple use cases with easy enable/disable"""
    
    def __init__(self, camera_config: Dict[str, Any], shared_model: YOLO):
        self.camera_id = camera_config['camera_id']
        self.camera_name = camera_config['name']
        self.stream_url = camera_config['stream_url']
        
        # FLEXIBLE: Multiple use cases with enable/disable status
        self.enabled_use_cases = camera_config.get('enabled_use_cases', [])
        self.available_use_cases = camera_config.get('available_use_cases', [])
        self.zones_config = camera_config.get('zones', {})
        self.rules_config = camera_config.get('rules', {})
        
        # Shared YOLO model (memory efficient)
        self.shared_model = shared_model
        
        # Camera-specific model instances - CREATE ALL, ENABLE SELECTIVELY
        self.camera_models = {}
        self.model_enabled = {}  # Track which models are enabled
        
        self.cap = None
        
        # Processing state
        self.running = False
        self.frame_count = 0
        self.last_processed_time = 0
        
        # Statistics per use case
        self.stats = {
            'frames_processed': 0,
            'events_detected_by_use_case': defaultdict(int),
            'last_fps': 0,
            'connection_status': 'disconnected',
            'enabled_models': []
        }
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Logger
        import logging
        self.logger = logging.getLogger(f'camera_{self.camera_id}')
    
    def initialize(self, db_handler: DatabaseHandler, gcp_uploader: GCPUploader):
        """Initialize camera stream and ALL available models"""
        try:
            self.logger.info(f"Initializing camera {self.camera_id} with flexible use cases")
            
            # Initialize ALL available camera models (even if not enabled yet)
            for use_case in self.available_use_cases:
                if use_case in CAMERA_MODEL_MAPPING:
                    model_class = CAMERA_MODEL_MAPPING[use_case]
                    
                    # Extract zones and rules for this specific use case
                    zones = {use_case: self.zones_config.get(use_case, {})}
                    rules = self.rules_config.get(use_case, {})
                    
                    settings = {
                        'use_case': use_case,
                        'shared_model': self.shared_model,
                        'multi_camera_mode': True,
                        'flexible_mode': True
                    }
                    
                    camera_model = model_class(
                        camera_id=self.camera_id,
                        zones=zones,
                        rules=rules,
                        settings=settings,
                        db=db_handler,
                        db_writer=None,
                        frames_base_dir=f'outputs/frames/camera_{self.camera_id}/{use_case}'
                    )
                    
                    # Enable individual events for each model
                    if hasattr(camera_model, 'set_individual_events_enabled'):
                        camera_model.set_individual_events_enabled(True)
                    
                    self.camera_models[use_case] = camera_model
                    
                    # Set initial enabled status
                    self.model_enabled[use_case] = use_case in self.enabled_use_cases
                    
                    self.logger.info(f"  Initialized {use_case} model ({'ENABLED' if self.model_enabled[use_case] else 'DISABLED'})")
                else:
                    self.logger.error(f"Unknown use case: {use_case}")
            
            # Update stats
            self.stats['enabled_models'] = [uc for uc in self.enabled_use_cases]
            
            self.logger.info(f"Camera {self.camera_id} initialized with {len(self.camera_models)} models, {len(self.enabled_use_cases)} enabled")
            return True
                
        except Exception as e:
            self.logger.error(f"Failed to initialize camera {self.camera_id}: {e}")
            return False
    
    def enable_use_case(self, use_case: str) -> bool:
        """Enable a specific use case for this camera"""
        try:
            with self.lock:
                if use_case in self.camera_models:
                    self.model_enabled[use_case] = True
                    if use_case not in self.enabled_use_cases:
                        self.enabled_use_cases.append(use_case)
                    self.stats['enabled_models'] = [uc for uc in self.enabled_use_cases]
                    self.logger.info(f"✅ ENABLED {use_case} for camera {self.camera_id}")
                    return True
                else:
                    self.logger.error(f"Use case {use_case} not available for camera {self.camera_id}")
                    return False
        except Exception as e:
            self.logger.error(f"Error enabling {use_case}: {e}")
            return False
    
    def disable_use_case(self, use_case: str) -> bool:
        """Disable a specific use case for this camera"""
        try:
            with self.lock:
                if use_case in self.camera_models:
                    self.model_enabled[use_case] = False
                    if use_case in self.enabled_use_cases:
                        self.enabled_use_cases.remove(use_case)
                    self.stats['enabled_models'] = [uc for uc in self.enabled_use_cases]
                    self.logger.info(f"❌ DISABLED {use_case} for camera {self.camera_id}")
                    return True
                else:
                    self.logger.error(f"Use case {use_case} not available for camera {self.camera_id}")
                    return False
        except Exception as e:
            self.logger.error(f"Error disabling {use_case}: {e}")
            return False
    
    def get_enabled_use_cases(self) -> List[str]:
        """Get list of currently enabled use cases"""
        with self.lock:
            return self.enabled_use_cases.copy()
    
    def get_available_use_cases(self) -> List[str]:
        """Get list of all available use cases for this camera"""
        return list(self.camera_models.keys())
    
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
        """Process frame with ALL ENABLED use cases"""
        try:
            if not self.cap or not self.cap.isOpened():
                return False, None
            
            ret, frame = self.cap.read()
            if not ret:
                self.logger.warning(f"Failed to read frame from camera {self.camera_id}")
                return False, None
            
            self.frame_count += 1
            
            # Run YOLO detection ONCE (shared across all models)
            detection_result = self.shared_model(frame, verbose=False)
            
            # Process with ALL ENABLED camera models
            all_events = {}
            annotated_frame = frame.copy()
            total_events = 0
            
            with self.lock:
                enabled_models = {uc: model for uc, model in self.camera_models.items() 
                                if self.model_enabled.get(uc, False)}
            
            for use_case, model in enabled_models.items():
                try:
                    # Process with this specific model
                    model_frame, detections = model.process_frame(
                        frame, 
                        datetime.now(),
                        detection_result
                    )
                    
                    # Collect events from this use case
                    if detections:
                        all_events[use_case] = detections
                        detection_count = len(detections) if isinstance(detections, list) else 1
                        total_events += detection_count
                        self.stats['events_detected_by_use_case'][use_case] += detection_count
                    
                    # For visualization, you could overlay all annotations
                    # but it might be messy with multiple models
                    # annotated_frame = cv2.addWeighted(annotated_frame, 0.8, model_frame, 0.2, 0)
                    
                except Exception as e:
                    self.logger.error(f"Error processing {use_case} for camera {self.camera_id}: {e}")
            
            # Add info overlay showing which models are running
            self._add_status_overlay(annotated_frame, enabled_models.keys(), total_events)
            
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
                'enabled_use_cases': list(enabled_models.keys()),
                'frame_count': self.frame_count,
                'annotated_frame': annotated_frame,
                'all_events': all_events,  # Events from ALL enabled use cases
                'total_events': total_events,
                'timestamp': datetime.now(),
                'has_events': bool(all_events)
            }
            
            return True, result
            
        except Exception as e:
            self.logger.error(f"Frame processing error for camera {self.camera_id}: {e}")
            return False, None
    
    def _add_status_overlay(self, frame, enabled_use_cases, total_events):
        """Add status overlay showing which models are running"""
        try:
            # Status info
            status_text = f"Camera {self.camera_id} | Models: {len(enabled_use_cases)} | Events: {total_events}"
            cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # List enabled models
            models_text = "Active: " + ", ".join([uc.replace('_', ' ').title() for uc in enabled_use_cases])
            cv2.putText(frame, models_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            
        except Exception as e:
            self.logger.error(f"Error adding status overlay: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get camera statistics"""
        with self.lock:
            return {
                'camera_id': self.camera_id,
                'camera_name': self.camera_name,
                'available_use_cases': list(self.camera_models.keys()),
                'enabled_use_cases': self.enabled_use_cases.copy(),
                'connection_status': self.stats['connection_status'],
                'frames_processed': self.stats['frames_processed'],
                'events_by_use_case': dict(self.stats['events_detected_by_use_case']),
                'total_events': sum(self.stats['events_detected_by_use_case'].values()),
                'current_fps': self.stats['last_fps'],
                'frame_count': self.frame_count
            }


class FlexibleMultiCameraProcessor:
    """
    Flexible multi-camera processor with dynamic use case enable/disable
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
        
        # Flexible camera streams
        self.camera_streams = {}  # {camera_id: FlexibleCameraStream}
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
        """Load flexible camera configurations"""
        self.camera_configs = camera_configs
        self.global_stats['total_cameras'] = len(camera_configs)
        
        self.logger.info(f"Loaded {len(camera_configs)} flexible camera configurations")
        
        # Create flexible camera stream instances
        for config in camera_configs:
            camera_stream = FlexibleCameraStream(config, self.shared_model)
            self.camera_streams[config['camera_id']] = camera_stream
            
            enabled_count = len(config.get('enabled_use_cases', []))
            available_count = len(config.get('available_use_cases', []))
            
            self.logger.info(f"Camera {config['camera_id']}: {config['name']} -> {enabled_count}/{available_count} use cases enabled")
    
    def enable_use_case_for_camera(self, camera_id: str, use_case: str) -> bool:
        """Enable a specific use case for a specific camera"""
        if camera_id in self.camera_streams:
            return self.camera_streams[camera_id].enable_use_case(use_case)
        return False
    
    def disable_use_case_for_camera(self, camera_id: str, use_case: str) -> bool:
        """Disable a specific use case for a specific camera"""
        if camera_id in self.camera_streams:
            return self.camera_streams[camera_id].disable_use_case(use_case)
        return False
    
    def get_camera_status(self, camera_id: str) -> Optional[Dict]:
        """Get status of a specific camera"""
        if camera_id in self.camera_streams:
            return self.camera_streams[camera_id].get_stats()
        return None
    
    def get_all_camera_status(self) -> Dict[str, Dict]:
        """Get status of all cameras"""
        status = {}
        for camera_id, camera_stream in self.camera_streams.items():
            status[camera_id] = camera_stream.get_stats()
        return status
    
    def _camera_processing_worker(self, camera_id: str):
        """Worker thread for processing individual camera"""
        camera_stream = self.camera_streams[camera_id]
        self.logger.info(f"Started flexible processing worker for camera {camera_id}")
        
        while self.running:
            try:
                # Process frame
                success, result = camera_stream.process_frame()
                
                if success and result and result['has_events']:
                    # Queue events for saving
                    self.event_queue.put(result)
                    
                    # Update global statistics
                    self.global_stats['total_events'] += result['total_events']
                    self.global_stats['events_by_camera'][camera_id] += result['total_events']
                    
                    for use_case in result['enabled_use_cases']:
                        if use_case in result['all_events']:
                            self.global_stats['events_by_use_case'][use_case] += 1
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"Error in camera {camera_id} worker: {e}")
                time.sleep(1)
        
        # Cleanup
        camera_stream.disconnect()
        self.logger.info(f"Stopped flexible processing worker for camera {camera_id}")
    
    def _save_camera_event(self, result: Dict[str, Any]):
        """Save camera events from all enabled use cases"""
        try:
            camera_id = result['camera_id']
            camera_name = result['camera_name']
            annotated_frame = result['annotated_frame']
            all_events = result['all_events']
            
            # Save events for each use case that generated events
            for use_case, events in all_events.items():
                # Make data JSON serializable
                json_safe_data = self._make_json_serializable({
                    'camera_id': camera_id,
                    'camera_name': camera_name,
                    'use_case': use_case,
                    'events': events,
                    'enabled_use_cases': result['enabled_use_cases'],
                    'timestamp': result['timestamp'].isoformat(),
                    'frame_count': result['frame_count']
                })
                
                # Save to GCP
                local_path, gcp_path = self.gcp_uploader.save_and_upload_event(
                    annotated_frame,
                    f"{use_case}_multi",  # Distinguish from single-use case events
                    camera_id,
                    json_safe_data
                )
                
                # Save to database
                event_id = self.db_handler.save_event(
                    camera_id=camera_id,
                    project_id='flexible-multi-camera-project',
                    event_type=use_case,
                    detection_data=json_safe_data,
                    local_path=local_path,
                    gcp_path=gcp_path,
                    confidence=0.75
                )
                
                if event_id:
                    self.logger.info(f"Event saved: Camera {camera_id} -> {use_case} -> {event_id}")
            
        except Exception as e:
            self.logger.error(f"Error saving camera events: {e}")
    
    def _print_global_stats(self):
        """Print global statistics with flexible use case info"""
        print("\n" + "="*80)
        print(f" FLEXIBLE MULTI-CAMERA PROCESSING STATS")
        print("="*80)
        print(f" Active cameras: {self.global_stats['active_cameras']}/{self.global_stats['total_cameras']}")
        print(f" Total events: {self.global_stats['total_events']}")
        print(f" Pending events: {self.event_queue.qsize()}")
        
        print("\n Camera Status:")
        for camera_id, camera_stream in self.camera_streams.items():
            stats = camera_stream.get_stats()
            enabled_models = ", ".join([uc.replace('_', ' ').title() for uc in stats['enabled_use_cases']])
            print(f"   {camera_id}: {stats['connection_status']} | FPS: {stats['current_fps']:.1f}")
            print(f"      Enabled models: {enabled_models}")
            print(f"      Events: {stats['total_events']} total")
        
        print("\n Events by use case:")
        for use_case, count in self.global_stats['events_by_use_case'].items():
            print(f"   {use_case.replace('_', ' ').title()}: {count}")
        
        print("="*80)
    
    def initialize(self):
        """Initialize the flexible multi-camera processor"""
        self.logger.info("Initializing Flexible Multi-Camera Processor")
        
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
        
        self.logger.info(f"Flexible Multi-Camera Processor initialized: {initialized_cameras}/{len(self.camera_streams)} cameras active")
    
    def _event_saving_worker(self):
        """Worker thread for saving events to database and GCP"""
        self.logger.info("Started event saving worker")
        
        while self.running or not self.event_queue.empty():
            try:
                # Get event from queue (with timeout)
                result = self.event_queue.get(timeout=1.0)
                
                # Save event using existing logic
                self._save_camera_event(result)
                
                # Mark task as done
                self.event_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error saving event: {e}")
        
        self.logger.info("Stopped event saving worker")
    
    def _make_json_serializable(self, obj):
        """Make object JSON serializable"""
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
        """Start flexible multi-camera processing"""
        self.logger.info("Starting flexible multi-camera processing...")
        
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
        
        self.logger.info(f"Started flexible processing for {len(self.processing_threads)} cameras")
        
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
        """Stop flexible multi-camera processing"""
        self.logger.info("Stopping flexible multi-camera processing...")
        
        # Stop processing
        self.running = False
        
        # Wait for worker threads to finish
        for camera_id, thread in self.processing_threads.items():
            self.logger.info(f"Waiting for camera {camera_id} worker to finish...")
            thread.join(timeout=5.0)
        
        # Wait for event queue to empty
        self.logger.info("Waiting for pending events to be saved...")
        try:
            self.event_queue.join()
        except:
            pass
        
        # Cleanup resources
        self.gcp_uploader.stop()
        self.db_handler.disconnect()
        
        self.logger.info("Flexible multi-camera processing stopped")
    
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


# Sample flexible camera configuration
def create_flexible_camera_config():
    """Create sample flexible camera configuration"""
    return [
        {
            'camera_id': 'cam_001',
            'name': 'Main Entrance - All Models',
            'stream_url': 'rtsp://admin:password@192.168.29.213:554/ch0_0.264',
            
            # ALL use cases available, ALL enabled
            'available_use_cases': ['people_counting', 'ppe_detection', 'tailgating', 'intrusion', 'loitering'],
            'enabled_use_cases': ['people_counting', 'ppe_detection', 'tailgating', 'intrusion', 'loitering'],
            
            'zones': {
                'people_counting': {'counting': [{'name': 'Entry Zone', 'coordinates': [[100, 100], [500, 100], [500, 400], [100, 400]]}]},
                'ppe_detection': {'ppe_zone': [{'name': 'PPE Required', 'coordinates': [[200, 200], [600, 200], [600, 500], [200, 500]]}]},
                'tailgating': {'entry': [{'name': 'Access Control', 'coordinates': [[150, 150], [550, 150], [550, 450], [150, 450]]}]},
                'intrusion': {'intrusion': [{'name': 'Restricted', 'coordinates': [[300, 300], [700, 300], [700, 600], [300, 600]]}]},
                'loitering': {'loitering': [{'name': 'No Loitering', 'coordinates': [[250, 250], [650, 250], [650, 550], [250, 550]]}]}
            },
            'rules': {
                'people_counting': {'count_threshold': 0, 'confidence_threshold': 0.3},
                'ppe_detection': {'required_ppe': ['hard_hat', 'safety_vest'], 'confidence_threshold': 0.3},
                'tailgating': {'time_limit': 2.0, 'confidence_threshold': 0.3},
                'intrusion': {'alert_immediately': True, 'confidence_threshold': 0.3},
                'loitering': {'time_threshold': 300, 'confidence_threshold': 0.3}
            }
        },
        {
            'camera_id': 'cam_002',
            'name': 'Workshop - Selected Models',
            'stream_url': 'rtsp://admin:password@192.168.1.102:554/ch0_0.264',
            
            # Only some use cases available and enabled
            'available_use_cases': ['people_counting', 'ppe_detection', 'intrusion'],
            'enabled_use_cases': ['ppe_detection', 'intrusion'],  # Only 2 enabled initially
            
            'zones': {
                'people_counting': {'counting': [{'name': 'Workshop Entry', 'coordinates': [[100, 100], [500, 100], [500, 400], [100, 400]]}]},
                'ppe_detection': {'ppe_zone': [{'name': 'Work Area', 'coordinates': [[200, 200], [600, 200], [600, 500], [200, 500]]}]},
                'intrusion': {'intrusion': [{'name': 'Equipment Zone', 'coordinates': [[300, 300], [700, 300], [700, 600], [300, 600]]}]}
            },
            'rules': {
                'people_counting': {'count_threshold': 0, 'confidence_threshold': 0.3},
                'ppe_detection': {'required_ppe': ['hard_hat', 'safety_vest'], 'confidence_threshold': 0.3},
                'intrusion': {'alert_immediately': True, 'confidence_threshold': 0.3}
            }
        }
    ]