# api/multi_camera_api.py
"""
Multi-Camera Monitoring System API Endpoints
FastAPI-based REST API for camera management and monitoring
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import json
import os
import sys
import logging
import asyncio
from pathlib import Path
import uuid

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your existing modules
from core.database_handler import DatabaseHandler
from core.gcp_uploader import GCPUploader
from core.flexible_multi_camera_processor import FlexibleMultiCameraProcessor
from config.multi_camera_config import MultiCameraConfig
from interface.flexible_camera_management import FlexibleCameraConfigurationManager
from logger import setup_datacenter_logger

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Camera Monitoring System API",
    description="API for managing cameras, use cases, and monitoring events",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for system components
processor: Optional[FlexibleMultiCameraProcessor] = None
config_manager: Optional[FlexibleCameraConfigurationManager] = None
logger = setup_datacenter_logger('multi_camera_api', 'api.log')

# Initialize database and components
def get_database():
    """Get database handler instance"""
    return DatabaseHandler({
        'host': MultiCameraConfig.MYSQL_HOST,
        'user': MultiCameraConfig.MYSQL_USER,
        'password': MultiCameraConfig.MYSQL_PASSWORD,
        'database': MultiCameraConfig.MYSQL_DATABASE,
        'port': MultiCameraConfig.MYSQL_PORT
    })

def get_gcp_uploader():
    """Get GCP uploader instance"""
    return GCPUploader(
        MultiCameraConfig.GCP_CREDENTIALS_PATH,
        MultiCameraConfig.GCP_BUCKET_NAME,
        MultiCameraConfig.GCP_PROJECT_ID
    )

# Pydantic models for API requests/responses
class CameraCreate(BaseModel):
    name: str = Field(..., description="Camera name")
    stream_url: str = Field(..., description="RTSP stream URL")
    location: str = Field(..., description="Camera location")
    description: str = Field("", description="Camera description")
    available_use_cases: List[str] = Field(
        default=["people_counting", "ppe_detection", "tailgating", "intrusion", "loitering"],
        description="Available use cases for this camera"
    )
    enabled_use_cases: List[str] = Field(..., description="Initially enabled use cases")
    zones: Dict[str, Any] = Field(default={}, description="Zone configurations")
    rules: Dict[str, Any] = Field(default={}, description="Processing rules")

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    stream_url: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    available_use_cases: Optional[List[str]] = None
    enabled_use_cases: Optional[List[str]] = None
    zones: Optional[Dict[str, Any]] = None
    rules: Optional[Dict[str, Any]] = None
    status: Optional[str] = None

class CameraResponse(BaseModel):
    camera_id: str
    name: str
    stream_url: str
    location: str
    description: str
    available_use_cases: List[str]
    enabled_use_cases: List[str]
    zones: Dict[str, Any]
    rules: Dict[str, Any]
    status: str
    connection_status: Optional[str] = None
    last_seen: Optional[datetime] = None
    stats: Optional[Dict[str, Any]] = None

class UseCaseToggle(BaseModel):
    use_case: str
    enabled: bool

class EventFilter(BaseModel):
    camera_id: Optional[str] = None
    event_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    severity: Optional[str] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)

class SystemStats(BaseModel):
    total_cameras: int
    active_cameras: int
    total_events_today: int
    events_by_type: Dict[str, int]
    system_uptime: str
    avg_fps: float
    storage_usage: Dict[str, Any]

# API Endpoints

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    global config_manager
    try:
        config_manager = FlexibleCameraConfigurationManager()
        logger.info("Multi-Camera API started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize API: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global processor
    if processor:
        try:
            processor.stop()
        except:
            pass
    logger.info("Multi-Camera API shutdown")

# Health Check Endpoint
@app.get("/health")
async def health_check():
    """System health check"""
    try:
        # Test database connection
        db = get_database()
        db_status = "connected" if db.connect() else "disconnected"
        if db_status == "connected":
            db.disconnect()
        
        # Test GCP connection
        gcp_uploader = get_gcp_uploader()
        gcp_status = "connected" if gcp_uploader.test_connection() else "disconnected"
        gcp_uploader.stop()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": db_status,
            "gcp_storage": gcp_status,
            "processor_running": processor is not None and processor.running if processor else False
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# Camera Management Endpoints
@app.get("/api/cameras", response_model=List[CameraResponse])
async def get_cameras():
    """Get all cameras with their configurations and status"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        cameras = []
        for config in config_manager.configurations:
            camera_stats = None
            if processor:
                camera_stats = processor.get_camera_status(config['camera_id'])
            
            camera_response = CameraResponse(
                camera_id=config['camera_id'],
                name=config['name'],
                stream_url=config['stream_url'],
                location=config.get('location', ''),
                description=config.get('description', ''),
                available_use_cases=config.get('available_use_cases', []),
                enabled_use_cases=config.get('enabled_use_cases', []),
                zones=config.get('zones', {}),
                rules=config.get('rules', {}),
                status=config.get('status', 'inactive'),
                connection_status=camera_stats.get('connection_status') if camera_stats else None,
                stats=camera_stats
            )
            cameras.append(camera_response)
        
        return cameras
    except Exception as e:
        logger.error(f"Error getting cameras: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cameras/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str):
    """Get specific camera details"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        # Find camera in configurations
        camera_config = None
        for config in config_manager.configurations:
            if config['camera_id'] == camera_id:
                camera_config = config
                break
        
        if not camera_config:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        
        # Get real-time stats if processor is running
        camera_stats = None
        if processor:
            camera_stats = processor.get_camera_status(camera_id)
        
        return CameraResponse(
            camera_id=camera_config['camera_id'],
            name=camera_config['name'],
            stream_url=camera_config['stream_url'],
            location=camera_config.get('location', ''),
            description=camera_config.get('description', ''),
            available_use_cases=camera_config.get('available_use_cases', []),
            enabled_use_cases=camera_config.get('enabled_use_cases', []),
            zones=camera_config.get('zones', {}),
            rules=camera_config.get('rules', {}),
            status=camera_config.get('status', 'inactive'),
            connection_status=camera_stats.get('connection_status') if camera_stats else None,
            stats=camera_stats
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cameras", response_model=CameraResponse)
async def create_camera(camera: CameraCreate):
    """Create a new camera configuration"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        # Generate new camera ID
        existing_ids = [config['camera_id'] for config in config_manager.configurations]
        new_id = f"cam_{len(existing_ids) + 1:03d}"
        
        # Create camera configuration
        new_camera_config = {
            'camera_id': new_id,
            'name': camera.name,
            'stream_url': camera.stream_url,
            'location': camera.location,
            'description': camera.description,
            'available_use_cases': camera.available_use_cases,
            'enabled_use_cases': camera.enabled_use_cases,
            'zones': camera.zones if camera.zones else config_manager._get_zones_for_use_cases(camera.available_use_cases),
            'rules': camera.rules if camera.rules else config_manager._get_rules_for_use_cases(camera.available_use_cases),
            'status': 'inactive'
        }
        
        # Add to configurations
        config_manager.configurations.append(new_camera_config)
        config_manager.save_configurations()
        
        logger.info(f"Created new camera: {new_id}")
        
        return CameraResponse(**new_camera_config)
    except Exception as e:
        logger.error(f"Error creating camera: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/cameras/{camera_id}", response_model=CameraResponse)
async def update_camera(camera_id: str, camera_update: CameraUpdate):
    """Update camera configuration"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        # Find and update camera
        camera_config = None
        for i, config in enumerate(config_manager.configurations):
            if config['camera_id'] == camera_id:
                camera_config = config
                break
        
        if not camera_config:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        
        # Update fields
        update_data = camera_update.dict(exclude_unset=True)
        camera_config.update(update_data)
        
        # Save configuration
        config_manager.save_configurations()
        
        logger.info(f"Updated camera: {camera_id}")
        
        return CameraResponse(**camera_config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/cameras/{camera_id}")
async def delete_camera(camera_id: str):
    """Delete camera configuration"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        # Find and remove camera
        for i, config in enumerate(config_manager.configurations):
            if config['camera_id'] == camera_id:
                removed_config = config_manager.configurations.pop(i)
                config_manager.save_configurations()
                logger.info(f"Deleted camera: {camera_id}")
                return {"message": f"Camera {camera_id} deleted successfully"}
        
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Use Case Management Endpoints
@app.post("/api/cameras/{camera_id}/use-cases")
async def toggle_use_case(camera_id: str, use_case_toggle: UseCaseToggle):
    """Enable or disable a specific use case for a camera"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        # Find camera
        camera_config = None
        for config in config_manager.configurations:
            if config['camera_id'] == camera_id:
                camera_config = config
                break
        
        if not camera_config:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        
        use_case = use_case_toggle.use_case
        enabled = use_case_toggle.enabled
        
        # Update use case status
        if enabled:
            if use_case not in camera_config['enabled_use_cases']:
                camera_config['enabled_use_cases'].append(use_case)
            if use_case not in camera_config['available_use_cases']:
                camera_config['available_use_cases'].append(use_case)
        else:
            if use_case in camera_config['enabled_use_cases']:
                camera_config['enabled_use_cases'].remove(use_case)
        
        # Update processor if running
        if processor:
            if enabled:
                processor.enable_use_case_for_camera(camera_id, use_case)
            else:
                processor.disable_use_case_for_camera(camera_id, use_case)
        
        # Save configuration
        config_manager.save_configurations()
        
        action = "enabled" if enabled else "disabled"
        logger.info(f"Use case {use_case} {action} for camera {camera_id}")
        
        return {
            "message": f"Use case {use_case} {action} for camera {camera_id}",
            "camera_id": camera_id,
            "use_case": use_case,
            "enabled": enabled
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling use case for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/use-cases")
async def get_available_use_cases():
    """Get all available use cases"""
    return {
        "use_cases": [
            {
                "id": "people_counting",
                "name": "People Counting",
                "description": "Count people in designated zones"
            },
            {
                "id": "ppe_detection",
                "name": "PPE Detection",
                "description": "Detect Personal Protective Equipment compliance"
            },
            {
                "id": "tailgating",
                "name": "Tailgating Detection",
                "description": "Detect unauthorized following through access points"
            },
            {
                "id": "intrusion",
                "name": "Intrusion Detection",
                "description": "Detect unauthorized access to restricted areas"
            },
            {
                "id": "loitering",
                "name": "Loitering Detection",
                "description": "Detect people staying in areas for too long"
            }
        ]
    }

# System Control Endpoints
@app.post("/api/system/start")
async def start_system(background_tasks: BackgroundTasks):
    """Start the multi-camera processing system"""
    try:
        global processor
        
        if processor and processor.running:
            return {"message": "System is already running"}
        
        if not config_manager or not config_manager.configurations:
            raise HTTPException(status_code=400, detail="No camera configurations found")
        
        # Create and start processor
        processor = FlexibleMultiCameraProcessor(MultiCameraConfig)
        processor.load_camera_configurations(config_manager.configurations)
        
        # Start processing in background
        background_tasks.add_task(start_processing_background)
        
        logger.info("Multi-camera system start initiated")
        return {"message": "System starting...", "cameras": len(config_manager.configurations)}
        
    except Exception as e:
        logger.error(f"Error starting system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def start_processing_background():
    """Background task to start processing"""
    try:
        if processor:
            processor.start_processing()
    except Exception as e:
        logger.error(f"Error in background processing: {e}")

@app.post("/api/system/stop")
async def stop_system():
    """Stop the multi-camera processing system"""
    try:
        global processor
        
        if not processor or not processor.running:
            return {"message": "System is not running"}
        
        processor.stop()
        processor = None
        
        logger.info("Multi-camera system stopped")
        return {"message": "System stopped successfully"}
        
    except Exception as e:
        logger.error(f"Error stopping system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/status")
async def get_system_status():
    """Get current system status"""
    try:
        global processor
        
        is_running = processor is not None and processor.running if processor else False
        
        stats = {
            "running": is_running,
            "timestamp": datetime.now().isoformat(),
            "cameras": [],
            "total_events": 0
        }
        
        if processor and is_running:
            camera_stats = processor.get_all_camera_status()
            stats.update(processor.get_camera_stats())
            stats["cameras"] = camera_stats
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Event Management Endpoints
@app.get("/api/events")
async def get_events(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(100, le=1000, description="Limit number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get events with optional filtering"""
    try:
        db = get_database()
        if not db.connect():
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Build query
        query = """
            SELECT 
                event_id, camera_id, event_type, severity, timestamp,
                detection_data, local_image_path, gcp_image_path,
                confidence_score, status
            FROM events 
            WHERE 1=1
        """
        params = []
        
        if camera_id:
            query += " AND camera_id = %s"
            params.append(camera_id)
        
        if event_type:
            query += " AND event_type = %s"
            params.append(event_type)
        
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        if severity:
            query += " AND severity = %s"
            params.append(severity)
        
        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        events = db.execute_query(query, tuple(params))
        db.disconnect()
        
        if not events:
            return []
        
        # Process events
        processed_events = []
        for event in events:
            try:
                detection_data = json.loads(event['detection_data']) if event['detection_data'] else {}
            except:
                detection_data = {}
            
            processed_events.append({
                "event_id": event['event_id'],
                "camera_id": event['camera_id'],
                "event_type": event['event_type'],
                "severity": event['severity'],
                "timestamp": event['timestamp'].isoformat() if event['timestamp'] else None,
                "detection_data": detection_data,
                "local_image_path": event['local_image_path'],
                "gcp_image_path": event['gcp_image_path'],
                "confidence_score": event['confidence_score'],
                "status": event['status']
            })
        
        return processed_events
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events/{event_id}")
async def get_event(event_id: str):
    """Get specific event details"""
    try:
        db = get_database()
        if not db.connect():
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        query = """
            SELECT 
                event_id, camera_id, event_type, severity, timestamp,
                detection_data, local_image_path, gcp_image_path,
                confidence_score, status
            FROM events 
            WHERE event_id = %s
        """
        
        events = db.execute_query(query, (event_id,))
        db.disconnect()
        
        if not events:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        
        event = events[0]
        try:
            detection_data = json.loads(event['detection_data']) if event['detection_data'] else {}
        except:
            detection_data = {}
        
        return {
            "event_id": event['event_id'],
            "camera_id": event['camera_id'],
            "event_type": event['event_type'],
            "severity": event['severity'],
            "timestamp": event['timestamp'].isoformat() if event['timestamp'] else None,
            "detection_data": detection_data,
            "local_image_path": event['local_image_path'],
            "gcp_image_path": event['gcp_image_path'],
            "confidence_score": event['confidence_score'],
            "status": event['status']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events/{event_id}/image")
async def get_event_image(event_id: str):
    """Get event image file"""
    try:
        db = get_database()
        if not db.connect():
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        query = "SELECT local_image_path FROM events WHERE event_id = %s"
        events = db.execute_query(query, (event_id,))
        db.disconnect()
        
        if not events or not events[0]['local_image_path']:
            raise HTTPException(status_code=404, detail="Event image not found")
        
        image_path = events[0]['local_image_path']
        
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image file not found on disk")
        
        return FileResponse(
            image_path,
            media_type='image/jpeg',
            filename=f"event_{event_id}.jpg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event image {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Statistics Endpoints
@app.get("/api/stats/dashboard", response_model=SystemStats)
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        db = get_database()
        if not db.connect():
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Get total cameras
        total_cameras = len(config_manager.configurations) if config_manager else 0
        active_cameras = 0
        
        if processor:
            camera_stats = processor.get_all_camera_status()
            active_cameras = sum(1 for stats in camera_stats.values() 
                               if stats.get('connection_status') == 'connected')
        
        # Get today's events
        today = datetime.now().date()
        events_query = """
            SELECT event_type, COUNT(*) as count
            FROM events 
            WHERE DATE(timestamp) = %s
            GROUP BY event_type
        """
        
        events = db.execute_query(events_query, (today,))
        db.disconnect()
        
        events_by_type = {}
        total_events_today = 0
        
        if events:
            for event in events:
                events_by_type[event['event_type']] = event['count']
                total_events_today += event['count']
        
        # Get system stats
        avg_fps = 0.0
        if processor:
            system_stats = processor.get_camera_stats()
            avg_fps = sum(camera.get('current_fps', 0) for camera in system_stats.get('camera_stats', {}).values()) / max(1, active_cameras)
        
        # Storage usage (simplified)
        storage_usage = {
            "total_gb": 100,
            "used_gb": 45,
            "free_gb": 55,
            "usage_percentage": 45
        }
        
        return SystemStats(
            total_cameras=total_cameras,
            active_cameras=active_cameras,
            total_events_today=total_events_today,
            events_by_type=events_by_type,
            system_uptime="2h 30m",  # You can calculate actual uptime
            avg_fps=avg_fps,
            storage_usage=storage_usage
        )
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/events")
async def get_event_stats(
    days: int = Query(7, description="Number of days to include in stats"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID")
):
    """Get event statistics over time"""
    try:
        db = get_database()
        if not db.connect():
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Build query for event stats
        query = """
            SELECT 
                DATE(timestamp) as date,
                event_type,
                COUNT(*) as count
            FROM events 
            WHERE timestamp >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        """
        params = [days]
        
        if camera_id:
            query += " AND camera_id = %s"
            params.append(camera_id)
        
        query += " GROUP BY DATE(timestamp), event_type ORDER BY date DESC"
        
        stats = db.execute_query(query, tuple(params))
        db.disconnect()
        
        # Process stats for frontend
        result = {
            "period_days": days,
            "camera_id": camera_id,
            "daily_stats": {},
            "total_by_type": {}
        }
        
        if stats:
            for stat in stats:
                date_str = stat['date'].strftime('%Y-%m-%d')
                event_type = stat['event_type']
                count = stat['count']
                
                if date_str not in result["daily_stats"]:
                    result["daily_stats"][date_str] = {}
                
                result["daily_stats"][date_str][event_type] = count
                
                if event_type not in result["total_by_type"]:
                    result["total_by_type"][event_type] = 0
                result["total_by_type"][event_type] += count
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting event stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuration Endpoints
@app.get("/api/config/export")
async def export_configuration():
    """Export current system configuration"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        config_data = {
            "cameras": config_manager.configurations,
            "system_config": {
                "detection_model": MultiCameraConfig.DETECTION_MODEL_PATH,
                "ppe_model": MultiCameraConfig.PPE_DETECTION_MODEL_PATH,
                "pose_model": MultiCameraConfig.POSE_ESTIMATION_MODEL_PATH,
                "confidence_threshold": MultiCameraConfig.DETECTION_CONFIDENCE_THRESHOLD,
                "gcp_bucket": MultiCameraConfig.GCP_BUCKET_NAME
            },
            "exported_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        return JSONResponse(
            content=config_data,
            headers={
                "Content-Disposition": f"attachment; filename=camera_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/import")
async def import_configuration(config_data: Dict[str, Any]):
    """Import system configuration"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        if "cameras" not in config_data:
            raise HTTPException(status_code=400, detail="Invalid configuration format")
        
        # Validate camera configurations
        cameras = config_data["cameras"]
        for camera in cameras:
            required_fields = ["camera_id", "name", "stream_url"]
            for field in required_fields:
                if field not in camera:
                    raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Update configurations
        config_manager.configurations = cameras
        config_manager.save_configurations()
        
        logger.info(f"Imported {len(cameras)} camera configurations")
        return {
            "message": f"Successfully imported {len(cameras)} camera configurations",
            "cameras_imported": len(cameras)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Template Management Endpoints
@app.get("/api/templates")
async def get_templates():
    """Get available camera configuration templates"""
    templates = {
        "entrance_monitoring": {
            "name": "Entrance Monitoring",
            "description": "Optimized for main entrances with people counting and tailgating detection",
            "use_cases": ["people_counting", "tailgating"],
            "zones": {
                "people_counting": {"counting": [{"name": "Entry Count Zone", "coordinates": [[200, 200], [800, 200], [800, 600], [200, 600]]}]},
                "tailgating": {"entry": [{"name": "Access Control", "coordinates": [[250, 300], [750, 300], [750, 650], [250, 650]]}]}
            },
            "rules": {
                "people_counting": {"count_threshold": 0, "confidence_threshold": 0.3},
                "tailgating": {"time_limit": 2.0, "confidence_threshold": 0.3}
            }
        },
        "server_room_security": {
            "name": "Server Room Security",
            "description": "High-security monitoring for server rooms with PPE and intrusion detection",
            "use_cases": ["ppe_detection", "intrusion"],
            "zones": {
                "ppe_detection": {"ppe_zone": [{"name": "PPE Required Zone", "coordinates": [[300, 250], [900, 250], [900, 700], [300, 700]]}]},
                "intrusion": {"intrusion": [{"name": "Server Area", "coordinates": [[500, 200], [1200, 200], [1200, 800], [500, 800]]}]}
            },
            "rules": {
                "ppe_detection": {"required_ppe": ["hard_hat", "safety_vest"], "confidence_threshold": 0.3},
                "intrusion": {"alert_immediately": True, "confidence_threshold": 0.3}
            }
        },
        "workspace_monitoring": {
            "name": "Workspace Monitoring",
            "description": "General workspace monitoring with occupancy and loitering detection",
            "use_cases": ["people_counting", "loitering"],
            "zones": {
                "people_counting": {"counting": [{"name": "Workspace", "coordinates": [[100, 100], [600, 100], [600, 500], [100, 500]]}]},
                "loitering": {"loitering": [{"name": "No Loitering Zone", "coordinates": [[400, 350], [1000, 350], [1000, 750], [400, 750]]}]}
            },
            "rules": {
                "people_counting": {"count_threshold": 0, "confidence_threshold": 0.3},
                "loitering": {"time_threshold": 300, "confidence_threshold": 0.3}
            }
        },
        "comprehensive_monitoring": {
            "name": "Comprehensive Monitoring",
            "description": "Full monitoring solution with all available use cases",
            "use_cases": ["people_counting", "ppe_detection", "tailgating", "intrusion", "loitering"],
            "zones": {
                "people_counting": {"counting": [{"name": "Count Zone", "coordinates": [[200, 200], [800, 200], [800, 600], [200, 600]]}]},
                "ppe_detection": {"ppe_zone": [{"name": "PPE Zone", "coordinates": [[300, 250], [900, 250], [900, 700], [300, 700]]}]},
                "tailgating": {"entry": [{"name": "Entry Control", "coordinates": [[250, 300], [750, 300], [750, 650], [250, 650]]}]},
                "intrusion": {"intrusion": [{"name": "Restricted", "coordinates": [[500, 200], [1200, 200], [1200, 800], [500, 800]]}]},
                "loitering": {"loitering": [{"name": "No Loitering", "coordinates": [[400, 350], [1000, 350], [1000, 750], [400, 750]]}]}
            },
            "rules": {
                "people_counting": {"count_threshold": 0, "confidence_threshold": 0.3},
                "ppe_detection": {"required_ppe": ["hard_hat", "safety_vest"], "confidence_threshold": 0.3},
                "tailgating": {"time_limit": 2.0, "confidence_threshold": 0.3},
                "intrusion": {"alert_immediately": True, "confidence_threshold": 0.3},
                "loitering": {"time_threshold": 300, "confidence_threshold": 0.3}
            }
        }
    }
    
    return {"templates": templates}

@app.post("/api/templates/{template_id}/apply")
async def apply_template(template_id: str, camera_ids: Optional[List[str]] = None):
    """Apply a template to specific cameras or all cameras"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        # Get template
        templates_response = await get_templates()
        templates = templates_response["templates"]
        
        if template_id not in templates:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        
        template = templates[template_id]
        
        # Determine which cameras to update
        cameras_to_update = []
        if camera_ids:
            for camera_id in camera_ids:
                camera_config = None
                for config in config_manager.configurations:
                    if config['camera_id'] == camera_id:
                        camera_config = config
                        break
                if camera_config:
                    cameras_to_update.append(camera_config)
                else:
                    raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        else:
            cameras_to_update = config_manager.configurations
        
        # Apply template
        updated_cameras = []
        for camera_config in cameras_to_update:
            camera_config.update({
                "available_use_cases": template["use_cases"],
                "enabled_use_cases": template["use_cases"],
                "zones": template["zones"],
                "rules": template["rules"]
            })
            updated_cameras.append(camera_config['camera_id'])
        
        # Save configuration
        config_manager.save_configurations()
        
        logger.info(f"Applied template {template_id} to {len(updated_cameras)} cameras")
        
        return {
            "message": f"Template {template_id} applied successfully",
            "template_name": template["name"],
            "cameras_updated": updated_cameras,
            "use_cases_applied": template["use_cases"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Batch Operations Endpoints
@app.post("/api/cameras/batch/start")
async def start_cameras(camera_ids: Optional[List[str]] = None):
    """Start multiple cameras"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        cameras_to_start = camera_ids if camera_ids else [config['camera_id'] for config in config_manager.configurations]
        
        updated_cameras = []
        for camera_id in cameras_to_start:
            for config in config_manager.configurations:
                if config['camera_id'] == camera_id:
                    config['status'] = 'active'
                    updated_cameras.append(camera_id)
                    break
        
        config_manager.save_configurations()
        
        return {
            "message": f"Started {len(updated_cameras)} cameras",
            "cameras_started": updated_cameras
        }
        
    except Exception as e:
        logger.error(f"Error starting cameras: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cameras/batch/stop")
async def stop_cameras(camera_ids: Optional[List[str]] = None):
    """Stop multiple cameras"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not initialized")
        
        cameras_to_stop = camera_ids if camera_ids else [config['camera_id'] for config in config_manager.configurations]
        
        updated_cameras = []
        for camera_id in cameras_to_stop:
            for config in config_manager.configurations:
                if config['camera_id'] == camera_id:
                    config['status'] = 'inactive'
                    updated_cameras.append(camera_id)
                    break
        
        config_manager.save_configurations()
        
        return {
            "message": f"Stopped {len(updated_cameras)} cameras",
            "cameras_stopped": updated_cameras
        }
        
    except Exception as e:
        logger.error(f"Error stopping cameras: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Real-time WebSocket endpoint (optional)
@app.websocket("/ws/events")
async def websocket_events_endpoint(websocket):
    """WebSocket endpoint for real-time event streaming"""
    await websocket.accept()
    try:
        while True:
            # In a real implementation, you would stream events as they occur
            # For now, this is a placeholder
            await asyncio.sleep(1)
            
            # Send dummy event data
            event_data = {
                "type": "event_update",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "camera_id": "cam_001",
                    "event_type": "people_counting",
                    "count": 3
                }
            }
            await websocket.send_json(event_data)
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()

# Log Management Endpoints
@app.get("/api/logs")
async def get_logs(
    level: Optional[str] = Query(None, description="Log level filter"),
    component: Optional[str] = Query(None, description="Component filter"),
    limit: int = Query(100, le=1000, description="Number of log entries"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get system logs"""
    try:
        logs_dir = Path("logs")
        log_files = list(logs_dir.glob("*.log"))
        
        if not log_files:
            return {"logs": [], "total": 0}
        
        # For simplicity, read from main log file
        main_log_file = logs_dir / "multi_camera_system.log"
        
        if not main_log_file.exists():
            return {"logs": [], "total": 0}
        
        logs = []
        with open(main_log_file, 'r') as f:
            lines = f.readlines()
            
            # Apply filters and pagination
            filtered_lines = lines[-limit-offset:-offset] if offset > 0 else lines[-limit:]
            
            for line in reversed(filtered_lines):
                if line.strip():
                    # Parse log line (simplified)
                    parts = line.strip().split(' - ', 3)
                    if len(parts) >= 4:
                        logs.append({
                            "timestamp": parts[0],
                            "component": parts[1],
                            "level": parts[2],
                            "message": parts[3]
                        })
        
        return {
            "logs": logs,
            "total": len(lines),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Error Handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found", "detail": str(exc.detail) if hasattr(exc, 'detail') else "Not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"}
    )

# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    # Load configuration manager
    config_manager = FlexibleCameraConfigurationManager()
    
    logger.info("Starting Multi-Camera API server...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False  # Set to True for development
    )