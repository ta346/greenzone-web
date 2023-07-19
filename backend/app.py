from flask import Flask, request, jsonify
from flask_cors import CORS  # Import the CORS extension
from anomaly_processing import anomaly_processing
# Import necessary modules for backend processing
import ee

# Initialize the Earth Engine Python API
try:
    ee.Initialize()
except Exception as e:
    ee.Authenticate()
    ee.Initialize()

app = Flask(__name__)
CORS(app)  # Enable CORS for the entire app

@app.route('/api/fetch_anomaly_map_data', methods=['POST'])
def fetch_anomaly_map_data():
    data = request.get_json()
    selected_province = data.get('selectedProvince')
    selected_soum = data.get('selectedSoum')
    selected_vegetation_index = data.get('selectedVegetationIndex')
    selected_year = data.get('selectedYear')
    grazing_only = data.get('grazingOnly')

    # Process the data using the anomaly_processing function or other backend logic
    process_data = anomaly_processing(
        selected_province,
        selected_soum,
        selected_vegetation_index,
        selected_year,
        grazing_only,
    )

    print(process_data)
    # Return the processed data or any response data as a JSON response
    return jsonify(process_data)

if __name__ == "__main__":
    app.run()