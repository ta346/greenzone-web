import ee
import numpy as np
import xarray as xr

from gee_script.landsat_functions import get_landsat_collection, make_composite
from gee_script.mask import image_mask

# def ee_image_to_xarray(ee_image):
#     """Converts a Google Earth Engine image to an xarray dataset.

#     Args:
#         ee_image (ee.Image): The Earth Engine image.

#     Returns:
#         xarray.Dataset: The xarray dataset containing the image data.
#     """
#     # Get the image data as a NumPy array
#     image_data = np.array(ee_image.getInfo())

#     # Get the spatial and temporal information from the image
#     spatial_info = ee_image.projection().getInfo()['transform']
#     spatial_res = [abs(spatial_info[0]), abs(spatial_info[1])]
#     spatial_extent = [
#         spatial_info[2], spatial_info[5] + spatial_res[1] * image_data.shape[0],
#         spatial_info[2] + spatial_res[0] * image_data.shape[1], spatial_info[5],
#     ]
#     temporal_info = ee_image.get('system:time_start').getInfo()
    
#     # Create the xarray dataset
#     dataset = xr.Dataset(
#         {
#             'anomaly': (['y', 'x'], image_data),
#         },
#         coords={
#             'x': np.arange(spatial_extent[0], spatial_extent[2], spatial_res[0]),
#             'y': np.arange(spatial_extent[1], spatial_extent[3], -spatial_res[1]),
#             'time': [np.datetime64(temporal_info, 'ms')],
#         },
#     )

#     return dataset



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
                                                            cloud_cover_perc = 20,
                                                            sensor=["LC08", "LE07", "LT05"], # LC08, LE07, LT05, search for all available sensors
                                                            harmonization=True)) # ETM and ETM+ to OLI
    
    # Compute vegetation indices on cloud free landsat collection for only summer
    if selected_vegetation_index == 'NDVI':
        summer_composite = (make_composite(landsat_collection, 6, 8, geom)).select('ndvi')
    elif selected_vegetation_index == 'EVI':
      summer_composite = (make_composite(landsat_collection, 6, 8, geom)).select('evi')
    elif selected_vegetation_index == 'SAVI':
      summer_composite = (make_composite(landsat_collection, 6, 8, geom)).select('msavi')
    
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
    Anomaly = selected_image.subtract(yMean).divide(stdImg).clip(geom)

    Anomaly = Anomaly.select([0], ['z_score'])
    Anomaly = Anomaly.copyProperties(selected_image)

    # convert anomaly reaster into xarray

    return ee.Image(Anomaly)

    # # convert anomaly raster into xarray
    # anomaly_xr = ee_image_to_xarray(Anomaly)

    # # Serialize the xarray dataset to JSON
    # anomaly_json = anomaly_xr.to_dict()

    # For demonstration, we are returning the data as a dictionary
    # return ee.Image(Anomaly)

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