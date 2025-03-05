import eventlet
eventlet.monkey_patch()

import io
import random
from threading import Thread, Lock
from flask import Flask, request, render_template, jsonify, send_file
from flask_socketio import SocketIO, emit
import serial
import time
import csv
import os
from datetime import datetime
import plotly.graph_objs as go
import plotly.io as pio

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

port = "COM7"  # Change to the correct port
baud_rate = 115200

try:
    ser = serial.Serial(port, baud_rate, timeout=1)
    time.sleep(2)
except serial.SerialException:
    print("No ESP detected, switching to simulation mode.")
    ser = None  # No real connection

collecting_data = False
data_lock = Lock()
data = []
start_time = None

def save_to_csv(timestamp, value, patient_id):
    global start_time
    filename = f'results/{patient_id}_sensor_data.csv'
    file_exists = os.path.isfile(filename)

    os.makedirs('results', exist_ok=True)  # Create the 'results' directory if it doesn't exist

    if start_time is None:
        start_time = timestamp

    elapsed_time = (timestamp - start_time).total_seconds()

    try:
        with open(filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['Timestamp', 'Sensor Value', 'Elapsed Time (s)'])
            writer.writerow([timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'), value, elapsed_time])
    except IOError as e:
        print(f"Error writing to CSV file: {e}")


def get_sensor_value():
    if ser and ser.is_open:
        data = ser.readline().decode('utf-8').strip()
        return int(data) if data.isdigit() else random.randint(100, 500)
    return random.randint(100, 500)

def collect_data(patient_id):
    global collecting_data, data, start_time
    while collecting_data:
        timestamp = datetime.now()
        sensor_value = get_sensor_value()
        data_point = {"timestamp": timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'), "sensor_value": sensor_value}
        data.append(data_point)
        socketio.emit('data', data_point) #
        save_to_csv(timestamp, sensor_value, patient_id)
        time.sleep(1)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        patient_id = request.form['patient_id']
        return render_template('data.html', patient_id=patient_id)
    return render_template('index.html')

@app.route('/start_import_data/<patient_id>')
def start_import_data(patient_id):
    global collecting_data, data, data_thread, start_time
    if not collecting_data:
        collecting_data = True
        data = []  # Clear the data list when starting data import
        start_time = None  # Reset the start time
        data_thread = Thread(target=collect_data, args=(patient_id,))
        data_thread.start()
        return jsonify({"status": "collecting data"})

@app.route('/stop_import_data/<patient_id>')
def stop_import_data(patient_id):
    global collecting_data
    collecting_data = False
    if data_thread:
        data_thread.join()
    return jsonify({"status": "stopped collecting data"})

@app.route('/get_data')
def get_data():
    global data
    return jsonify(data)

@app.route('/export_plot/<patient_id>')
def export_plot(patient_id):
    global data
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[d['timestamp'] for d in data], y=[d['sensor_value'] for d in data], mode='lines', name='Sensor Value'))
    fig.update_layout(title=f'Sensor Data for Patient {patient_id}', xaxis_title='Time', yaxis_title='Sensor Value')
    filename = f'results/{patient_id}_sensor_data_plot.html'
    pio.write_html(fig, filename)
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)