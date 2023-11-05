import ee
import json
import numpy as np

def get_landsat_collection(dateIni, dateEnd, box, sensor=None, harmonization=False, other_mask=None, other_mask_parameter=None):
    """
    Get the best quality Landsat image collection.

    Args:
        dateIni (str): Start date in 'YYYY-MM-DD' format.
        dateEnd (str): End date in 'YYYY-MM-DD' format.
        box (ee.Geometry or ee.FeatureCollection): Area of interest.
        sensor (list, optional): List of Landsat sensors. Default is ['LC08', 'LE07', "LT05"].
        harmonization (bool, optional): Whether to harmonize TM (Landsat 5) and ETM+ (Landsat 7) to OLI (Landsat 8). Default is False.
        other_mask (ee.Image, optional): Custom image mask.
        other_mask_parameter (list, optional): List of pixel values to mask.

    Returns:
        ee.ImageCollection: The best quality Landsat image collection.
    """
    dateIni = ee.Date(dateIni)
    dateEnd = ee.Date(dateEnd)

    if sensor is None:
        sensor = ['LC08', 'LE07', "LT05"]

    # Landsat collections
    landsat8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
                .select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'ST_B10', 'QA_PIXEL'],
                        ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'ST_B10', 'QA_PIXEL'])
                .map(applyScaleFactors))

    if harmonization:
        landsat7 = (ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
                    .map(applyScaleFactors)
                    .map(harmonizationRoy_fromETMplus_OLI))
        landsat5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
                    .map(applyScaleFactors)
                    .map(harmonizationRoy_fromETM_OLI))
    else:
        landsat7 = (ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
                    .map(applyScaleFactors))
        landsat5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
                    .map(applyScaleFactors))

    landsat_dict = ee.Dictionary({
        'LC08': landsat8,
        'LE07': landsat7,
        'LT05': landsat5
    })

    # Get a list of image collections
    collection_list = get_from_dict(sensor, landsat_dict)

    # Merge image collections
    def merge_ic(ic, previous):
        merged = ee.ImageCollection(ic).merge(ee.ImageCollection(previous))
        return ee.ImageCollection(merged)

    landsat = (ee.ImageCollection(collection_list.iterate(merge_ic, collection_list.get(0)))
                        .filterBounds(box)  # boundary
                        .filterDate(dateIni, dateEnd)
                        .map(landsat578_cloud())
                        .map(ndvi(nir="SR_B4", red="SR_B3", bandname="ndvi"))
                        .map(ndwi(nir="SR_B4", swir="SR_B5", bandname="ndwi"))
                        .map(msavi(nir="SR_B4", red="SR_B3", G=2, H=8, L=1, bandname="msavi"))
                        .map(evi(nir="SR_B4", red="SR_B3", blue="SR_B1", G=2.5, C1=6, C2=7.5, L=1, bandname='evi'))
                        .map(nirv(nir="SR_B4", red="SR_B3", bandname="nirv"))
                        .select(["ndvi", "msavi", "evi", "nirv", "ndwi"]))  # masking out dilutedcloud, cloud, cirrus, and shadow

    if other_mask and other_mask_parameter:
        if not isinstance(other_mask, ee.Image):
            raise TypeError("other_mask expects ee.Image where pixel values 0 will return invalid")
        if not isinstance(other_mask_parameter, list):
            raise TypeError("other_mask_parameter expects a list of pixel values to mask")
        landsat = landsat.map(image_mask(other_mask, other_mask_parameter))

    return landsat

def make_composite(collection, startMonth, endMonth, box):
    """
    Create yearly composite images from a Landsat image collection.

    Args:
        collection: Landsat image collection.
        startMonth: Start month for the composite.
        endMonth: End month for the composite.
        box: Area of interest.

    Returns:
        ee.ImageCollection: Yearly composite images.
    """
    collection = ee.ImageCollection(collection)

    # Get range of years in the collection
    collection_sorted = collection.sort('system:time_start')
    range_date = collection_sorted.reduceColumns(ee.Reducer.minMax(), ['system:time_start'])
    startYear = int(ee.Date(range_date.get('min')).format('YYYY').getInfo())
    endYear = int(ee.Date(range_date.get('max')).format('YYYY').getInfo())
    stepList = ee.List(ee.List.sequence(startYear, endYear))

    meta_data = get_image_metadata(collection_sorted.first())

    def get_annual_median_composite(year):
        # Convert startMonth and endMonth to ee.Number outside the mapped function
        startMonth_ee = ee.Number(startMonth)
        endMonth_ee = ee.Number(endMonth)

        startDate = ee.Date.fromYMD(year, startMonth_ee, 1)
        endDate = ee.Date.fromYMD(year, endMonth_ee, 31)

        composite = (collection_sorted.filterBounds(box)
                      .filterDate(startDate, endDate))

        # Calculate the median composite
        composite_median = composite.median().clip(box).set('system:time_start', startDate)

        # Set the metadata properties for the individual image
        composite_median = composite_median.set('crs', meta_data.get('crs'))
        composite_median = composite_median.set('crs_transform', meta_data.get('crs_transform'))
        composite_median = composite_median.set('dimensions', meta_data.get('dimensions'))
        composite_median = composite_median.set('start_month', startMonth_ee)
        composite_median = composite_median.set('end_month', endMonth_ee)

        return composite_median

    # Use map() to create an ImageCollection from the stepList
    filterCollection = stepList.map(get_annual_median_composite)
    yearlyComposites = ee.ImageCollection(filterCollection)

    return yearlyComposites

def get_image_metadata(image):
    """
    Get metadata information for a Google Earth Engine image.

    Args:
        image: Google Earth Engine image.

    Returns:
        ee.Dictionary: Metadata information.
    """
    crs = image.projection().getInfo()['crs']
    crs_transform = image.projection().getInfo()['transform']
    dimensions = image.getInfo()['bands'][0]['dimensions']

    return ee.Dictionary({
        'crs': crs,
        'crs_transform': crs_transform,
        'dimensions': dimensions
    })

def convert_gee_image_to_geojson(gee_image):
    """
    Convert a Google Earth Engine image to GeoJSON format.

    Args:
        gee_image: Google Earth Engine image.

    Returns:
        str: GeoJSON data as a JSON string.
    """
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
  
def create_reduce_region_function(geometry, reducer=ee.Reducer.mean(), scale=1000, crs='EPSG:4326', bestEffort=True, maxPixels=1e13, tileScale=4):
    """
    Creates a region reduction function for ee.ImageCollection.map().

    Args:
        geometry: An ee.Geometry defining the region for reduction.
        reducer: An ee.Reducer defining the reduction method.
        scale: Nominal scale in meters of the projection to work in.
        crs: An ee.Projection or EPSG string that defines the projection.
        bestEffort: Boolean for using a larger scale if needed.
        maxPixels: Maximum number of pixels to reduce.
        tileScale: Scaling factor used to reduce aggregation tile size.

    Returns:
        A function for ee.ImageCollection.map() that reduces images by region.
    """

    def reduce_region_function(img):
        stat = img.reduceRegion(
            reducer=reducer,
            geometry=geometry,
            scale=scale,
            crs=crs,
            bestEffort=bestEffort,
            maxPixels=maxPixels,
            tileScale=tileScale
        )
        return ee.Feature(geometry, stat).set({'millis': img.date().millis()})
    
    return reduce_region_function

def reduce_regions_function(reduction_regions, reducerAll=True, scale=1000, crs='EPSG:4326', tileScale=1):
    """
    Creates a multiple regions reduction function for ee.ImageCollection.map().

    Args:
        reduction_regions: FeatureCollection defining the regions to reduce over.
        reducerAll: Use multiple reducers (mean, median, minMax, stdDev, intervalMean).
        scale: Nominal scale in meters of the projection to work in.
        crs: An ee.Projection or EPSG string that defines the projection.
        tileScale: Scaling factor used to reduce aggregation tile size.

    Returns:
        A function for ee.ImageCollection.map() that reduces images by region.
    """
    if reducerAll is True:
        reducerAll = (ee.Reducer.mean().combine(ee.Reducer.median(), '', True)
                      .combine(ee.Reducer.minMax(), '', True)
                      .combine(ee.Reducer.stdDev(), '', True)
                      .combine(ee.Reducer.intervalMean(10, 90).setOutputs(['int_mean_10_90']), '', True)
                      .combine(ee.Reducer.count(), '', True))
    else:
        reducerAll = (ee.Reducer.mean().combine(ee.Reducer.median(), '', True))

    def reduce_regions_function(image):
        fc = image.reduceRegions(
            collection=reduction_regions,
            reducer=reducerAll,
            scale=scale,
            crs=crs,
            tileScale=tileScale
        ).set({'millis': image.date().millis()})

        filtered = fc.filter(ee.Filter.notNull(fc.first().propertyNames()))

        return filtered

    return reduce_regions_function

def fc_to_dict(fc):
    """
    Convert a FeatureCollection to a dictionary.

    Args:
        fc: FeatureCollection to convert.

    Returns:
        A dictionary of feature properties.
    """
    prop_names = fc.first().propertyNames()
    prop_lists = fc.reduceColumns(
        reducer=ee.Reducer.toList().repeat(prop_names.size()),
        selectors=prop_names
    ).get('list')
    return ee.Dictionary.fromLists(prop_names, prop_lists)

# Add date-related information to a DataFrame.
def add_date_info(df):
    """
    Add date-related information to a pandas DataFrame.

    Args:
        df: DataFrame to add date information to.

    Returns:
        DataFrame with added date-related columns.
    """
    df['Timestamp'] = pd.to_datetime(df['millis'], unit='ms')
    df['Year'] = pd.DatetimeIndex(df['Timestamp']).year
    df['Month'] = pd.DatetimeIndex(df['Timestamp']).month
    df['Day'] = pd.DatetimeIndex(df['Timestamp']).day
    df['DOY'] = pd.DatetimeIndex(df['Timestamp']).dayofyear
    return df

def bitwiseExtract(img, fromBit, toBit, new_name):
    """
    Extract values from specific bits in an image.

    Args:
        img: Image or number to compute.
        fromBit: Start bit.
        toBit: End bit.
        new_name: Name for the new band.

    Returns:
        An image with extracted bit values.
    """
    fromBit = ee.Number(fromBit)
    toBit = ee.Number(toBit)
    new_name = ee.String(new_name)

    maskSize = ee.Number(1).add(toBit).subtract(fromBit)
    mask = ee.Number(1).leftShift(maskSize).subtract(1)

    return img.rename([new_name]).rightShift(fromBit).bitwiseAnd(mask)

def get_from_dict(a_list, a_dict):
    """
    Get a list of values from a dictionary based on keys.

    Args:
        a_list: List of keys.
        a_dict: Dictionary to get values from.

    Returns:
        A list of values corresponding to the keys in a_list.
    """
    a_list = ee.List(a_list) if isinstance(a_list, list) else a_list
    a_dict = ee.Dictionary(a_dict) if isinstance(a_dict, dict) else a_dict
    empty = ee.List([])

    def wrap(el, first):
        f = ee.List(first)
        cond = a_dict.contains(el)
        return ee.Algorithms.If(cond, f.add(a_dict.get(el)), f)

    values = ee.List(a_list.iterate(wrap, empty))
    return values

def applyScaleFactors(image):
    """
    Apply scaling factors to Landsat image bands.

    Args:
        image: Landsat image.

    Returns:
        Image with scaled bands.
    """
    opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2).toFloat()
    thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0).toFloat()
    return (image.addBands(opticalBands, overwrite=True)
            .addBands(thermalBands, overwrite=True))

def modis_scale_factor(img):
    bands = img.select('sur_ref1_b.').multiply(0.0001)
    return img.addBands(bands, overwrite=True)

def modis43A_scale_factor(img):
    bands = img.select('Nadir_Reflectance_Band.').multiply(0.0001)
    return img.addBands(bands, overwrite=True)

def harmonizationRoy_fromETM_OLI(img):
    """
    Harmonize TM (Landsat 5) to OLI (Landsat 8).

    Args:
        img: Landsat image.

    Returns:
        Image with harmonized bands.
    """
    slopes = ee.Image.constant([0.9785, 0.9542, 0.9825, 1.0073, 1.0171, 0.9949])
    constants = ee.Image.constant([-0.0095, -0.0016, -0.0022, -0.0021, -0.0030, 0.0029])
    y = img.select(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']).multiply(slopes).add(constants)
    return img.addBands(y, overwrite=True)

def harmonizationRoy_fromETMplus_OLI(img):
    """
    Harmonize ETM+ (Landsat 7) to OLI (Landsat 8).

    Args:
        img: Landsat image.

    Returns:
        Image with harmonized bands.
    """
    slopes = ee.Image.constant([0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071])
    constants = ee.Image.constant([0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172])
    y = img.select(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']).multiply(slopes).add(constants)
    return img.addBands(y, overwrite=True)
  
def image_mask(from_image, mask_parameter=None):
    """
    Create a mask from an ee.Image.

    Args:
        from_image: An ee.Image used as a reference for masking.
        mask_parameter: A list of pixel values to mask out.

    Returns:
        A function to apply with ee.ImageCollection.map() for masking.
    """

    if not isinstance(from_image, ee.Image):
        raise ValueError('from_image must be an ee.Image')

    if not mask_parameter:
        raise ValueError('mask_parameter must be a list of pixel values, e.g., [10, 20]')

    def apply_mask(image):
        mask_value_list = ee.List(mask_parameter)

        def compute(element):
            element = ee.Number(element)
            mask = from_image.neq(element)
            return ee.Image(mask)

        landcover_mask_list = ee.List(mask_value_list.map(compute))

        def compute2(img, previous):
            previous = ee.Image(previous)
            return previous.And(img)

        landcover_mask = ee.Image(landcover_mask_list.iterate(compute2, landcover_mask_list.get(0)))

        final = image.updateMask(landcover_mask).copyProperties(image, ['system:time_start'])
        return final

    return apply_mask

def apply_modis_lc_mask(mask_parameter=[11, 12, 13, 14, 15, 17], lc_type="LC_Type1"):
    """
    Create a function to mask based on MODIS yearly landcover data.

    Args:
        mask_parameter: A list of pixel values to mask out.
        lc_type: Landcover type.

    Returns:
        A function to apply with ee.ImageCollection.map() for masking based on MODIS data.
    """

    if not mask_parameter:
        raise ValueError('mask_parameter must be a list of pixel values, e.g., [10, 20]')

    def apply_mask(image):
        mask_value_list = ee.List(mask_parameter)
        year = ee.Date(image.date().format('YYYY'))

        if year.isEqual(ee.Date("2021-01-01")):
            year = ee.Date('2020-01-01')
        elif year.millis().lt(ee.Date('2001-01-01').millis()):
            year = ee.Date('2001-01-01')

        mask_image = (ee.ImageCollection('MODIS/006/MCD12Q1')
                      .filter(ee.Filter.date(year))
                      .select(lc_type)).first()

        def compute(element):
            element = ee.Number(element)
            mask = mask_image.neq(element)
            return ee.Image(mask)

        landcover_mask_list = ee.List(mask_value_list.map(compute))

        def compute2(img, previous):
            previous = ee.Image(previous)
            return previous.And(img)

        landcover_mask = ee.Image(landcover_mask_list.iterate(compute2, landcover_mask_list.get(0)))

        final = image.updateMask(landcover_mask).copyProperties(image, ['system:time_start'])
        return final

    return apply_mask

def landsat578_cloud(masks=['dilutedCloud', 'cirrus', 'cloud', 'shadow']):
    """
    Function to mask out clouds and shadow in Landsat 5, 7, 8 TOA C2.

    Args:
        masks: List of masks to compute.

    Returns:
        A function to apply with ee.ImageCollection.map() for cloud and shadow masking.
    """

    def apply_mask(image):
        options = ee.List(masks)
        qa = image.select('QA_PIXEL')

        dilutedCloud = bitwiseExtract(qa, 1, 1, 'dilutedCloud').eq(0)
        cirrus = bitwiseExtract(qa, 2, 2, 'cirrus').eq(0)
        cloud = bitwiseExtract(qa, 3, 3, 'cloud').eq(0)
        cloudShadow = bitwiseExtract(qa, 4, 4, 'cloudShadow').eq(0)

        cloud_dict = ee.Dictionary({
            'dilutedCloud': dilutedCloud,
            'cirrus': cirrus,
            'cloud': cloud,
            'cloudShadow': cloudShadow
        })

        masks_list = get_from_dict(options, cloud_dict)

        def compute(img, previous):
            previous = ee.Image(previous)
            return previous.And(img)

        mask_image = ee.Image(masks_list.iterate(compute, masks_list.get(0)))

        return image.updateMask(mask_image).copyProperties(image, ['system:time_start'])

    return apply_mask
  
def modis43A_cloud(masks=None):
    """
    Function to mask out clouds and shadow in MODIS 43A data.

    Args:
        masks: List of masks to compute.

    Returns:
        A function to apply with ee.ImageCollection.map() for MODIS 43A cloud and shadow masking.
    """

    if masks is None:
        masks = [
            'BRDF_Albedo_Band_Mandatory_Quality_Band1',
            'BRDF_Albedo_Band_Mandatory_Quality_Band2',
            'BRDF_Albedo_Band_Mandatory_Quality_Band3',
            'BRDF_Albedo_Band_Mandatory_Quality_Band4',
            'BRDF_Albedo_Band_Mandatory_Quality_Band5',
            'BRDF_Albedo_Band_Mandatory_Quality_Band6',
            'BRDF_Albedo_Band_Mandatory_Quality_Band7'
        ]

    def apply_mask(image):
        options = ee.List(masks)
        band_masks = []

        for mask_name in masks:
            band_mask = image.select(mask_name).eq(0)
            band_masks.append(band_mask)

        cloud_dict = ee.Dictionary(dict(zip(masks, band_masks)))

        masks_list = get_from_dict(options, cloud_dict)

        def compute(img, previous):
            previous = ee.Image(previous)
            return previous.And(img)

        mask_image = ee.Image(masks_list.iterate(compute, masks_list.get(0)))

        return image.updateMask(mask_image).copyProperties(image, ['system:time_start'])

    return apply_mask

def ndvi(nir, red, bandname='ndvi'):
    """
    Calculates the NDVI index: '(NIR-RED)/(NIR+RED)'

    Args:
        nir: Name of the Near Infrared (NIR) band.
        red: Name of the red (RED) band.
        bandname: Name of the NDVI band.

    Returns:
        A function to calculate NDVI for an image or collection.
    """

    def compute(image):
        ndvi = image.expression(
            '(NIR-RED)/(NIR+RED)', {
                'NIR': image.select(nir),
                'RED': image.select(red)}).rename(bandname)
        return image.addBands(ndvi)

    return compute

def evi(nir, red, blue, G=2.5, C1=6, C2=7.5, L=1, bandname='evi', scale_factor=0.0000275, offset=-0.2):
    """
    Calculates the EVI index: 'G*((NIR-RED)/(NIR+(C1*RED)-(C2*BLUE)+L))'

    Args:
        nir: Name of the Near Infrared (NIR) band.
        red: Name of the red (RED) band.
        blue: Name of the blue (BLUE) band.
        G: G coefficient for the EVI index.
        C1: C1 coefficient for the EVI index.
        C2: C2 coefficient for the EVI index.
        L: L coefficient for the EVI index.
        bandname: Name of the EVI band.
        scale_factor: Scale factor for EVI calculation.
        offset: Offset for EVI calculation.

    Returns:
        A function to calculate EVI for an image or collection.
    """

    L = float(L)
    G = float(G)
    C1 = float(C1)
    C2 = float(C2)

    def compute(image):
        evi = image.expression(
            'G*((NIR-RED)/(NIR+(C1*RED)-(C2*BLUE)+L))', {
                'NIR': image.select(nir),
                'RED': image.select(red),
                'BLUE': image.select(blue),
                'G': G,
                'C1': C1,
                'C2': C2,
                'L': L
            }).rename(bandname)

        return image.addBands(evi)

    return compute

def savi(nir, red, L=0.5, G=1.5, bandname='savi'):
    """
    Calculates the SAVI index: '((NIR - R) / (NIR + R + L)) * (1 + L)'

    Args:
        nir: Name of the Near Infrared (NIR) band.
        red: Name of the red (RED) band.
        L: L coefficient for the SAVI index.
        G: G coefficient for the SAVI index.
        bandname: Name of the SAVI band.

    Returns:
        A function to calculate SAVI for an image or collection.
    """

    L = float(L)
    G = float(G)

    def compute(image):
        savi = image.expression(
            "((NIR - RED) / (NIR + RED + L)) * G", {
                'NIR': image.select(nir),
                'RED': image.select(red),
                'L': L,
                'G': G
            }).rename(bandname)
        return image.addBands(savi)

    return compute

def msavi(nir, red, G=2, H=8, L=1, bandname='msavi'):
    """
    Calculates the MSAVI index: '(G * NIR + L - sqrt(pow((G * NIR + L), 2) - H*(NIR - RED)))/2'

    Args:
        nir: Name of the Near Infrared (NIR) band.
        red: Name of the red (RED) band.
        G: G coefficient for the MSAVI index.
        H: H coefficient for the MSAVI index.
        L: L coefficient for the MSAVI index.
        bandname: Name of the MSAVI band.

    Returns:
        A function to calculate MSAVI for an image or collection.
    """

    G = float(G)
    L = float(L)
    H = float(H)

    def compute(image):
        msavi = image.expression(
            '(G * NIR + L - sqrt(pow((G * NIR + L), 2) - H*(NIR - RED)))/2', {
                'NIR': image.select(nir),
                'RED': image.select(red),
                'L': L,
                'G': G,
                'H': H
            }).rename(bandname)
        return image.addBands(msavi)

    return compute

def nirv(nir, red, bandname='nirv'):
    """
    Calculates the NIRv index: 'NIRv': 'NIR * ((NIR - RED) / (NIR + RED)'

    Args:
        nir: Name of the Near Infrared (NIR) band.
        red: Name of the red (RED) band.
        bandname: Name of the NIRv band.

    Returns:
        A function to calculate NIRv for an image or collection.
    """

    def compute(image):
        nirv = image.expression(
            'NIR * ((NIR - RED) / (NIR + RED))', {
                'NIR': image.select(nir),
                'RED': image.select(red)
            }).rename(bandname)
        return image.addBands(nirv)

    return compute

def ndwi(nir, swir, bandname='ndwi'):
    """
    Calculates the NDWI index: '(NIR - SWIR) / (NIR + SWIR)'

    Args:
        nir: Name of the Near Infrared (NIR) band.
        swir: Name of the shortwave infrared (SWIR) band.
        bandname: Name of the NDWI band.

    Returns:
        A function to calculate NDWI for an image or collection.
    """

    def compute(image):
        ndwi = image.expression(
            '(NIR - SWIR) / (NIR + SWIR)', {
                'NIR': image.select(nir),
                'SWIR': image.select(swir)
            }).rename(bandname)
        return image.addBands(ndwi)

    return compute


        