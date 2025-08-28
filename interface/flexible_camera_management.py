# interface/flexible_camera_management.py - NEW FLEXIBLE INTERFACE
# Allows selecting multiple use cases per camera with easy enable/disable

import json
import os
from typing import List, Dict, Any, Optional
from tabulate import tabulate

class FlexibleCameraConfigurationManager:
    """Flexible camera configuration manager with use case selection"""
    
    def __init__(self, config_file: str = "config/flexible_camera_configurations.json"):
        self.config_file = config_file
        self.configurations = []
        self.available_use_cases = [
            'people_counting',
            'ppe_detection', 
            'tailgating',
            'intrusion',
            'loitering'
        ]
        
        # Ensure config directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # Load existing configurations
        self.load_configurations()
    
    def load_configurations(self):
        """Load camera configurations from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = f.read().strip()
                    if data:
                        self.configurations = json.loads(data)
                        print(f"✅ Loaded {len(self.configurations)} flexible camera configurations")
                    else:
                        print("📁 Configuration file is empty, starting fresh")
                        self.configurations = []
            else:
                print("📁 No existing configurations found, starting fresh")
                self.configurations = []
        except Exception as e:
            print(f"❌ Error loading configurations: {e}")
            self.configurations = []
    
    def save_configurations(self):
        """Save camera configurations to file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.configurations, f, indent=2)
            print(f"✅ Saved {len(self.configurations)} flexible camera configurations")
        except Exception as e:
            print(f"❌ Error saving configurations: {e}")
    
    def display_configurations(self):
        """Display current camera configurations with use case details"""
        if not self.configurations:
            print("📷 No cameras configured yet")
            return
        
        print("\n🎥 Current Flexible Camera Configurations:")
        print("=" * 100)
        
        for config in self.configurations:
            camera_id = config['camera_id']
            name = config['name']
            enabled_count = len(config.get('enabled_use_cases', []))
            available_count = len(config.get('available_use_cases', []))
            
            print(f"\n📷 {camera_id}: {name}")
            print(f"   🔗 URL: {config['stream_url']}")
            print(f"   📊 Use Cases: {enabled_count}/{available_count} enabled")
            
            # Show available use cases with status
            available = config.get('available_use_cases', [])
            enabled = config.get('enabled_use_cases', [])
            
            print("   📋 Available Use Cases:")
            for use_case in available:
                status = "✅ ENABLED" if use_case in enabled else "❌ DISABLED"
                print(f"      • {use_case.replace('_', ' ').title()}: {status}")
        
        print(f"\n📊 Total cameras: {len(self.configurations)}")
    
    def add_camera(self):
        """Interactive camera addition with flexible use case selection"""
        print("\n➕ Adding New Flexible Camera")
        print("-" * 50)
        
        try:
            # Get camera details
            camera_id = input("Camera ID (e.g., cam_001): ").strip()
            if not camera_id:
                print("❌ Camera ID is required")
                return
            
            # Check for duplicate
            if any(config['camera_id'] == camera_id for config in self.configurations):
                print(f"❌ Camera ID '{camera_id}' already exists")
                return
            
            name = input("Camera Name (e.g., Main Entrance): ").strip()
            if not name:
                print("❌ Camera name is required")
                return
            
            stream_url = input("Stream URL (RTSP): ").strip()
            if not stream_url:
                print("❌ Stream URL is required")
                return
            
            # Select available use cases
            print("\n📋 Select Available Use Cases for this camera:")
            print("(You can enable/disable them later)")
            
            available_use_cases = []
            for i, use_case in enumerate(self.available_use_cases, 1):
                include = input(f"  Include {use_case.replace('_', ' ').title()}? (y/n, default=y): ").strip().lower()
                if include != 'n':
                    available_use_cases.append(use_case)
            
            if not available_use_cases:
                print("❌ At least one use case must be available")
                return
            
            # Select initially enabled use cases
            print(f"\n🎯 Select Initially ENABLED Use Cases:")
            print("(You selected these as available, now choose which to enable initially)")
            
            enabled_use_cases = []
            for use_case in available_use_cases:
                enable = input(f"  Enable {use_case.replace('_', ' ').title()} initially? (y/n, default=y): ").strip().lower()
                if enable != 'n':
                    enabled_use_cases.append(use_case)
            
            # Quick option for "all enabled"
            if not enabled_use_cases:
                enable_all = input("  No use cases selected. Enable all available? (y/n): ").strip().lower()
                if enable_all == 'y':
                    enabled_use_cases = available_use_cases.copy()
            
            # Create camera configuration
            camera_config = {
                'camera_id': camera_id,
                'name': name,
                'stream_url': stream_url,
                'available_use_cases': available_use_cases,
                'enabled_use_cases': enabled_use_cases,
                'zones': self._get_zones_for_use_cases(available_use_cases),
                'rules': self._get_rules_for_use_cases(available_use_cases),
                'status': 'active'
            }
            
            # Add to configurations
            self.configurations.append(camera_config)
            self.save_configurations()
            
            print(f"\n✅ Flexible camera '{name}' added successfully!")
            print(f"   📷 ID: {camera_id}")
            print(f"   📋 Available use cases: {len(available_use_cases)}")
            print(f"   🎯 Initially enabled: {len(enabled_use_cases)}")
            print(f"   🔗 URL: {stream_url}")
            
        except KeyboardInterrupt:
            print("\n❌ Camera addition cancelled")
        except Exception as e:
            print(f"❌ Error adding camera: {e}")
    
    def manage_camera_use_cases(self):
        """Manage use cases for a specific camera"""
        if not self.configurations:
            print("📷 No cameras to manage")
            return
        
        print("\n🔧 Manage Camera Use Cases")
        print("-" * 40)
        
        self.display_configurations()
        
        try:
            camera_id = input("\nEnter Camera ID to manage: ").strip()
            
            # Find camera
            camera_config = None
            for config in self.configurations:
                if config['camera_id'] == camera_id:
                    camera_config = config
                    break
            
            if not camera_config:
                print(f"❌ Camera ID '{camera_id}' not found")
                return
            
            while True:
                print(f"\n🎥 Managing: {camera_config['name']} ({camera_id})")
                print("=" * 60)
                
                available = camera_config.get('available_use_cases', [])
                enabled = camera_config.get('enabled_use_cases', [])
                
                print("Current Status:")
                for i, use_case in enumerate(available, 1):
                    status = "✅ ENABLED" if use_case in enabled else "❌ DISABLED"
                    print(f"  {i}. {use_case.replace('_', ' ').title()}: {status}")
                
                print(f"\n{len(available) + 1}. ✅ Enable All")
                print(f"{len(available) + 2}. ❌ Disable All")
                print(f"{len(available) + 3}. 💾 Save & Exit")
                print(f"{len(available) + 4}. 🚪 Exit without saving")
                
                choice = input(f"\nSelect option (1-{len(available) + 4}): ").strip()
                
                try:
                    choice_num = int(choice)
                    
                    if 1 <= choice_num <= len(available):
                        # Toggle specific use case
                        use_case = available[choice_num - 1]
                        if use_case in enabled:
                            enabled.remove(use_case)
                            print(f"❌ Disabled {use_case.replace('_', ' ').title()}")
                        else:
                            enabled.append(use_case)
                            print(f"✅ Enabled {use_case.replace('_', ' ').title()}")
                    
                    elif choice_num == len(available) + 1:
                        # Enable all
                        camera_config['enabled_use_cases'] = available.copy()
                        print("✅ Enabled all use cases")
                    
                    elif choice_num == len(available) + 2:
                        # Disable all
                        camera_config['enabled_use_cases'] = []
                        print("❌ Disabled all use cases")
                    
                    elif choice_num == len(available) + 3:
                        # Save and exit
                        self.save_configurations()
                        print(f"✅ Saved changes for {camera_config['name']}")
                        break
                    
                    elif choice_num == len(available) + 4:
                        # Exit without saving
                        print("❌ Exited without saving changes")
                        break
                    
                    else:
                        print("❌ Invalid choice")
                
                except ValueError:
                    print("❌ Please enter a valid number")
            
        except KeyboardInterrupt:
            print("\n❌ Management cancelled")
    
    def test_camera_connection(self):
        """Test camera connection"""
        if not self.configurations:
            print("📷 No cameras to test")
            return
        
        print("\n🔍 Test Camera Connection")
        print("-" * 40)
        
        self.display_configurations()
        
        camera_id = input("\nEnter Camera ID to test (or 'all' for all cameras): ").strip()
        
        if camera_id.lower() == 'all':
            cameras_to_test = self.configurations
        else:
            cameras_to_test = [config for config in self.configurations if config['camera_id'] == camera_id]
            if not cameras_to_test:
                print(f"❌ Camera ID '{camera_id}' not found")
                return
        
        print("\n🔍 Testing connections...")
        
        import cv2
        for config in cameras_to_test:
            print(f"\n📷 Testing {config['name']} ({config['camera_id']})...")
            print(f"   URL: {config['stream_url']}")
            
            try:
                cap = cv2.VideoCapture(config['stream_url'])
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    if ret:
                        print(f"   ✅ Connection successful - receiving frames")
                    else:
                        print(f"   ⚠️  Connected but no frames received")
                else:
                    print(f"   ❌ Connection failed")
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    def clone_camera_config(self):
        """Clone an existing camera configuration"""
        if not self.configurations:
            print("📷 No cameras to clone")
            return
        
        print("\n📋 Clone Camera Configuration")
        print("-" * 40)
        
        self.display_configurations()
        
        try:
            source_id = input("\nEnter Camera ID to clone from: ").strip()
            
            # Find source camera
            source_config = None
            for config in self.configurations:
                if config['camera_id'] == source_id:
                    source_config = config.copy()
                    break
            
            if not source_config:
                print(f"❌ Camera ID '{source_id}' not found")
                return
            
            # Get new camera details
            new_id = input("New Camera ID: ").strip()
            if not new_id or any(config['camera_id'] == new_id for config in self.configurations):
                print("❌ Invalid or duplicate Camera ID")
                return
            
            new_name = input("New Camera Name: ").strip()
            if not new_name:
                print("❌ Camera name is required")
                return
            
            new_url = input("New Stream URL: ").strip()
            if not new_url:
                print("❌ Stream URL is required")
                return
            
            # Create cloned configuration
            source_config['camera_id'] = new_id
            source_config['name'] = new_name
            source_config['stream_url'] = new_url
            
            self.configurations.append(source_config)
            self.save_configurations()
            
            print(f"✅ Cloned camera configuration successfully!")
            print(f"   📷 New ID: {new_id}")
            print(f"   📋 Inherited {len(source_config.get('available_use_cases', []))} use cases")
            
        except KeyboardInterrupt:
            print("\n❌ Clone cancelled")
    
    def _get_zones_for_use_cases(self, use_cases: List[str]) -> Dict[str, Any]:
        """Get zones configuration for selected use cases"""
        zones = {}
        for use_case in use_cases:
            zones[use_case] = self._get_default_zones_for_use_case(use_case)[use_case]
        return zones
    
    def _get_rules_for_use_cases(self, use_cases: List[str]) -> Dict[str, Any]:
        """Get rules configuration for selected use cases"""
        rules = {}
        for use_case in use_cases:
            rules[use_case] = self._get_default_rules_for_use_case(use_case)
        return rules
    
    def _get_default_zones_for_use_case(self, use_case: str) -> Dict[str, Any]:
        """Get default zones for a use case"""
        default_zones = {
            'people_counting': {
                'people_counting': {
                    'counting': [{
                        'zone_id': 1,
                        'name': 'Counting Zone',
                        'coordinates': [[200, 200], [800, 200], [800, 600], [200, 600]]
                    }]
                }
            },
            'ppe_detection': {
                'ppe_detection': {
                    'ppe_zone': [{
                        'zone_id': 2,
                        'name': 'PPE Required Zone',
                        'coordinates': [[300, 250], [900, 250], [900, 700], [300, 700]]
                    }]
                }
            },
            'tailgating': {
                'tailgating': {
                    'entry': [{
                        'zone_id': 3,
                        'name': 'Entry Control Zone',
                        'coordinates': [[250, 300], [750, 300], [750, 650], [250, 650]]
                    }]
                }
            },
            'intrusion': {
                'intrusion': {
                    'intrusion': [{
                        'zone_id': 4,
                        'name': 'Restricted Zone',
                        'coordinates': [[500, 200], [1200, 200], [1200, 800], [500, 800]]
                    }]
                }
            },
            'loitering': {
                'loitering': {
                    'loitering': [{
                        'zone_id': 5,
                        'name': 'No Loitering Zone',
                        'coordinates': [[400, 350], [1000, 350], [1000, 750], [400, 750]]
                    }]
                }
            }
        }
        return default_zones.get(use_case, {})
    
    def _get_default_rules_for_use_case(self, use_case: str) -> Dict[str, Any]:
        """Get default rules for a use case"""
        default_rules = {
            'people_counting': {
                'count_threshold': 0,
                'confidence_threshold': 0.3
            },
            'ppe_detection': {
                'required_ppe': ['hard_hat', 'safety_vest'],
                'confidence_threshold': 0.3
            },
            'tailgating': {
                'time_limit': 2.0,
                'distance_threshold': 200,
                'confidence_threshold': 0.3
            },
            'intrusion': {
                'alert_immediately': True,
                'confidence_threshold': 0.3
            },
            'loitering': {
                'time_threshold': 300,
                'movement_threshold': 20,
                'confidence_threshold': 0.3
            }
        }
        return default_rules.get(use_case, {})
    
    def run_interactive_menu(self):
        """Run interactive flexible camera management menu"""
        while True:
            print("\n" + "="*70)
            print("🎥 FLEXIBLE MULTI-CAMERA SYSTEM - CONFIGURATION MANAGER")
            print("="*70)
            print("1. 📋 Display Current Cameras")
            print("2. ➕ Add New Camera")  
            print("3. 🔧 Manage Camera Use Cases")
            print("4. ✏️  Edit Camera Details")
            print("5. ➖ Remove Camera")
            print("6. 📋 Clone Camera Configuration")
            print("7. 🔍 Test Camera Connection")
            print("8. 💾 Save Configurations")
            print("9. 📤 Export Configurations")
            print("10. 🚀 Start Flexible Multi-Camera System")
            print("11. 🚪 Exit")
            print("-"*70)
            
            try:
                choice = input("Select option (1-11): ").strip()
                
                if choice == '1':
                    self.display_configurations()
                elif choice == '2':
                    self.add_camera()
                elif choice == '3':
                    self.manage_camera_use_cases()
                elif choice == '4':
                    self.edit_camera_details()
                elif choice == '5':
                    self.remove_camera()
                elif choice == '6':
                    self.clone_camera_config()
                elif choice == '7':
                    self.test_camera_connection()
                elif choice == '8':
                    self.save_configurations()
                elif choice == '9':
                    self.export_configurations()
                elif choice == '10':
                    if self.configurations:
                        print("\n🚀 Starting Flexible Multi-Camera System...")
                        return self.configurations
                    else:
                        print("❌ No cameras configured. Please add cameras first.")
                elif choice == '11':
                    print("\n👋 Goodbye!")
                    return None
                else:
                    print("❌ Invalid choice. Please select 1-11.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                return None
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def edit_camera_details(self):
        """Edit camera name and URL (not use cases)"""
        if not self.configurations:
            print("📷 No cameras to edit")
            return
        
        print("\n✏️ Edit Camera Details")
        print("-" * 40)
        
        self.display_configurations()
        
        try:
            camera_id = input("\nEnter Camera ID to edit: ").strip()
            
            camera_config = None
            for config in self.configurations:
                if config['camera_id'] == camera_id:
                    camera_config = config
                    break
            
            if not camera_config:
                print(f"❌ Camera ID '{camera_id}' not found")
                return
            
            print(f"\n📷 Editing: {camera_config['name']}")
            
            new_name = input(f"Name [{camera_config['name']}]: ").strip()
            if new_name:
                camera_config['name'] = new_name
            
            new_url = input(f"Stream URL [{camera_config['stream_url']}]: ").strip()
            if new_url:
                camera_config['stream_url'] = new_url
            
            self.save_configurations()
            print(f"✅ Camera details updated successfully!")
            
        except KeyboardInterrupt:
            print("\n❌ Edit cancelled")
    
    def remove_camera(self):
        """Remove a camera configuration"""
        if not self.configurations:
            print("📷 No cameras to remove")
            return
        
        print("\n➖ Remove Camera")
        print("-" * 40)
        
        self.display_configurations()
        
        try:
            camera_id = input("\nEnter Camera ID to remove: ").strip()
            
            for i, config in enumerate(self.configurations):
                if config['camera_id'] == camera_id:
                    removed_config = self.configurations.pop(i)
                    self.save_configurations()
                    print(f"✅ Removed camera '{removed_config['name']}' ({camera_id})")
                    return
            
            print(f"❌ Camera ID '{camera_id}' not found")
            
        except KeyboardInterrupt:
            print("\n❌ Operation cancelled")
    
    def export_configurations(self):
        """Export configurations"""
        if not self.configurations:
            print("📷 No configurations to export")
            return
        
        export_file = input("Export filename [flexible_camera_configs.json]: ").strip()
        if not export_file:
            export_file = "flexible_camera_configs.json"
        
        try:
            with open(export_file, 'w') as f:
                json.dump(self.configurations, f, indent=2)
            print(f"✅ Configurations exported to {export_file}")
        except Exception as e:
            print(f"❌ Export failed: {e}")


def main():
    """Main function for flexible camera management"""
    print("🎥 Welcome to Flexible Multi-Camera System Configuration!")
    
    manager = FlexibleCameraConfigurationManager()
    camera_configs = manager.run_interactive_menu()
    
    if camera_configs:
        print("\n🚀 Launching Flexible Multi-Camera System...")
        
        try:
            from core.flexible_multi_camera_processor import FlexibleMultiCameraProcessor
            from config.multi_camera_config import MultiCameraConfig
            
            processor = FlexibleMultiCameraProcessor(MultiCameraConfig)
            processor.load_camera_configurations(camera_configs)
            processor.start_processing()
            
        except ImportError as e:
            print(f"❌ Error importing flexible processor: {e}")
        except Exception as e:
            print(f"❌ Error starting system: {e}")


if __name__ == "__main__":
    main()