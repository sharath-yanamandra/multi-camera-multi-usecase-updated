# flexible_multi_camera_main.py - NEW MAIN LAUNCHER
# Launcher for flexible multi-camera system

import os
import sys
import argparse
import logging
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_banner():
    """Print application banner"""
    print("="*80)
    print(" 🎥 FLEXIBLE MULTI-CAMERA MONITORING SYSTEM")
    print("="*80)
    print(f" ⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 🔧 Features: Multiple use cases per camera with easy enable/disable")
    print(f" 🎯 Control: Runtime enable/disable of specific models per camera")
    print("="*80)

def run_flexible_system():
    """Run the flexible multi-camera system"""
    try:
        # Import flexible components
        from interface.flexible_camera_management import FlexibleCameraConfigurationManager
        from core.flexible_multi_camera_processor import FlexibleMultiCameraProcessor
        from config.multi_camera_config import MultiCameraConfig
        
        print("🎥 Welcome to Flexible Multi-Camera System!")
        
        # Run configuration manager
        manager = FlexibleCameraConfigurationManager()
        camera_configs = manager.run_interactive_menu()
        
        if camera_configs:
            print(f"\n🚀 Starting Flexible Multi-Camera System with {len(camera_configs)} cameras...")
            
            # Show configuration summary
            print("\n📋 Configuration Summary:")
            for config in camera_configs:
                enabled_count = len(config.get('enabled_use_cases', []))
                available_count = len(config.get('available_use_cases', []))
                print(f"  📷 {config['camera_id']}: {enabled_count}/{available_count} models enabled")
                
                enabled_models = ", ".join([uc.replace('_', ' ').title() 
                                          for uc in config.get('enabled_use_cases', [])])
                print(f"      Active: {enabled_models}")
            
            # Create and start processor
            processor = FlexibleMultiCameraProcessor(MultiCameraConfig)
            processor.load_camera_configurations(camera_configs)
            
            print("\n🔄 Starting processing (Ctrl+C to stop)...")
            processor.start_processing()
            
        else:
            print("❌ No camera configurations provided")
    
    except KeyboardInterrupt:
        print("\n⏹️  System stopped by user")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you have created the flexible_multi_camera_processor.py file")
    except Exception as e:
        print(f"❌ System error: {e}")
        logging.getLogger(__name__).error(f"System error: {e}", exc_info=True)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Flexible Multi-Camera Monitoring System')
    
    parser.add_argument('command', nargs='?', default='run',
                       choices=['run', 'config', 'help'],
                       help='Command to execute')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        print_banner()
        
        if args.command == 'run':
            run_flexible_system()
        elif args.command == 'config':
            from interface.flexible_camera_management import FlexibleCameraConfigurationManager
            manager = FlexibleCameraConfigurationManager()
            manager.run_interactive_menu()
        elif args.command == 'help':
            print("\n🎯 Flexible Multi-Camera System Commands:")
            print("  python flexible_multi_camera_main.py run     - Start the system")
            print("  python flexible_multi_camera_main.py config  - Configure cameras only")
            print("  python flexible_multi_camera_main.py help    - Show this help")
            
            print("\n💡 Features:")
            print("  • Multiple use cases per camera")
            print("  • Easy enable/disable of specific models")
            print("  • Runtime configuration changes")
            print("  • Per-camera model selection")
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"❌ Application error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
