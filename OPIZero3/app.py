import os
import json
import sqlite3
import logging
import threading
import time
import subprocess
import psutil
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/marvinlink.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'db_path': 'marvinlink.db',
    'host': '0.0.0.0',
    'port': 5000
}

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # ESP32 modules table
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
            
            # Sensors table with predefined types
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
            
            # System settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
            # DON'T insert demo data - start clean
            self.check_initial_settings()
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def check_initial_settings(self):
        """Insert only basic settings, no demo data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert only default settings if they don't exist
            cursor.execute('SELECT COUNT(*) FROM settings')
            if cursor.fetchone()[0] == 0:
                default_settings = [
                    ('user_name', 'Чед'),
                    ('weather_city', 'Київ'),
                    ('timezone', 'Europe/Kiev'),
                    ('system_initialized', 'true')
                ]
                
                cursor.executemany('''
                    INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
                ''', default_settings)
                
                conn.commit()
                logger.info("Initial settings inserted")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to insert initial settings: {e}")
    
    def log_event(self, level, message):
        """Log system event"""
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

class SystemMonitor:
    @staticmethod
    def get_cpu_temperature():
        """Get CPU temperature for Orange Pi Zero 3"""
        try:
            # Orange Pi Zero 3 specific thermal zones
            temp_paths = [
                '/sys/class/thermal/thermal_zone0/temp',
                '/sys/class/thermal/thermal_zone1/temp',
                '/sys/devices/virtual/thermal/thermal_zone0/temp'
            ]
            
            for path in temp_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        temp = int(f.read().strip()) / 1000.0
                        return round(temp, 1)
            
            # Fallback for other thermal interfaces
            try:
                result = subprocess.run(['cat', '/sys/class/hwmon/hwmon0/temp1_input'], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    temp = int(result.stdout.strip()) / 1000.0
                    return round(temp, 1)
            except:
                pass
            
            return None
        except Exception:
            return None
    
    @staticmethod
    def get_ram_usage():
        """Get RAM usage in MB using psutil for accuracy"""
        try:
            memory = psutil.virtual_memory()
            used_mb = memory.used // (1024 * 1024)
            return used_mb
        except Exception:
            return None
    
    @staticmethod
    def get_cpu_usage():
        """Get CPU usage percentage"""
        try:
            return psutil.cpu_percent(interval=1)
        except Exception:
            return None
    
    @staticmethod
    def ping_host(ip_address):
        """Check if host is reachable"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', ip_address],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

# Initialize components
db_manager = DatabaseManager(CONFIG['db_path'])
system_monitor = SystemMonitor()

# Load HTML template from the fixed version
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MarvinLink - Smart Home</title>
    <style>
        /* Include the fixed CSS from the artifact here */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e1b4b 0%, #3730a3 50%, #7c3aed 100%);
            min-height: 100vh; color: white; overflow-x: hidden;
        }
        /* Add all the CSS styles from the fixed version here */
    </style>
</head>
<body>
    <!-- Include the fixed HTML from the artifact here -->
    <div id="app">Loading MarvinLink...</div>
    <script>
        // The frontend will load via static file serving
        window.location.href = '/static/index.html';
    </script>
</body>
</html>'''

@app.route('/')
def index():
    """Serve main dashboard"""
    # Try to serve the static file first
    try:
        with open('static/index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return HTML_TEMPLATE

@app.route('/api/system-status')
def get_system_status():
    """Get real system status for Orange Pi"""
    try:
        cpu_temp = system_monitor.get_cpu_temperature()
        ram_usage = system_monitor.get_ram_usage()
        cpu_usage = system_monitor.get_cpu_usage()
        
        return jsonify({
            'cpu_temp': cpu_temp,
            'ram_usage': ram_usage,
            'cpu_usage': cpu_usage,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def get_status():
    """Get complete system status"""
    try:
        conn = sqlite3.connect(CONFIG['db_path'])
        cursor = conn.cursor()
        
        # Get real system info
        cpu_temp = system_monitor.get_cpu_temperature()
        ram_usage = system_monitor.get_ram_usage()
        
        # Get ESP modules count
        cursor.execute('SELECT COUNT(*) FROM esp_modules WHERE is_online = 1')
        active_esp = cursor.fetchone()[0]
        
        # Get total sensors count
        cursor.execute('SELECT COUNT(*) FROM sensors WHERE is_enabled = 1')
        total_sensors = cursor.fetchone()[0]
        
        # Get ESP modules with sensors
        cursor.execute('''
            SELECT id, name, location, location_icon, ip_address, is_online, last_seen
            FROM esp_modules
            ORDER BY is_online DESC, name
        ''')
        
        esp_modules = []
        for esp in cursor.fetchall():
            esp_id, name, location, location_icon, ip_address, is_online, last_seen = esp
            
            # Get sensors for this ESP
            cursor.execute('''
                SELECT sensor_name, last_value, unit, icon, sensor_type, is_enabled
                FROM sensors
                WHERE esp_id = ? AND is_enabled = 1
                ORDER BY sensor_name
            ''', (esp_id,))
            
            sensors = []
            for sensor in cursor.fetchall():
                sensor_name, last_value, unit, sensor_icon, sensor_type, is_enabled = sensor
                
                # Only show values for online modules
                display_value = last_value if is_online else None
                
                sensors.append({
                    'name': sensor_name,
                    'value': display_value,
                    'unit': unit,
                    'icon': sensor_icon,
                    'type': sensor_type
                })
            
            esp_modules.append({
                'id': esp_id,
                'name': name,
                'location': location,
                'icon': location_icon,
                'ip_address': ip_address,
                'online': bool(is_online),
                'last_seen': last_seen,
                'sensors': sensors
            })
        
        conn.close()
        
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
        required_fields = ['name', 'location', 'mac_address', 'sensors']
        
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = sqlite3.connect(CONFIG['db_path'])
        cursor = conn.cursor()
        
        # Map location to icon
        location_icons = {
            'kitchen': '🍳',
            'living': '🛋️',
            'bedroom': '🛏️',
            'bathroom': '🚿',
            'outdoor': '🌤️',
            'other': '📍'
        }
        
        location_names = {
            'kitchen': 'Кухня',
            'living': 'Вітальня',
            'bedroom': 'Спальня',
            'bathroom': 'Ванна',
            'outdoor': 'Надворі',
            'other': 'Інше'
        }
        
        location_icon = location_icons.get(data['location'], '📍')
        location_name = location_names.get(data['location'], data['location'])
        
        # Insert ESP module
        cursor.execute('''
            INSERT OR REPLACE INTO esp_modules (name, location, location_icon, mac_address, ip_address, is_online)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (data['name'], location_name, location_icon, data['mac_address'], data.get('ip_address')))
        
        esp_id = cursor.lastrowid
        
        # Insert sensors based on predefined template
        for sensor in data['sensors']:
            cursor.execute('''
                INSERT INTO sensors (esp_id, sensor_type, sensor_name, unit, icon, is_enabled)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (esp_id, sensor['type'], sensor['name'], sensor['unit'], sensor.get('icon', '📊')))
        
        conn.commit()
        conn.close()
        
        db_manager.log_event('INFO', f'New ESP module registered: {data["name"]}')
        logger.info(f"ESP module registered: {data}")
        
        return jsonify({'success': True, 'esp_id': esp_id})
        
    except Exception as e:
        logger.error(f"Error registering ESP: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/<int:esp_id>/delete', methods=['DELETE'])
def delete_esp(esp_id):
    """Delete ESP32 module and its sensors"""
    try:
        conn = sqlite3.connect(CONFIG['db_path'])
        cursor = conn.cursor()
        
        # Get ESP name for logging
        cursor.execute('SELECT name FROM esp_modules WHERE id = ?', (esp_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'ESP module not found'}), 404
        
        esp_name = result[0]
        
        # Delete sensor data history
        cursor.execute('''
            DELETE FROM sensor_data 
            WHERE sensor_id IN (SELECT id FROM sensors WHERE esp_id = ?)
        ''', (esp_id,))
        
        # Delete sensors
        cursor.execute('DELETE FROM sensors WHERE esp_id = ?', (esp_id,))
        
        # Delete ESP module
        cursor.execute('DELETE FROM esp_modules WHERE id = ?', (esp_id,))
        
        conn.commit()
        conn.close()
        
        db_manager.log_event('INFO', f'ESP module deleted: {esp_name}')
        logger.info(f"ESP module {esp_name} deleted")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting ESP: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp/<int:esp_id>/data', methods=['POST'])
def receive_esp_data(esp_id):
    """Receive sensor data from ESP32"""
    try:
        data = request.json
        if not data or 'sensors' not in data:
            return jsonify({'error': 'No sensor data provided'}), 400
        
        conn = sqlite3.connect(CONFIG['db_path'])
        cursor = conn.cursor()
        
        # Verify ESP exists
        cursor.execute('SELECT id FROM esp_modules WHERE id = ?', (esp_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'ESP module not found'}), 404
        
        # Update ESP online status
        cursor.execute('''
            UPDATE esp_modules 
            SET is_online = 1, last_seen = CURRENT_TIMESTAMP,
                ip_address = COALESCE(?, ip_address)
            WHERE id = ?
        ''', (data.get('ip_address'), esp_id))
        
        # Update sensor values
        for sensor_type, value in data['sensors'].items():
            # Update current value
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
        
        # Clean old history (keep last 1000 entries per sensor)
        cursor.execute('''
            DELETE FROM sensor_data 
            WHERE id NOT IN (
                SELECT id FROM sensor_data 
                WHERE sensor_id IN (SELECT id FROM sensors WHERE esp_id = ?)
                ORDER BY timestamp DESC 
                LIMIT 1000
            )
        ''', (esp_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Data received from ESP {esp_id}: {data}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error receiving ESP data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Get or update system settings"""
    conn = sqlite3.connect(CONFIG['db_path'])
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('SELECT key, value FROM settings')
        settings = dict(cursor.fetchall())
        conn.close()
        return jsonify(settings)
    
    elif request.method == 'POST':
        data = request.json
        for key, value in data.items():
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
        
        conn.commit()
        conn.close()
        
        db_manager.log_event('INFO', 'Settings updated')
        return jsonify({'success': True})

@app.route('/api/weather/<city>')
def get_weather(city):
    """Get weather data using free wttr.in service"""
    try:
        import requests
        
        response = requests.get(
            f'https://wttr.in/{city}?format=%t,%C&lang=uk',
            timeout=10,
            headers={'User-Agent': 'MarvinLink/1.0'}
        )
        
        if response.status_code == 200:
            data = response.text.strip()
            parts = data.split(',')
            
            if len(parts) >= 2:
                temp = int(''.join(filter(str.isdigit, parts[0].replace('-', 'MINUS'))))
                if 'MINUS' in parts[0]:
                    temp = -temp
                
                description = parts[1].strip()
                
                weather = {
                    'temp': temp,
                    'desc': description,
                    'city': city
                }
                
                return jsonify(weather)
        
        # Fallback
        return jsonify({
            'temp': '--',
            'desc': 'Немає даних',
            'city': city
        })
        
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        return jsonify({
            'temp': '--',
            'desc': 'Помилка з\'єднання',
            'city': city
        })

@app.route('/api/logs')
def get_logs():
    """Get system logs"""
    try:
        conn = sqlite3.connect(CONFIG['db_path'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT level, message, timestamp 
            FROM system_logs 
            ORDER BY timestamp DESC 
            LIMIT 100
        ''')
        
        logs = []
        for log in cursor.fetchall():
            level, message, timestamp = log
            logs.append({
                'level': level,
                'message': message,
                'timestamp': timestamp
            })
        
        conn.close()
        return jsonify({'logs': logs})
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500

def health_monitor():
    """Background task to monitor ESP health"""
    while True:
        try:
            conn = sqlite3.connect(CONFIG['db_path'])
            cursor = conn.cursor()
            
            # Get all ESP modules with IP addresses
            cursor.execute('''
                SELECT id, ip_address FROM esp_modules 
                WHERE ip_address IS NOT NULL
            ''')
            
            esp_modules = cursor.fetchall()
            
            for esp_id, ip_address in esp_modules:
                # Check if ESP is reachable
                is_online = system_monitor.ping_host(ip_address)
                
                # Update status
                cursor.execute('''
                    UPDATE esp_modules 
                    SET is_online = ? 
                    WHERE id = ?
                ''', (is_online, esp_id))
                
                # If offline, clear sensor values
                if not is_online:
                    cursor.execute('''
                        UPDATE sensors 
                        SET last_value = NULL 
                        WHERE esp_id = ?
                    ''', (esp_id,))
            
            # Mark ESP as offline if not seen for more than 2 minutes
            cursor.execute('''
                UPDATE esp_modules 
                SET is_online = 0 
                WHERE last_seen < datetime('now', '-2 minutes')
            ''')
            
            # Clear sensor values for offline modules
            cursor.execute('''
                UPDATE sensors 
                SET last_value = NULL 
                WHERE esp_id IN (
                    SELECT id FROM esp_modules WHERE is_online = 0
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
        
        time.sleep(30)  # Check every 30 seconds

def cleanup_old_data():
    """Clean up old sensor data and logs"""
    while True:
        try:
            conn = sqlite3.connect(CONFIG['db_path'])
            cursor = conn.cursor()
            
            # Keep only last 7 days of sensor data
            cursor.execute('''
                DELETE FROM sensor_data 
                WHERE timestamp < datetime('now', '-7 days')
            ''')
            
            # Keep only last 30 days of logs
            cursor.execute('''
                DELETE FROM system_logs 
                WHERE timestamp < datetime('now', '-30 days')
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Old data cleaned up")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        time.sleep(3600)  # Run every hour

if __name__ == '__main__':
    # Log startup
    db_manager.log_event('INFO', 'MarvinLink system starting up')
    logger.info("Starting MarvinLink Smart Home System - Clean Version")
    
    # Start background tasks
    health_thread = threading.Thread(target=health_monitor, daemon=True)
    cleanup_thread = threading.Thread(target=cleanup_old_data, daemon=True)
    
    health_thread.start()
    cleanup_thread.start()
    
    logger.info("Background tasks started")
    
    # Start Flask app
    try:
        app.run(
            host=CONFIG['host'],
            port=CONFIG['port'],
            debug=False,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask app: {e}")
        db_manager.log_event('ERROR', f'Failed to start Flask app: {e}')