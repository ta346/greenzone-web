from flask import Flask, request, jsonify
from flask_cors import CORS  # Import the CORS extension


import ee
import json
import numpy as np

from gee_script.utils import get_landsat_collection
from gee_script.utils import make_composite
from gee_script.utils import image_mask

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
    
    # Validate required fields
    if (
        selected_province is None
        or selected_soum is None
        or selected_vegetation_index is None
        or selected_year is None
        or grazing_only is None
    ):
        return jsonify({"error": "Missing required fields in the request."}), 400

    # Process the data using the anomaly_processing function or other backend logic
    gee_image = anomaly_processing(
        selected_province,
        selected_soum,
        selected_vegetation_index,
        selected_year,
        grazing_only,
    )

    # Convert the Google Earth Engine image to GeoJSON
    geojson_data = convert_gee_image_to_geojson(gee_image)

    # Return the processed data as a JSON response with correct Content-Type
    return jsonify(geojson_data), 200, {'Content-Type': 'application/json'}

def anomaly_processing(
        selected_province: str,
        selected_soum: str,
        selected_vegetation_index: str,
        selected_year: str,
        grazing_only: bool
):  
    selected_province = str(selected_province)
    selected_soum = str(selected_soum)
    selected_vegetation_index = str(selected_vegetation_index)
    selected_year = int(selected_year)
    
    # laod province soum features from GEE
    fc = ee.FeatureCollection('users/ta346/mng-bounds/soum_aimag')
    
    # subset province and soum given user inputs
    soum_aimag = fc.filter(ee.Filter.And(ee.Filter.eq("aimag_eng", selected_province), ee.Filter.eq("soum_eng", selected_soum)))
    geom = soum_aimag.geometry()

    
    # cloud free landsat collection
    landsat_collection = (get_landsat_collection(dateIni='2017-01-01', # initial date
                                                            dateEnd='2023-12-31', # end date
                                                            box=geom, # area of interest
                                                            sensor=["LC08", "LE07", "LT05"], # LC08, LE07, LT05, search for all available sensors
                                                            harmonization=True)) # ETM and ETM+ to OLI
    
    summer_composite = (make_composite(landsat_collection, 6, 8, geom))
    
    # Compute vegetation indices on cloud free landsat collection for only summer
    if selected_vegetation_index == 'NDVI':
        summer_composite = summer_composite.select('ndvi')
    elif selected_vegetation_index == 'EVI':
      summer_composite = summer_composite.select('evi')
    elif selected_vegetation_index == 'SAVI':
      summer_composite = summer_composite.select('msavi')
    
    if grazing_only:
        summer_pasture_mask = ee.Image("users/ta346/pasture_delineation/pas_raster_new")
        
        summer_composite = summer_composite.map(image_mask(summer_pasture_mask, [3]))
    

    # Define dates to filter given user input
    dateIni = ee.Date.fromYMD(selected_year, 1, 1)
    dateEnd = ee.Date.fromYMD(selected_year, 12, 31)
    
    # Anomaly year
    selected_image = summer_composite.filterDate(dateIni, dateEnd).first()
    
    # Take mean of entire summer composite
    yMean = summer_composite.mean()

    # Find the standard deviation
    stdImg = summer_composite.reduce(ee.Reducer.stdDev())
    
    # Find anomaly
    anomaly = selected_image.subtract(yMean).divide(stdImg).clip(geom)

    anomaly = anomaly.select([0], ['z_score'])
    anomaly = anomaly.copyProperties(selected_image)

    # print(anomaly.getInfo())

    return ee.Image(anomaly)

def convert_gee_image_to_geojson(gee_image):

    # Sample data (replace this with your actual Google Earth Engine Image data)
    # Get the latlon image
    latlon = ee.Image.pixelLonLat().addBands(gee_image)

    # Get the coordinates and pixel values using latlon image
    latlon_data = latlon.unmask().reduceRegion(
        reducer=ee.Reducer.toList(),
        geometry=gee_image.geometry(),
        maxPixels=1e13,
        scale=1000
    )

    # Extract the pixel values, latitudes, and longitudes from the latlon_data dictionary
    pixel_values = np.array(latlon_data.get('z_score').getInfo())
    lats = np.array(latlon_data.get('latitude').getInfo())
    lons = np.array(latlon_data.get('longitude').getInfo())

    # Get unique latitudes and longitudes
    # uniqueLats = np.unique(lats)
    # uniqueLons = np.unique(lons)

    # Create a list of features for GeoJSON
    features = []
    for i in range(len(pixel_values)):
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lons[i], lats[i]]
            },
            "properties": {
                "z_score": pixel_values[i]
            }
        }
        features.append(feature)

    # Create the GeoJSON data as a dictionary
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    # Convert GeoJSON data to JSON string
    geojson_json_str = json.dumps(geojson_data)
    
    return geojson_json_str

if __name__ == "__main__":
    app.run()