import io
import random
import threading
from threading import Thread
from flask import Flask, request, render_template, jsonify, send_file
import serial
import time
import csv
import os
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt

app = Flask(__name__)

port = "COM7"  # Change to the correct port
baudrate = 115200

try:
    ser = serial.Serial(port, baudrate, timeout=1)
    time.sleep(2)
except serial.SerialException:
    print("No ESP detected, switching to simulation mode.")
    ser = None  # No real connection

collecting_data = False
data_thread = None
data = []

def save_to_csv(timestamp, value, patient_id):
    filename = f'results/{patient_id}_sensor_data.csv'
    file_exists = os.path.isfile(filename)

    os.makedirs('results', exist_ok=True)  # Create the 'results' directory if it doesn't exist

    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Timestamp', 'Sensor Value'])
        writer.writerow([timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'), value])

def get_sensor_value():
    if ser and ser.is_open:
        data = ser.readline().decode('utf-8').strip()
        return int(data) if data.isdigit() else random.randint(100, 500)
    return random.randint(100, 500)

def collect_data(patient_id):
    global collecting_data, data
    while collecting_data:
        timestamp = datetime.now()
        sensor_value = get_sensor_value()
        save_to_csv(timestamp, sensor_value, patient_id)
        data.append({"timestamp": timestamp.strftime('%H:%M:%S.%f'),
                     "sensor_value": sensor_value})
        time.sleep(1)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        patient_id = request.form['patient_id']
        return render_template('data.html', patient_id=patient_id)
    return render_template('index.html')

@app.route('/start_import_data/<patient_id>')
def start_import_data(patient_id):
    global collecting_data, data_thread
    if not collecting_data:
        collecting_data = True
        data_thread = Thread(target=collect_data, args=(patient_id,))
        data_thread.start()
        return jsonify({"status": "collecting data"})

@app.route('/stop_import_data/<patient_id>')
def stop_import_data(patient_id):
    global collecting_data, data
    collecting_data = False
    if data_thread:
        data_thread.join()
    data = []  # Clear the data list
    return jsonify({"status": "stopped collecting data"})

@app.route('/get_data')
def get_data():
    global data
    return jsonify(data)

@app.route('/export_plot/<patient_id>')
def export_plot(patient_id):
    filename = f'results/{patient_id}_sensor_data.csv'
    if not os.path.isfile(filename):
        return jsonify({"error": "No data available for this patient"}), 404

    timestamps = []
    sensor_values = []
    with open(filename, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            timestamps.append(datetime.strptime(row['Timestamp'], '%Y-%m-%d %H:%M:%S.%f'))
            sensor_values.append(int(row['Sensor Value']))

    if not timestamps or not sensor_values:
        return jsonify({"error": "No data available for this patient"}), 404

    plt.figure()
    plt.plot(timestamps, sensor_values, marker='o')
    plt.xlabel('Timestamp')
    plt.ylabel('Sensor Value')
    plt.title(f'Sensor Data for Patient {patient_id}')
    plt.grid(True)

    img = io.BytesIO()
    plt.savefig(img, format='jpg')
    img.seek(0)
    plt.close()  # Close the plot to free memory
    return send_file(img, mimetype='image/jpeg', as_attachment=True, download_name=f'{patient_id}_sensor_data_plot.jpg')

if __name__ == '__main__':
    app.run(debug=True)