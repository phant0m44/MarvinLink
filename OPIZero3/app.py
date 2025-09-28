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

app = Flask(__name__)

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
            self.insert_demo_data()
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def insert_demo_data(self):
        """Insert demo data if database is empty"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if demo data exists
            cursor.execute('SELECT COUNT(*) FROM esp_modules')
            if cursor.fetchone()[0] > 0:
                conn.close()
                return
            
            # Insert demo ESP32 modules
            esp_modules = [
                ('ESP32-Kitchen', 'Кухня', '🍳', '192.168.1.100', 'AA:BB:CC:DD:EE:01', 1),
                ('ESP32-Living', 'Вітальня', '🛋️', None, None, 0)  # Offline module
            ]
            
            cursor.executemany('''
                INSERT INTO esp_modules (name, location, location_icon, ip_address, mac_address, is_online)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', esp_modules)
            
            # Insert sensors for Kitchen ESP
            kitchen_sensors = [
                (1, 'temperature', 'Температура', '°C', '🌡️', 23.2, 1),
                (1, 'humidity', 'Вологість', '%', '💧', 64.5, 1),
                (1, 'pressure', 'Тиск', 'hPa', '📊', 1013.2, 1),
                (1, 'light', 'Освітлення', 'lx', '💡', 425.0, 1)
            ]
            
            cursor.executemany('''
                INSERT INTO sensors (esp_id, sensor_type, sensor_name, unit, icon, last_value, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', kitchen_sensors)
            
            # Insert sensors for Living room ESP (offline)
            living_sensors = [
                (2, 'temperature', 'Температура', '°C', '🌡️', None, 1),
                (2, 'humidity', 'Вологість', '%', '💧', None, 1)
            ]
            
            cursor.executemany('''
                INSERT INTO sensors (esp_id, sensor_type, sensor_name, unit, icon, last_value, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', living_sensors)
            
            # Insert default settings
            default_settings = [
                ('user_name', 'Чед'),
                ('weather_city', 'Київ'),
                ('timezone', 'Europe/Kiev'),
                ('weather_api_key', '')  # User should add their API key
            ]
            
            cursor.executemany('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', default_settings)
            
            conn.commit()
            conn.close()
            logger.info("Demo data inserted successfully")
            
        except Exception as e:
            logger.error(f"Failed to insert demo data: {e}")
    
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
        """Get CPU temperature"""
        try:
            temp_paths = [
                '/sys/class/thermal/thermal_zone0/temp',
                '/sys/class/thermal/thermal_zone1/temp'
            ]
            
            for path in temp_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        temp = int(f.read().strip()) / 1000.0
                        return round(temp, 1)
            
            # Fallback: try vcgencmd for Raspberry Pi compatibility
            try:
                result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    temp_str = result.stdout.strip()
                    temp = float(temp_str.split('=')[1].replace("'C", ""))
                    return round(temp, 1)
            except:
                pass
            
            return None
        except Exception:
            return None
    
    @staticmethod
    def get_ram_usage():
        """Get RAM usage in MB"""
        try:
            memory = psutil.virtual_memory()
            used_mb = memory.used // (1024 * 1024)
            return used_mb
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

# Load HTML template
HTML_FILE = 'templates/index.html'
try:
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        HTML_TEMPLATE = f.read()
except FileNotFoundError:
    HTML_TEMPLATE = '''
    <!DOCTYPE html>
    <html><head><title>MarvinLink - Template Missing</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px; background: #1e1b4b; color: white;">
    <h1>Template Missing</h1>
    <p>Please ensure marvinlink_complete.html is in the same directory as this script.</p>
    </body></html>
    '''

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status():
    """Get complete system status"""
    try:
        conn = sqlite3.connect(CONFIG['db_path'])
        cursor = conn.cursor()
        
        # Get system info
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
                sensors.append({
                    'name': sensor_name,
                    'value': last_value,
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
        
        location_icon = location_icons.get(data['location'], '📍')
        
        # Insert ESP module
        cursor.execute('''
            INSERT OR REPLACE INTO esp_modules (name, location, location_icon, mac_address, ip_address, is_online)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (data['name'], data['location'], location_icon, data['mac_address'], data.get('ip_address')))
        
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
    """Get weather data for city (mock implementation)"""
    try:
        # This is a mock implementation
        # Replace with actual weather API like OpenWeatherMap
        
        import random
        
        # Mock weather data
        conditions = [
            {'temp': 22, 'desc': 'Сонячно', 'icon': '☀️'},
            {'temp': 18, 'desc': 'Хмарно', 'icon': '☁️'},
            {'temp': 15, 'desc': 'Дощ', 'icon': '🌧️'},
            {'temp': 8, 'desc': 'Сніг', 'icon': '❄️'},
            {'temp': 12, 'desc': 'Туман', 'icon': '🌫️'}
        ]
        
        weather = random.choice(conditions)
        weather['city'] = city
        
        return jsonify(weather)
        
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        return jsonify({'error': str(e)}), 500

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
            
            # Mark ESP as offline if not seen for more than 2 minutes
            cursor.execute('''
                UPDATE esp_modules 
                SET is_online = 0 
                WHERE last_seen < datetime('now', '-2 minutes')
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
    logger.info("Starting MarvinLink Smart Home System")
    
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