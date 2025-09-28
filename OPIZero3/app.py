from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import sqlite3
import asyncio
from datetime import datetime
import threading
import time
import requests
import socket
from bleak import BleakClient, BleakScanner
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database initialization
def init_db():
    conn = sqlite3.connect('marvinlink.db')
    c = conn.cursor()
    
    # Create sensors table
    c.execute('''CREATE TABLE IF NOT EXISTS sensors
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  room TEXT NOT NULL,
                  ip_address TEXT,
                  mac_address TEXT,
                  sensor_type TEXT,
                  last_seen TIMESTAMP,
                  is_online BOOLEAN DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create sensor_data table
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sensor_id INTEGER,
                  temperature REAL,
                  humidity REAL,
                  light_level REAL,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (sensor_id) REFERENCES sensors (id))''')
    
    # Create system_logs table
    c.execute('''CREATE TABLE IF NOT EXISTS system_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  level TEXT,
                  message TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

# Bluetooth configuration
MARVINLINK_SERVICE_UUID = "12345678-1234-5678-9012-123456789012"
WIFI_SSID_CHAR_UUID = "12345678-1234-5678-9012-123456789013"
WIFI_PASS_CHAR_UUID = "12345678-1234-5678-9012-123456789014"
DEVICE_NAME_CHAR_UUID = "12345678-1234-5678-9012-123456789015"
STATIC_IP_CHAR_UUID = "12345678-1234-5678-9012-123456789016"

class SensorManager:
    def __init__(self):
        self.sensors = {}
        self.ble_devices = {}
        
    def add_sensor(self, name, room, ip_address=None, mac_address=None):
        conn = sqlite3.connect('marvinlink.db')
        c = conn.cursor()
        c.execute('''INSERT INTO sensors (name, room, ip_address, mac_address, sensor_type)
                     VALUES (?, ?, ?, ?, ?)''', 
                  (name, room, ip_address, mac_address, 'ESP32-C3'))
        sensor_id = c.lastrowid
        conn.commit()
        conn.close()
        
        log_system_event('INFO', f'New sensor added: {name} in {room}')
        return sensor_id
    
    def get_sensors(self):
        conn = sqlite3.connect('marvinlink.db')
        c = conn.cursor()
        c.execute('''SELECT id, name, room, ip_address, is_online, last_seen 
                     FROM sensors ORDER BY room, name''')
        sensors = c.fetchall()
        conn.close()
        
        sensor_list = []
        for sensor in sensors:
            sensor_data = {
                'id': sensor[0],
                'name': sensor[1],
                'room': sensor[2],
                'ip_address': sensor[3],
                'is_online': sensor[4],
                'last_seen': sensor[5]
            }
            
            # Get latest sensor reading
            latest_data = self.get_latest_sensor_data(sensor[0])
            sensor_data.update(latest_data)
            sensor_list.append(sensor_data)
        
        return sensor_list
    
    def get_latest_sensor_data(self, sensor_id):
        conn = sqlite3.connect('marvinlink.db')
        c = conn.cursor()
        c.execute('''SELECT temperature, humidity, light_level, timestamp 
                     FROM sensor_data 
                     WHERE sensor_id = ? 
                     ORDER BY timestamp DESC 
                     LIMIT 1''', (sensor_id,))
        data = c.fetchone()
        conn.close()
        
        if data:
            return {
                'temperature': data[0],
                'humidity': data[1],
                'light_level': data[2],
                'last_reading': data[3]
            }
        return {
            'temperature': None,
            'humidity': None,
            'light_level': None,
            'last_reading': None
        }
    
    def update_sensor_status(self, sensor_id, is_online):
        conn = sqlite3.connect('marvinlink.db')
        c = conn.cursor()
        c.execute('''UPDATE sensors 
                     SET is_online = ?, last_seen = CURRENT_TIMESTAMP 
                     WHERE id = ?''', (is_online, sensor_id))
        conn.commit()
        conn.close()
    
    def add_sensor_reading(self, sensor_id, temperature=None, humidity=None, light_level=None):
        conn = sqlite3.connect('marvinlink.db')
        c = conn.cursor()
        c.execute('''INSERT INTO sensor_data (sensor_id, temperature, humidity, light_level)
                     VALUES (?, ?, ?, ?)''', (sensor_id, temperature, humidity, light_level))
        conn.commit()
        conn.close()

def log_system_event(level, message):
    conn = sqlite3.connect('marvinlink.db')
    c = conn.cursor()
    c.execute('INSERT INTO system_logs (level, message) VALUES (?, ?)', (level, message))
    conn.commit()
    conn.close()
    logger.info(f"[{level}] {message}")

# Initialize components
sensor_manager = SensorManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sensors')
def get_sensors():
    """Get all sensors with their latest data"""
    sensors = sensor_manager.get_sensors()
    return jsonify({
        'sensors': sensors,
        'count': len(sensors)
    })

@app.route('/api/sensors/add', methods=['POST'])
def add_sensor():
    """Add new sensor via BLE configuration"""
    data = request.json
    
    sensor_id = sensor_manager.add_sensor(
        name=data.get('name'),
        room=data.get('room'),
        ip_address=data.get('ip_address'),
        mac_address=data.get('mac_address')
    )
    
    return jsonify({
        'success': True,
        'sensor_id': sensor_id,
        'message': 'Sensor added successfully'
    })

@app.route('/api/ble/scan')
def ble_scan():
    """Scan for available BLE devices"""
    try:
        # This would be implemented with actual BLE scanning
        # For now, return mock data
        devices = [
            {
                'name': 'MarvinLink-001',
                'address': 'AA:BB:CC:DD:EE:FF',
                'rssi': -45
            }
        ]
        return jsonify({'devices': devices})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ble/configure', methods=['POST'])
async def configure_ble_device():
    """Configure ESP32-C3 via Bluetooth"""
    data = request.json
    device_address = data.get('device_address')
    config = data.get('config')
    
    try:
        async with BleakClient(device_address) as client:
            # Write Wi-Fi configuration
            await client.write_gatt_char(
                WIFI_SSID_CHAR_UUID, 
                config['wifi_ssid'].encode('utf-8')
            )
            await client.write_gatt_char(
                WIFI_PASS_CHAR_UUID, 
                config['wifi_password'].encode('utf-8')
            )
            await client.write_gatt_char(
                DEVICE_NAME_CHAR_UUID, 
                config['device_name'].encode('utf-8')
            )
            
            if config.get('static_ip'):
                await client.write_gatt_char(
                    STATIC_IP_CHAR_UUID, 
                    config['static_ip'].encode('utf-8')
                )
            
            log_system_event('INFO', f'BLE configuration sent to {device_address}')
            
        return jsonify({
            'success': True,
            'message': 'Device configured successfully'
        })
        
    except Exception as e:
        log_system_event('ERROR', f'BLE configuration failed: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/sensor/<int:sensor_id>/data', methods=['POST'])
def receive_sensor_data():
    """Receive sensor data from ESP32-C3"""
    data = request.json
    sensor_id = request.view_args['sensor_id']
    
    # Validate sensor exists
    sensors = sensor_manager.get_sensors()
    if not any(s['id'] == sensor_id for s in sensors):
        return jsonify({'error': 'Sensor not found'}), 404
    
    # Add sensor reading
    sensor_manager.add_sensor_reading(
        sensor_id=sensor_id,
        temperature=data.get('temperature'),
        humidity=data.get('humidity'),
        light_level=data.get('light_level')
    )
    
    # Update sensor status
    sensor_manager.update_sensor_status(sensor_id, True)
    
    return jsonify({'success': True})

@app.route('/api/system/info')
def system_info():
    """Get system information"""
    try:
        # Get CPU temperature (Orange Pi specific)
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                cpu_temp = int(f.read().strip()) / 1000
        except:
            cpu_temp = 56.0  # Mock data
        
        # Get memory usage
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
            # Parse memory info (simplified)
            mem_total = 175 * 1024 * 1024  # Mock 175TB
            mem_free = 5.8 * 1024 * 1024   # Mock 5.8GB free
        except:
            mem_total = 175 * 1024 * 1024
            mem_free = 5.8 * 1024 * 1024
        
        # Get sensor count
        sensors = sensor_manager.get_sensors()
        active_sensors = len([s for s in sensors if s['is_online']])
        
        return jsonify({
            'cpu_temperature': cpu_temp,
            'memory_total': mem_total,
            'memory_free': mem_free,
            'sensors_total': len(sensors),
            'sensors_active': active_sensors,
            'sync_percentage': 86.92  # Mock sync status
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """Get system logs"""
    conn = sqlite3.connect('marvinlink.db')
    c = conn.cursor()
    c.execute('SELECT level, message, timestamp FROM system_logs ORDER BY timestamp DESC LIMIT 50')
    logs = c.fetchall()
    conn.close()
    
    log_list = []
    for log in logs:
        log_list.append({
            'level': log[0],
            'message': log[1],
            'timestamp': log[2]
        })
    
    return jsonify({'logs': log_list})

def ping_sensor(ip_address):
    """Check if sensor is reachable"""
    try:
        response = requests.get(f"http://{ip_address}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def sensor_health_check():
    """Background task to check sensor health"""
    while True:
        try:
            sensors = sensor_manager.get_sensors()
            for sensor in sensors:
                if sensor['ip_address']:
                    is_online = ping_sensor(sensor['ip_address'])
                    sensor_manager.update_sensor_status(sensor['id'], is_online)
            
            time.sleep(30)  # Check every 30 seconds
        except Exception as e:
            log_system_event('ERROR', f'Health check failed: {str(e)}')
            time.sleep(60)

def start_background_tasks():
    """Start background monitoring tasks"""
    health_thread = threading.Thread(target=sensor_health_check, daemon=True)
    health_thread.start()

if __name__ == '__main__':
    init_db()
    log_system_event('INFO', 'MarvinLink system starting...')
    
    # Start background tasks
    start_background_tasks()
    
    # Add some mock sensors for demonstration
    try:
        sensor_manager.add_sensor('Kitchen Temperature', 'kitchen', '192.168.0.100')
        sensor_manager.add_sensor('Kitchen Humidity', 'kitchen', '192.168.0.101') 
        sensor_manager.add_sensor('Living Room Temperature', 'livingroom', '192.168.0.102')
        sensor_manager.add_sensor('Living Room Light', 'livingroom', '192.168.0.103')
        
        # Add some mock data
        sensor_manager.add_sensor_reading(1, temperature=12.0)
        sensor_manager.add_sensor_reading(2, humidity=65.0)
        sensor_manager.add_sensor_reading(3, temperature=22.0)
        sensor_manager.add_sensor_reading(4, light_level=450.0)
        
        log_system_event('INFO', 'Demo sensors added')
    except:
        pass  # Sensors might already exist
    
    log_system_event('INFO', 'Flask server started on port 5000')
    app.run(host='0.0.0.0', port=5000, debug=True)
