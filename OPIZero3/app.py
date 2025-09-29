import os
import json
import sqlite3
import logging
import threading
import time
import subprocess
import psutil
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

# Configure logging
os.makedirs('logs', exist_ok=True)
os.makedirs('data', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/marvinlink.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration paths
CONFIG_FILE = 'data/config.json'
SENSORS_FILE = 'data/sensors_data.json'
DB_PATH = 'data/marvinlink.db'

# ========== JSON FILE MANAGERS ==========

class ConfigManager:
    """Manages configuration in JSON file"""
    
    @staticmethod
    def load():
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            default = {
                'user_name': 'Чед',
                'weather_city': 'Київ',
                'timezone': 'Europe/Kiev'
            }
            ConfigManager.save(default)
            return default
    
    @staticmethod
    def save(config):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info("Config saved to file")

class SensorsDataManager:
    """Manages sensor data in JSON file"""
    
    @staticmethod
    def load():
        if os.path.exists(SENSORS_FILE):
            with open(SENSORS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            default = {'esp_modules': []}
            SensorsDataManager.save(default)
            return default
    
    @staticmethod
    def save(data):
        with open(SENSORS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def update_module_data(ip_address, sensor_data):
        """Update sensor values for a module by IP"""
        data = SensorsDataManager.load()
        
        for esp in data['esp_modules']:
            if esp.get('ip_address') == ip_address:
                esp['online'] = True
                esp['last_seen'] = datetime.now().isoformat()
                
                for sensor in esp['sensors']:
                    sensor_type = sensor['type']
                    if sensor_type in sensor_data:
                        sensor['value'] = sensor_data[sensor_type]
                        sensor['last_updated'] = datetime.now().isoformat()
                
                SensorsDataManager.save(data)
                return True
        
        return False

# ========== DATABASE MANAGER ==========

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # ESP modules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS esp_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                location_icon TEXT DEFAULT '📍',
                ip_address TEXT UNIQUE NOT NULL,
                is_online BOOLEAN DEFAULT 0,
                last_seen TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Sensors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                esp_id INTEGER,
                sensor_type TEXT NOT NULL,
                sensor_name TEXT NOT NULL,
                unit TEXT NOT NULL,
                icon TEXT DEFAULT '📊',
                last_value REAL,
                last_updated TIMESTAMP,
                FOREIGN KEY (esp_id) REFERENCES esp_modules (id)
            )
        ''')
        
        # System logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def log_event(self, level, message):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO system_logs (level, message) VALUES (?, ?)',
                (level, message)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

# ========== SYSTEM MONITOR ==========

class SystemMonitor:
    @staticmethod
    def get_cpu_temperature():
        try:
            temp_paths = [
                '/sys/class/thermal/thermal_zone0/temp',
                '/sys/class/thermal/thermal_zone1/temp',
            ]
            
            for path in temp_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        temp = int(f.read().strip()) / 1000.0
                        return round(temp, 1)
            return None
        except:
            return None
    
    @staticmethod
    def get_ram_usage():
        try:
            memory = psutil.virtual_memory()
            return memory.used // (1024 * 1024)
        except:
            return None
    
    @staticmethod
    def ping_host(ip_address):
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', ip_address],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except:
            return False

# Initialize
db_manager = DatabaseManager(DB_PATH)
system_monitor = SystemMonitor()

# ========== ROUTES ==========

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/system-status')
def get_system_status():
    """Real Orange Pi system status"""
    try:
        return jsonify({
            'cpu_temp': system_monitor.get_cpu_temperature(),
            'ram_usage': system_monitor.get_ram_usage(),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def get_status():
    """Get complete system status"""
    try:
        cpu_temp = system_monitor.get_cpu_temperature()
        ram_usage = system_monitor.get_ram_usage()
        
        sensors_data = SensorsDataManager.load()
        esp_modules = sensors_data.get('esp_modules', [])
        
        active_esp = sum(1 for esp in esp_modules if esp.get('online', False))
        total_sensors = sum(len(esp.get('sensors', [])) for esp in esp_modules)
        
        return jsonify({
            'system': {
                'cpu_temp': cpu_temp,
                'ram_usage': ram_usage,
                'active_esp': active_esp,
                'total_sensors': total_sensors
            },
            'esp_modules': esp_modules,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/discover')
def discover_esp():
    """Discover ESP modules on network"""
    try:
        # Get list of registered IPs
        sensors_data = SensorsDataManager.load()
        registered_ips = {esp['ip_address'] for esp in sensors_data['esp_modules']}
        
        # Scan network for new ESP devices (placeholder - ESP should announce itself)
        discovered = []
        
        return jsonify({'discovered': discovered, 'registered': list(registered_ips)})
        
    except Exception as e:
        logger.error(f"Error discovering ESP: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/info/<ip_address>')
def get_esp_info(ip_address):
    """Get ESP module info by IP (ESP should provide this)"""
    try:
        # This would query the ESP device directly
        # For now, return error if not found
        sensors_data = SensorsDataManager.load()
        
        for esp in sensors_data['esp_modules']:
            if esp.get('ip_address') == ip_address:
                return jsonify(esp)
        
        return jsonify({'error': 'ESP not found'}), 404
        
    except Exception as e:
        logger.error(f"Error getting ESP info: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/register', methods=['POST'])
def register_esp():
    """Register or update ESP32 module"""
    try:
        data = request.json
        required = ['name', 'location', 'ip_address', 'sensors']
        
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        location_icons = {
            'kitchen': '🍳', 'living': '🛋️', 'bedroom': '🛏️',
            'bathroom': '🚿', 'outdoor': '🌤️', 'other': '📍'
        }
        
        icon = location_icons.get(data['location'], '📍')
        
        # Load current data
        sensors_data = SensorsDataManager.load()
        
        # Check if IP already exists
        existing_esp = None
        for esp in sensors_data['esp_modules']:
            if esp['ip_address'] == data['ip_address']:
                existing_esp = esp
                break
        
        if existing_esp:
            # Update existing
            existing_esp['name'] = data['name']
            existing_esp['location'] = data['location']
            existing_esp['icon'] = icon
            existing_esp['sensors'] = [
                {
                    'name': s['name'],
                    'type': s['type'],
                    'unit': s['unit'],
                    'icon': s.get('icon', '📊'),
                    'value': None,
                    'last_updated': None
                }
                for s in data['sensors']
            ]
            esp_id = existing_esp.get('id', len(sensors_data['esp_modules']))
        else:
            # Create new
            esp_id = max([esp.get('id', 0) for esp in sensors_data['esp_modules']], default=0) + 1
            
            new_esp = {
                'id': esp_id,
                'name': data['name'],
                'location': data['location'],
                'icon': icon,
                'ip_address': data['ip_address'],
                'online': False,
                'last_seen': None,
                'sensors': [
                    {
                        'name': s['name'],
                        'type': s['type'],
                        'unit': s['unit'],
                        'icon': s.get('icon', '📊'),
                        'value': None,
                        'last_updated': None
                    }
                    for s in data['sensors']
                ]
            }
            
            sensors_data['esp_modules'].append(new_esp)
        
        SensorsDataManager.save(sensors_data)
        
        db_manager.log_event('INFO', f'ESP registered/updated: {data["name"]} ({data["ip_address"]})')
        logger.info(f"ESP {data['name']} registered with IP {data['ip_address']}")
        
        return jsonify({'success': True, 'esp_id': esp_id})
        
    except Exception as e:
        logger.error(f"Error registering ESP: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/data', methods=['POST'])
def receive_esp_data():
    """Receive sensor data from ESP32"""
    try:
        data = request.json
        
        if not data or 'ip_address' not in data or 'sensors' not in data:
            return jsonify({'error': 'Missing ip_address or sensors'}), 400
        
        ip_address = data['ip_address']
        sensor_data = data['sensors']
        
        # Update in JSON
        success = SensorsDataManager.update_module_data(ip_address, sensor_data)
        
        if not success:
            return jsonify({'error': 'ESP not registered'}), 404
        
        logger.info(f"Data received from {ip_address}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error receiving data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/<int:esp_id>', methods=['PUT'])
def update_esp(esp_id):
    """Update ESP32 module configuration"""
    try:
        data = request.json
        sensors_data = SensorsDataManager.load()
        
        for esp in sensors_data['esp_modules']:
            if esp['id'] == esp_id:
                if 'name' in data:
                    esp['name'] = data['name']
                if 'location' in data:
                    esp['location'] = data['location']
                    location_icons = {
                        'kitchen': '🍳', 'living': '🛋️', 'bedroom': '🛏️',
                        'bathroom': '🚿', 'outdoor': '🌤️', 'other': '📍'
                    }
                    esp['icon'] = location_icons.get(data['location'], '📍')
                
                SensorsDataManager.save(sensors_data)
                db_manager.log_event('INFO', f'ESP updated: {esp["name"]}')
                return jsonify({'success': True})
        
        return jsonify({'error': 'ESP not found'}), 404
        
    except Exception as e:
        logger.error(f"Error updating ESP: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/<int:esp_id>', methods=['DELETE'])
def delete_esp(esp_id):
    """Delete ESP32 module"""
    try:
        sensors_data = SensorsDataManager.load()
        
        initial_len = len(sensors_data['esp_modules'])
        sensors_data['esp_modules'] = [
            esp for esp in sensors_data['esp_modules'] if esp['id'] != esp_id
        ]
        
        if len(sensors_data['esp_modules']) == initial_len:
            return jsonify({'error': 'ESP not found'}), 404
        
        SensorsDataManager.save(sensors_data)
        db_manager.log_event('INFO', f'ESP deleted: ID {esp_id}')
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting ESP: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Get or update system settings"""
    if request.method == 'GET':
        config = ConfigManager.load()
        return jsonify(config)
    
    elif request.method == 'POST':
        config = ConfigManager.load()
        data = request.json
        
        config.update(data)
        ConfigManager.save(config)
        
        db_manager.log_event('INFO', 'Settings updated')
        return jsonify({'success': True})

@app.route('/api/logs')
def get_logs():
    """Get system logs"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT level, message, timestamp 
            FROM system_logs 
            ORDER BY timestamp DESC 
            LIMIT 100
        ''')
        
        logs = [
            {'level': level, 'message': msg, 'timestamp': ts}
            for level, msg, ts in cursor.fetchall()
        ]
        
        conn.close()
        return jsonify({'logs': logs})
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500

# ========== BACKGROUND TASKS ==========

def health_monitor():
    """Monitor ESP health"""
    while True:
        try:
            sensors_data = SensorsDataManager.load()
            now = datetime.now()
            
            for esp in sensors_data['esp_modules']:
                # Check last seen (2 minutes timeout)
                if esp.get('last_seen'):
                    last_seen = datetime.fromisoformat(esp['last_seen'])
                    if (now - last_seen).total_seconds() > 120:
                        esp['online'] = False
                        for sensor in esp['sensors']:
                            sensor['value'] = None
                else:
                    esp['online'] = False
            
            SensorsDataManager.save(sensors_data)
            
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
        
        time.sleep(30)

def cleanup_old_data():
    """Clean up old logs"""
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM system_logs WHERE timestamp < datetime('now', '-30 days')")
            
            conn.commit()
            conn.close()
            logger.info("Old logs cleaned")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        time.sleep(86400)  # Once per day

# ========== MAIN ==========

if __name__ == '__main__':
    db_manager.log_event('INFO', 'MarvinLink starting')
    logger.info("Starting MarvinLink")
    
    # Start background tasks
    threading.Thread(target=health_monitor, daemon=True).start()
    threading.Thread(target=cleanup_old_data, daemon=True).start()
    
    logger.info("Background tasks started")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"Failed to start: {e}")
        db_manager.log_event('ERROR', f'Failed to start: {e}')