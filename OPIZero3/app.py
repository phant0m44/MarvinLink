import os
import json
import sqlite3
import logging
import threading
import time
import subprocess
import psutil
import requests
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
DB_PATH = 'marvinlink.db'

# ========== JSON FILE MANAGERS ==========

class ConfigManager:
    """Manages configuration in JSON file"""
    
    @staticmethod
    def load():
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Default config
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
    def update_sensor_value(esp_id, sensor_type, value):
        """Update single sensor value"""
        data = SensorsDataManager.load()
        
        for esp in data['esp_modules']:
            if esp['id'] == esp_id:
                for sensor in esp['sensors']:
                    if sensor['type'] == sensor_type:
                        sensor['value'] = value
                        sensor['last_updated'] = datetime.now().isoformat()
                        break
                esp['last_seen'] = datetime.now().isoformat()
                break
        
        SensorsDataManager.save(data)

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
                ip_address TEXT,
                mac_address TEXT UNIQUE,
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
                is_enabled BOOLEAN DEFAULT 1,
                FOREIGN KEY (esp_id) REFERENCES esp_modules (id)
            )
        ''')
        
        # Sensor data history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id INTEGER,
                value REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sensor_id) REFERENCES sensors (id)
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
                ['ping', '-c', '1', '-W', '2', ip_address],
                capture_output=True,
                timeout=5
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
    """Get complete system status from JSON file"""
    try:
        # Get system info
        cpu_temp = system_monitor.get_cpu_temperature()
        ram_usage = system_monitor.get_ram_usage()
        
        # Load sensor data from JSON
        sensors_data = SensorsDataManager.load()
        esp_modules = sensors_data.get('esp_modules', [])
        
        # Count active ESP and sensors
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

@app.route('/api/esp/register', methods=['POST'])
def register_esp():
    """Register new ESP32 module"""
    try:
        data = request.json
        required = ['name', 'location', 'mac_address', 'sensors']
        
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Location mappings
        location_icons = {
            'kitchen': '🍳', 'living': '🛋️', 'bedroom': '🛏️',
            'bathroom': '🚿', 'outdoor': '🌤️', 'other': '📍'
        }
        location_names = {
            'kitchen': 'Кухня', 'living': 'Вітальня', 'bedroom': 'Спальня',
            'bathroom': 'Ванна', 'outdoor': 'Надворі', 'other': 'Інше'
        }
        
        icon = location_icons.get(data['location'], '📍')
        loc_name = location_names.get(data['location'], data['location'])
        
        # Insert into DB
        cursor.execute('''
            INSERT OR REPLACE INTO esp_modules 
            (name, location, location_icon, mac_address, ip_address, is_online, last_seen)
            VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ''', (data['name'], loc_name, icon, data['mac_address'], data.get('ip_address')))
        
        esp_id = cursor.lastrowid
        
        # Insert sensors
        for sensor in data['sensors']:
            cursor.execute('''
                INSERT INTO sensors (esp_id, sensor_type, sensor_name, unit, icon, is_enabled)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (esp_id, sensor['type'], sensor['name'], sensor['unit'], sensor.get('icon', '📊')))
        
        conn.commit()
        conn.close()
        
        # Add to JSON file
        sensors_data = SensorsDataManager.load()
        
        new_esp = {
            'id': esp_id,
            'name': data['name'],
            'location': loc_name,
            'icon': icon,
            'ip_address': data.get('ip_address'),
            'mac_address': data['mac_address'],
            'online': True,
            'last_seen': datetime.now().isoformat(),
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
        
        # Remove old entry with same MAC
        sensors_data['esp_modules'] = [
            esp for esp in sensors_data['esp_modules'] 
            if esp.get('mac_address') != data['mac_address']
        ]
        sensors_data['esp_modules'].append(new_esp)
        
        SensorsDataManager.save(sensors_data)
        
        db_manager.log_event('INFO', f'ESP registered: {data["name"]}')
        logger.info(f"ESP {data['name']} registered with ID {esp_id}")
        
        return jsonify({'success': True, 'esp_id': esp_id})
        
    except Exception as e:
        logger.error(f"Error registering ESP: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/<int:esp_id>/data', methods=['POST'])
def receive_esp_data(esp_id):
    """Receive sensor data from ESP32"""
    try:
        data = request.json
        if not data or 'sensors' not in data:
            return jsonify({'error': 'No sensor data'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verify ESP exists
        cursor.execute('SELECT id, name FROM esp_modules WHERE id = ?', (esp_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'ESP not found'}), 404
        
        esp_name = result[1]
        
        # Update ESP status in DB
        cursor.execute('''
            UPDATE esp_modules 
            SET is_online = 1, last_seen = CURRENT_TIMESTAMP,
                ip_address = COALESCE(?, ip_address)
            WHERE id = ?
        ''', (data.get('ip_address'), esp_id))
        
        # Update sensor values in DB
        for sensor_type, value in data['sensors'].items():
            cursor.execute('''
                UPDATE sensors 
                SET last_value = ?, last_updated = CURRENT_TIMESTAMP 
                WHERE esp_id = ? AND sensor_type = ?
            ''', (value, esp_id, sensor_type))
            
            # Add to history
            cursor.execute('''
                INSERT INTO sensor_data (sensor_id, value)
                SELECT id, ? FROM sensors 
                WHERE esp_id = ? AND sensor_type = ?
            ''', (value, esp_id, sensor_type))
            
            # Update JSON file
            SensorsDataManager.update_sensor_value(esp_id, sensor_type, value)
        
        conn.commit()
        conn.close()
        
        # Update JSON file ESP status
        sensors_data = SensorsDataManager.load()
        for esp in sensors_data['esp_modules']:
            if esp['id'] == esp_id:
                esp['online'] = True
                esp['last_seen'] = datetime.now().isoformat()
                if data.get('ip_address'):
                    esp['ip_address'] = data['ip_address']
                break
        
        SensorsDataManager.save(sensors_data)
        
        logger.info(f"Data received from {esp_name} (ID: {esp_id})")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error receiving data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/<int:esp_id>/delete', methods=['DELETE'])
def delete_esp(esp_id):
    """Delete ESP32 module"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT name FROM esp_modules WHERE id = ?', (esp_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'ESP not found'}), 404
        
        esp_name = result[0]
        
        # Delete from DB
        cursor.execute('DELETE FROM sensor_data WHERE sensor_id IN (SELECT id FROM sensors WHERE esp_id = ?)', (esp_id,))
        cursor.execute('DELETE FROM sensors WHERE esp_id = ?', (esp_id,))
        cursor.execute('DELETE FROM esp_modules WHERE id = ?', (esp_id,))
        
        conn.commit()
        conn.close()
        
        # Delete from JSON
        sensors_data = SensorsDataManager.load()
        sensors_data['esp_modules'] = [
            esp for esp in sensors_data['esp_modules'] if esp['id'] != esp_id
        ]
        SensorsDataManager.save(sensors_data)
        
        db_manager.log_event('INFO', f'ESP deleted: {esp_name}')
        logger.info(f"ESP {esp_name} deleted")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting ESP: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Get or update system settings from JSON file"""
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
    """Get system logs from database"""
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
    """Monitor ESP health and update status"""
    while True:
        try:
            sensors_data = SensorsDataManager.load()
            
            for esp in sensors_data['esp_modules']:
                if esp.get('ip_address'):
                    # Check if reachable
                    is_online = system_monitor.ping_host(esp['ip_address'])
                    esp['online'] = is_online
                    
                    # Clear sensor values if offline
                    if not is_online:
                        for sensor in esp['sensors']:
                            sensor['value'] = None
                else:
                    esp['online'] = False
            
            # Check last_seen timestamp (2 minutes timeout)
            now = datetime.now()
            for esp in sensors_data['esp_modules']:
                if esp.get('last_seen'):
                    last_seen = datetime.fromisoformat(esp['last_seen'])
                    if (now - last_seen).total_seconds() > 120:
                        esp['online'] = False
                        for sensor in esp['sensors']:
                            sensor['value'] = None
            
            SensorsDataManager.save(sensors_data)
            
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
        
        time.sleep(30)

def cleanup_old_data():
    """Clean up old sensor data"""
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM sensor_data WHERE timestamp < datetime('now', '-7 days')")
            cursor.execute("DELETE FROM system_logs WHERE timestamp < datetime('now', '-30 days')")
            
            conn.commit()
            conn.close()
            logger.info("Old data cleaned")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        time.sleep(3600)

# ========== MAIN ==========

if __name__ == '__main__':
    db_manager.log_event('INFO', 'MarvinLink starting (NO SIMULATION)')
    logger.info("Starting MarvinLink - Real data only")
    
    # Start background tasks
    threading.Thread(target=health_monitor, daemon=True).start()
    threading.Thread(target=cleanup_old_data, daemon=True).start()
    
    logger.info("Background tasks started")
    
    # Start Flask
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"Failed to start: {e}")
        db_manager.log_event('ERROR', f'Failed to start: {e}')