#!/usr/bin/env python3
# check_database.py - Check database status and table updates

import sys
import os
from datetime import datetime, timedelta

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_database_status():
    """Check database tables and their status"""
    try:
        from core.database_handler import DatabaseHandler
        from config.config import Config
        
        print("Multi-Camera System Database Status Check")
        print("=" * 50)
        
        # Connect to database
        db = DatabaseHandler({
            'host': Config.MYSQL_HOST,
            'user': Config.MYSQL_USER,
            'password': Config.MYSQL_PASSWORD,
            'database': Config.MYSQL_DATABASE,
            'port': Config.MYSQL_PORT
        })
        
        if not db.connect():
            print("❌ Database connection failed")
            return False
        
        print(f"✅ Connected to database: {Config.MYSQL_DATABASE}")
        print(f"   Host: {Config.MYSQL_HOST}:{Config.MYSQL_PORT}")
        print()
        
        # Check if required tables exist
        required_tables = ['users', 'projects', 'cameras', 'events', 'processing_stats']
        
        print("📋 Checking Required Tables:")
        print("-" * 30)
        
        all_tables_exist = True
        for table in required_tables:
            try:
                result = db.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                if result:
                    count = result[0]['count']
                    print(f"✅ {table}: {count} rows")
                else:
                    print(f"❌ {table}: Query failed")
                    all_tables_exist = False
            except Exception as e:
                print(f"❌ {table}: Does not exist ({e})")
                all_tables_exist = False
        
        if not all_tables_exist:
            print("\n⚠️  Some required tables are missing!")
            print("   Run: python fix_database.py")
            return False
        
        # Show table details
        print("\n📊 Table Details:")
        print("-" * 30)
        
        # Projects
        projects = db.execute_query("SELECT * FROM projects")
        if projects:
            for project in projects:
                print(f"Project: {project['name']} ({project['project_id']})")
                print(f"  Status: {project['status']}")
                print(f"  Location: {project.get('location', 'N/A')}")
        
        # Cameras
        cameras = db.execute_query("SELECT * FROM cameras")
        if cameras:
            print(f"\n📹 Cameras ({len(cameras)} total):")
            for camera in cameras:
                print(f"  {camera['camera_id']}: {camera['name']}")
                print(f"    URL: {camera['stream_url']}")
                print(f"    Status: {camera['status']}")
                print(f"    Connection: {camera.get('connection_status', 'unknown')}")
                print(f"    Use Case: {camera.get('primary_use_case', 'N/A')}")
        
        # Recent events
        print(f"\n🎯 Recent Events (last 24 hours):")
        recent_events = db.execute_query("""
            SELECT event_type, camera_id, severity, timestamp, confidence_score 
            FROM events 
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ORDER BY timestamp DESC 
            LIMIT 10
        """)
        
        if recent_events:
            for event in recent_events:
                timestamp = event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                confidence = f"{event['confidence_score']:.2f}" if event['confidence_score'] else "N/A"
                print(f"  {timestamp}: {event['event_type']} ({event['camera_id']}) - {event['severity']} - conf: {confidence}")
        else:
            print("  No events found in last 24 hours")
        
        # Event statistics
        print(f"\n📈 Event Statistics:")
        event_stats = db.execute_query("""
            SELECT 
                event_type,
                COUNT(*) as count,
                MAX(timestamp) as latest
            FROM events 
            GROUP BY event_type 
            ORDER BY count DESC
        """)
        
        if event_stats:
            total_events = sum(stat['count'] for stat in event_stats)
            print(f"  Total Events: {total_events}")
            for stat in event_stats:
                latest = stat['latest'].strftime('%Y-%m-%d %H:%M:%S') if stat['latest'] else 'Never'
                print(f"  {stat['event_type']}: {stat['count']} events (latest: {latest})")
        else:
            print("  No events recorded yet")
        
        # Processing stats
        print(f"\n⚡ Processing Statistics:")
        proc_stats = db.execute_query("""
            SELECT 
                camera_id,
                SUM(frames_processed) as total_frames,
                SUM(total_detections) as total_detections,
                MAX(timestamp) as last_update
            FROM processing_stats 
            GROUP BY camera_id
        """)
        
        if proc_stats:
            for stat in proc_stats:
                last_update = stat['last_update'].strftime('%Y-%m-%d %H:%M:%S') if stat['last_update'] else 'Never'
                print(f"  {stat['camera_id']}: {stat['total_frames']} frames, {stat['total_detections']} detections (updated: {last_update})")
        else:
            print("  No processing statistics recorded yet")
        
        # Database health check
        print(f"\n🏥 Database Health:")
        try:
            # Check database version
            version = db.execute_query("SELECT VERSION() as version")
            if version:
                print(f"  MySQL Version: {version[0]['version']}")
            
            # Check table sizes
            table_sizes = db.execute_query(f"""
                SELECT 
                    table_name,
                    table_rows,
                    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
                FROM information_schema.tables
                WHERE table_schema = '{Config.MYSQL_DATABASE}'
                ORDER BY size_mb DESC
            """)
            
            if table_sizes:
                total_size = sum(float(t['size_mb'] or 0) for t in table_sizes)
                print(f"  Database Size: {total_size:.2f} MB")
                for table in table_sizes:
                    if table['size_mb'] and float(table['size_mb']) > 0:
                        print(f"    {table['table_name']}: {table['size_mb']} MB")
            
        except Exception as e:
            print(f"  Health check warning: {e}")
        
        db.disconnect()
        
        print(f"\n{'='*50}")
        print("Database status check completed!")
        
        if all_tables_exist:
            print("✅ All required tables exist")
            print("✅ Your system should work without database errors")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you have config/config.py and core/database_handler.py")
        return False
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        return False

def check_recent_activity():
    """Check for recent system activity"""
    try:
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
            # Check events from last hour
            recent = db.execute_query("""
                SELECT COUNT(*) as count, MAX(timestamp) as latest
                FROM events 
                WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            
            if recent and recent[0]['count'] > 0:
                print(f"\n🔥 RECENT ACTIVITY: {recent[0]['count']} events in last hour")
                print(f"   Latest event: {recent[0]['latest']}")
                print("   ✅ Your system is actively saving events!")
            else:
                print(f"\n💤 No recent activity (last hour)")
                print("   This is normal if your system isn't currently running")
            
            db.disconnect()
    except:
        pass

if __name__ == "__main__":
    try:
        if check_database_status():
            check_recent_activity()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nCheck cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nCheck failed: {e}")
        sys.exit(1)