# interface/camera_management.py - FIXED VERSION
# Fixes: Menu numbering, table display, configuration persistence

import json
import os
from typing import List, Dict, Any, Optional
from tabulate import tabulate

class CameraConfigurationManager:
    """Fixed camera configuration manager"""
    
    def __init__(self, config_file: str = "config/camera_configurations.json"):
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
                    if data:  # Check if file is not empty
                        self.configurations = json.loads(data)
                        print(f"✅ Loaded {len(self.configurations)} camera configurations")
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
            print(f"✅ Saved {len(self.configurations)} camera configurations to {self.config_file}")
        except Exception as e:
            print(f"❌ Error saving configurations: {e}")
    
    def display_configurations(self):
        """Display current camera configurations"""
        if not self.configurations:
            print("📷 No cameras configured yet")
            return
        
        print("\n🎥 Current Camera Configurations:")
        print("=" * 80)
        
        table_data = []
        for config in self.configurations:
            table_data.append([
                config['camera_id'],
                config['name'],
                config['use_case'].replace('_', ' ').title(),
                config['stream_url'][:40] + "..." if len(config['stream_url']) > 40 else config['stream_url'],
                "✅ Active" if config.get('status', 'active') == 'active' else "❌ Inactive"
            ])
        
        headers = ['Camera ID', 'Name', 'Use Case', 'Stream URL', 'Status']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        print(f"\n📊 Total cameras: {len(self.configurations)}")
    
    def add_camera(self):
        """Interactive camera addition"""
        print("\n➕ Adding New Camera")
        print("-" * 40)
        
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
            
            # Select use case
            print("\n📋 Available Use Cases:")
            for i, use_case in enumerate(self.available_use_cases, 1):
                print(f"  {i}. {use_case.replace('_', ' ').title()}")
            
            while True:
                try:
                    choice = int(input("\nSelect use case (1-5): "))
                    if 1 <= choice <= len(self.available_use_cases):
                        selected_use_case = self.available_use_cases[choice - 1]
                        break
                    else:
                        print("❌ Invalid choice, please select 1-5")
                except ValueError:
                    print("❌ Please enter a valid number")
            
            # Create camera configuration
            camera_config = {
                'camera_id': camera_id,
                'name': name,
                'stream_url': stream_url,
                'use_case': selected_use_case,
                'zones': self._get_default_zones_for_use_case(selected_use_case),
                'rules': self._get_default_rules_for_use_case(selected_use_case),
                'status': 'active'
            }
            
            # Add to configurations
            self.configurations.append(camera_config)
            
            # Auto-save after adding
            self.save_configurations()
            
            print(f"\n✅ Camera '{name}' added successfully!")
            print(f"   📷 ID: {camera_id}")
            print(f"   🎯 Use Case: {selected_use_case.replace('_', ' ').title()}")
            print(f"   🔗 URL: {stream_url}")
            
        except KeyboardInterrupt:
            print("\n❌ Camera addition cancelled")
        except Exception as e:
            print(f"❌ Error adding camera: {e}")
    
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
            
            # Find and remove camera
            for i, config in enumerate(self.configurations):
                if config['camera_id'] == camera_id:
                    removed_config = self.configurations.pop(i)
                    self.save_configurations()  # Auto-save after removing
                    print(f"✅ Removed camera '{removed_config['name']}' ({camera_id})")
                    return
            
            print(f"❌ Camera ID '{camera_id}' not found")
            
        except KeyboardInterrupt:
            print("\n❌ Operation cancelled")
    
    def edit_camera(self):
        """Edit an existing camera configuration"""
        if not self.configurations:
            print("📷 No cameras to edit")
            return
        
        print("\n✏️ Edit Camera")
        print("-" * 40)
        
        self.display_configurations()
        
        try:
            camera_id = input("\nEnter Camera ID to edit: ").strip()
            
            # Find camera
            camera_config = None
            for config in self.configurations:
                if config['camera_id'] == camera_id:
                    camera_config = config
                    break
            
            if not camera_config:
                print(f"❌ Camera ID '{camera_id}' not found")
                return
            
            print(f"\n📷 Editing: {camera_config['name']}")
            
            # Edit fields
            new_name = input(f"Name [{camera_config['name']}]: ").strip()
            if new_name:
                camera_config['name'] = new_name
            
            new_url = input(f"Stream URL [{camera_config['stream_url']}]: ").strip()
            if new_url:
                camera_config['stream_url'] = new_url
            
            # Change use case
            current_use_case = camera_config['use_case']
            print(f"\nCurrent use case: {current_use_case.replace('_', ' ').title()}")
            change_use_case = input("Change use case? (y/n): ").strip().lower()
            
            if change_use_case == 'y':
                print("\n📋 Available Use Cases:")
                for i, use_case in enumerate(self.available_use_cases, 1):
                    marker = " (current)" if use_case == current_use_case else ""
                    print(f"  {i}. {use_case.replace('_', ' ').title()}{marker}")
                
                try:
                    choice = int(input("\nSelect new use case (1-5): "))
                    if 1 <= choice <= len(self.available_use_cases):
                        new_use_case = self.available_use_cases[choice - 1]
                        camera_config['use_case'] = new_use_case
                        camera_config['zones'] = self._get_default_zones_for_use_case(new_use_case)
                        camera_config['rules'] = self._get_default_rules_for_use_case(new_use_case)
                        print(f"✅ Use case changed to: {new_use_case.replace('_', ' ').title()}")
                except ValueError:
                    print("❌ Invalid choice, keeping current use case")
            
            # Auto-save after editing
            self.save_configurations()
            print(f"✅ Camera '{camera_config['name']}' updated successfully!")
            
        except KeyboardInterrupt:
            print("\n❌ Edit cancelled")
    
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
    
    def export_configurations(self):
        """Export configurations for production use"""
        if not self.configurations:
            print("📷 No configurations to export")
            return
        
        export_file = input("Export filename [camera_configs_export.json]: ").strip()
        if not export_file:
            export_file = "camera_configs_export.json"
        
        try:
            with open(export_file, 'w') as f:
                json.dump(self.configurations, f, indent=2)
            print(f"✅ Configurations exported to {export_file}")
        except Exception as e:
            print(f"❌ Export failed: {e}")
    
    def _get_default_zones_for_use_case(self, use_case: str) -> Dict[str, Any]:
        """Get default zones for a use case"""
        default_zones = {
            'people_counting': {
                'counting': [{
                    'zone_id': 1,
                    'name': 'Counting Zone',
                    'coordinates': [[200, 200], [800, 200], [800, 600], [200, 600]]
                }]
            },
            'ppe_detection': {
                'ppe_zone': [{
                    'zone_id': 2,
                    'name': 'PPE Required Zone',
                    'coordinates': [[300, 250], [900, 250], [900, 700], [300, 700]]
                }]
            },
            'tailgating': {
                'entry': [{
                    'zone_id': 3,
                    'name': 'Entry Control Zone',
                    'coordinates': [[250, 300], [750, 300], [750, 650], [250, 650]]
                }]
            },
            'intrusion': {
                'intrusion': [{
                    'zone_id': 4,
                    'name': 'Restricted Zone',
                    'coordinates': [[500, 200], [1200, 200], [1200, 800], [500, 800]]
                }]
            },
            'loitering': {
                'loitering': [{
                    'zone_id': 5,
                    'name': 'No Loitering Zone',
                    'coordinates': [[400, 350], [1000, 350], [1000, 750], [400, 750]]
                }]
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
        """Run interactive camera management menu - FIXED VERSION"""
        while True:
            print("\n" + "="*60)
            print("🎥 MULTI-CAMERA SYSTEM - CONFIGURATION MANAGER")
            print("="*60)
            print("1. 📋 Display Current Cameras")
            print("2. ➕ Add New Camera")  
            print("3. ✏️  Edit Camera")
            print("4. ➖ Remove Camera")
            print("5. 🔍 Test Camera Connection")
            print("6. 💾 Save Configurations")
            print("7. 📤 Export Configurations")
            print("8. 🚀 Start Multi-Camera System")
            print("9. 🚪 Exit")
            print("-"*60)
            
            try:
                choice = input("Select option (1-9): ").strip()
                
                if choice == '1':
                    self.display_configurations()
                elif choice == '2':
                    self.add_camera()
                elif choice == '3':
                    self.edit_camera()
                elif choice == '4':
                    self.remove_camera()
                elif choice == '5':
                    self.test_camera_connection()
                elif choice == '6':
                    self.save_configurations()
                elif choice == '7':
                    self.export_configurations()
                elif choice == '8':
                    if self.configurations:
                        print("\n🚀 Starting Multi-Camera System...")
                        return self.configurations  # Return configs to start system
                    else:
                        print("❌ No cameras configured. Please add cameras first.")
                elif choice == '9':
                    print("\n👋 Goodbye!")
                    return None
                else:
                    print("❌ Invalid choice. Please select 1-9.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                return None
            except Exception as e:
                print(f"❌ Error: {e}")


def main():
    """Main function to run camera management interface"""
    print("🎥 Welcome to Multi-Camera System Configuration!")
    
    manager = CameraConfigurationManager()
    
    # Run interactive menu
    camera_configs = manager.run_interactive_menu()
    
    if camera_configs:
        # Start the multi-camera system
        print("\n🚀 Launching Multi-Camera System...")
        
        # Import and run multi-camera processor
        try:
            from core.multi_camera_processor import MultiCameraProcessor
            from config.multi_camera_config import MultiCameraConfig
            
            processor = MultiCameraProcessor(MultiCameraConfig)
            processor.load_camera_configurations(camera_configs)
            processor.start_processing()
            
        except ImportError as e:
            print(f"❌ Error importing multi-camera processor: {e}")
            print("Please ensure the multi-camera processor is properly installed.")
        except Exception as e:
            print(f"❌ Error starting multi-camera system: {e}")


if __name__ == "__main__":
    main()

# interface/camera_management.py - NEW FILE
# Simple CLI interface for camera management
'''
import json
import os
from typing import List, Dict, Any, Optional
from tabulate import tabulate

class CameraConfigurationManager:
    """Simple interface for managing camera configurations"""
    
    def __init__(self, config_file: str = "config/camera_configurations.json"):
        self.config_file = config_file
        self.configurations = []
        self.available_use_cases = [
            'people_counting',
            'ppe_detection', 
            'tailgating',
            'intrusion',
            'loitering'
        ]
        
        # Load existing configurations
        self.load_configurations()
    
    def load_configurations(self):
        """Load camera configurations from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.configurations = json.load(f)
                print(f"✅ Loaded {len(self.configurations)} camera configurations")
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
            print(f"✅ Saved {len(self.configurations)} camera configurations")
        except Exception as e:
            print(f"❌ Error saving configurations: {e}")
    
    def display_configurations(self):
        """Display current camera configurations"""
        if not self.configurations:
            print("📷 No cameras configured yet")
            return
        
        print("\n🎥 Current Camera Configurations:")
        print("=" * 80)
        
        table_data = []
        for config in self.configurations:
            table_data.append([
                config['camera_id'],
                config['name'],
                config['use_case'].replace('_', ' ').title(),
                config['stream_url'][:50] + "..." if len(config['stream_url']) > 50 else config['stream_url'],
                "✅ Active" if config.get('status', 'active') == 'active' else "❌ Inactive"
            ])
        
        headers = ['Camera ID', 'Name', 'Use Case', 'Stream URL', 'Status']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        print(f"\n📊 Total cameras: {len(self.configurations)}")
    
    def add_camera(self):
        """Interactive camera addition"""
        print("\n➕ Adding New Camera")
        print("-" * 40)
        
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
            
            # Select use case
            print("\n📋 Available Use Cases:")
            for i, use_case in enumerate(self.available_use_cases, 1):
                print(f"  {i}. {use_case.replace('_', ' ').title()}")
            
            while True:
                try:
                    choice = int(input("\nSelect use case (1-5): "))
                    if 1 <= choice <= len(self.available_use_cases):
                        selected_use_case = self.available_use_cases[choice - 1]
                        break
                    else:
                        print("❌ Invalid choice, please select 1-5")
                except ValueError:
                    print("❌ Please enter a valid number")
            
            # Create camera configuration
            camera_config = {
                'camera_id': camera_id,
                'name': name,
                'stream_url': stream_url,
                'use_case': selected_use_case,
                'zones': self._get_default_zones_for_use_case(selected_use_case),
                'rules': self._get_default_rules_for_use_case(selected_use_case),
                'status': 'active'
            }
            
            # Add to configurations
            self.configurations.append(camera_config)
            
            print(f"\n✅ Camera '{name}' added successfully!")
            print(f"   📷 ID: {camera_id}")
            print(f"   🎯 Use Case: {selected_use_case.replace('_', ' ').title()}")
            print(f"   🔗 URL: {stream_url}")
            
        except KeyboardInterrupt:
            print("\n❌ Camera addition cancelled")
        except Exception as e:
            print(f"❌ Error adding camera: {e}")
    
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
            
            # Find and remove camera
            for i, config in enumerate(self.configurations):
                if config['camera_id'] == camera_id:
                    removed_config = self.configurations.pop(i)
                    print(f"✅ Removed camera '{removed_config['name']}' ({camera_id})")
                    return
            
            print(f"❌ Camera ID '{camera_id}' not found")
            
        except KeyboardInterrupt:
            print("\n❌ Operation cancelled")
    
    def edit_camera(self):
        """Edit an existing camera configuration"""
        if not self.configurations:
            print("📷 No cameras to edit")
            return
        
        print("\n✏️ Edit Camera")
        print("-" * 40)
        
        self.display_configurations()
        
        try:
            camera_id = input("\nEnter Camera ID to edit: ").strip()
            
            # Find camera
            camera_config = None
            for config in self.configurations:
                if config['camera_id'] == camera_id:
                    camera_config = config
                    break
            
            if not camera_config:
                print(f"❌ Camera ID '{camera_id}' not found")
                return
            
            print(f"\n📷 Editing: {camera_config['name']}")
            
            # Edit fields
            new_name = input(f"Name [{camera_config['name']}]: ").strip()
            if new_name:
                camera_config['name'] = new_name
            
            new_url = input(f"Stream URL [{camera_config['stream_url']}]: ").strip()
            if new_url:
                camera_config['stream_url'] = new_url
            
            # Change use case
            current_use_case = camera_config['use_case']
            print(f"\nCurrent use case: {current_use_case.replace('_', ' ').title()}")
            change_use_case = input("Change use case? (y/n): ").strip().lower()
            
            if change_use_case == 'y':
                print("\n📋 Available Use Cases:")
                for i, use_case in enumerate(self.available_use_cases, 1):
                    marker = " (current)" if use_case == current_use_case else ""
                    print(f"  {i}. {use_case.replace('_', ' ').title()}{marker}")
                
                try:
                    choice = int(input("\nSelect new use case (1-5): "))
                    if 1 <= choice <= len(self.available_use_cases):
                        new_use_case = self.available_use_cases[choice - 1]
                        camera_config['use_case'] = new_use_case
                        camera_config['zones'] = self._get_default_zones_for_use_case(new_use_case)
                        camera_config['rules'] = self._get_default_rules_for_use_case(new_use_case)
                        print(f"✅ Use case changed to: {new_use_case.replace('_', ' ').title()}")
                except ValueError:
                    print("❌ Invalid choice, keeping current use case")
            
            print(f"✅ Camera '{camera_config['name']}' updated successfully!")
            
        except KeyboardInterrupt:
            print("\n❌ Edit cancelled")
    
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
    
    def export_configurations(self):
        """Export configurations for production use"""
        if not self.configurations:
            print("📷 No configurations to export")
            return
        
        export_file = input("Export filename [camera_configs_export.json]: ").strip()
        if not export_file:
            export_file = "camera_configs_export.json"
        
        try:
            with open(export_file, 'w') as f:
                json.dump(self.configurations, f, indent=2)
            print(f"✅ Configurations exported to {export_file}")
        except Exception as e:
            print(f"❌ Export failed: {e}")
    
    def _get_default_zones_for_use_case(self, use_case: str) -> Dict[str, Any]:
        """Get default zones for a use case"""
        default_zones = {
            'people_counting': {
                'counting': [{
                    'zone_id': 1,
                    'name': 'Counting Zone',
                    'coordinates': [[200, 200], [800, 200], [800, 600], [200, 600]]
                }]
            },
            'ppe_detection': {
                'ppe_zone': [{
                    'zone_id': 2,
                    'name': 'PPE Required Zone',
                    'coordinates': [[300, 250], [900, 250], [900, 700], [300, 700]]
                }]
            },
            'tailgating': {
                'entry': [{
                    'zone_id': 3,
                    'name': 'Entry Control Zone',
                    'coordinates': [[250, 300], [750, 300], [750, 650], [250, 650]]
                }]
            },
            'intrusion': {
                'intrusion': [{
                    'zone_id': 4,
                    'name': 'Restricted Zone',
                    'coordinates': [[500, 200], [1200, 200], [1200, 800], [500, 800]]
                }]
            },
            'loitering': {
                'loitering': [{
                    'zone_id': 5,
                    'name': 'No Loitering Zone',
                    'coordinates': [[400, 350], [1000, 350], [1000, 750], [400, 750]]
                }]
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
        """Run interactive camera management menu"""
        while True:
            print("\n" + "="*60)
            print("🎥 MULTI-CAMERA SYSTEM - CONFIGURATION MANAGER")
            print("="*60)
            print("1. 📋 Display Current Cameras")
            print("2. ➕ Add New Camera")  
            print("3. ✏️  Edit Camera")
            print("4. ➖ Remove Camera")
            print("5. 🔍 Test Camera Connection")
            print("6. 💾 Save Configurations")
            print("7. 📤 Export Configurations")
            print("8. 🚀 Start Multi-Camera System")
            print("9. 🚪 Exit")
            print("-"*60)
            
            try:
                choice = input("Select option (1-9): ").strip()
                
                if choice == '1':
                    self.display_configurations()
                elif choice == '2':
                    self.add_camera()
                elif choice == '3':
                    self.edit_camera()
                elif choice == '4':
                    self.remove_camera()
                elif choice == '5':
                    self.test_camera_connection()
                elif choice == '6':
                    self.save_configurations()
                elif choice == '7':
                    self.export_configurations()
                elif choice == '8':
                    if self.configurations:
                        print("\n🚀 Starting Multi-Camera System...")
                        return self.configurations  # Return configs to start system
                    else:
                        print("❌ No cameras configured. Please add cameras first.")
                elif choice == '9':
                    print("\n👋 Goodbye!")
                    return None
                else:
                    print("❌ Invalid choice. Please select 1-9.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                return None
            except Exception as e:
                print(f"❌ Error: {e}")


def main():
    """Main function to run camera management interface"""
    print("🎥 Welcome to Multi-Camera System Configuration!")
    
    manager = CameraConfigurationManager()
    
    # Run interactive menu
    camera_configs = manager.run_interactive_menu()
    
    if camera_configs:
        # Start the multi-camera system
        print("\n🚀 Launching Multi-Camera System...")
        
        # Import and run multi-camera processor
        try:
            from core.multi_camera_processor import MultiCameraProcessor
            from config.multi_camera_config import MultiCameraConfig
            
            processor = MultiCameraProcessor(MultiCameraConfig)
            processor.load_camera_configurations(camera_configs)
            processor.start_processing()
            
        except ImportError as e:
            print(f"❌ Error importing multi-camera processor: {e}")
            print("Please ensure the multi-camera processor is properly installed.")
        except Exception as e:
            print(f"❌ Error starting multi-camera system: {e}")


if __name__ == "__main__":
    main()

    '''