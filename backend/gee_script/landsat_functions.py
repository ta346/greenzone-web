# coding=utf-8
""" Functions for landsat data acquisition """
from concurrent.futures.process import _MAX_WINDOWS_WORKERS
import errno
from logging.config import valid_ident
from multiprocessing import reduction
from multiprocessing.sharedctypes import Value
from xmlrpc.client import Boolean, boolean

import ee
from .utils import get_from_dict, applyScaleFactors, modis43A_scale_factor, harmonizationRoy_fromETM_OLI, harmonizationRoy_fromETMplus_OLI, get_image_metadata
from .mask import landsat578_cloud, modis43A_cloud, image_mask
from .indices import ndvi, ndwi, msavi, evi, nirv

#----------------------------------------------------------------------------------------------------------------------------------------
def get_landsat_collection(dateIni, 
                            dateEnd, 
                            box,
                            cloud_cover_perc = 30,
                            sensor = ['LC08', 'LE07', "LT05"], 
                            harmonization=False):
    
    '''Function collects all available landsat images respective to different sensors as ImageCollection
    
    Parameters
    
    ----------
            
    dateIni: EE date
    type: chr
    format: '1900-01-01'
    
    dateEnd: EE date
    type: chr
    format: '1900-01-01'
    
    box : Area of interest
    type: ee.Geometry or ee.FeatureCollection

    perc_cover: 
        (Optional) Percentage cloud cover (0-100) to filter. 
    type: int
    
    sensor: 
        (Optional) a list of landsat sensors
    type: list
    format: By defualt, ['LC08', 'LE07', "LT05"]

    harmonization: 
        (Optional) harmonize TM (landsat 5) and ETM+ (Landsat 7) to OLI (Landsat 8)
    type: boolean. False by default. If True, sensor must include 'LE07', "LT05". 

    other_mask: 
        (Optional) Image mask. Useful if there is need for landcover mask or other custom made masks. All values 0 in the other mask will be masked out in the result
    type: ee.Image
    
    other_mask_parameter: 
        (Optional) a list of pixel values to mask. These values will be masked out in the result. 
    type: list
    format: [10, 20, 40]
    
    -----------

    RETURN: the best quality landsat image collection 
    rtype: ee.ImageCollection
    
    '''
    dateIni = ee.Date(dateIni)
    dateEnd = ee.Date(dateEnd)
    # startDate = ee.Date.fromYMD(year,startMonth,1)
    # endDate = ee.Date.fromYMD(year,endMonth,31)
    sensor_list = ee.List(sensor)
    cloud_cover_perc = ee.Number(cloud_cover_perc)

    # landasat 8 collection and change band names to match with landsat 5 and 7
    landsat8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
                            .select(['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6','SR_B7', 'ST_B10','QA_PIXEL'],['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7', 'ST_B10', 'QA_PIXEL'])
                            .map(applyScaleFactors)) # apply scale factors (refer to Google Earth Engine Data Catalogue Document
    
    if harmonization is True: 

        landsat7 = (ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
                        .map(applyScaleFactors) # apply scale factors (refer to Google Earth Engine Data Catalogue Document
                        .map(harmonizationRoy_fromETMplus_OLI))
        
        landsat5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
                        .map(applyScaleFactors) # apply scale factors (refer to Google Earth Engine Data Catalogue Document
                        .map(harmonizationRoy_fromETM_OLI))
    else:
        landsat7 = (ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
                        .map(applyScaleFactors)) # apply scale factors (refer to Google Earth Engine Data Catalogue Document)
        landsat5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
                        .map(applyScaleFactors))

    landsat_dict = ee.Dictionary({
        'LC08' : landsat8,
        'LE07' : landsat7,
        'LT05' : landsat5
    })

    # get a list of image collection
    collection_list = get_from_dict(sensor_list, landsat_dict)

    # function to merge a list of image collection to image collection
    def merge_ic(ic, previous):
        merged = ee.ImageCollection(ic).merge(ee.ImageCollection(previous))
        return ee.ImageCollection(merged)

    landsat = (ee.ImageCollection(collection_list.iterate(merge_ic, collection_list.get(0)))
                        .filterBounds(box) # boundary
                        .filterDate(dateIni, dateEnd)
                        .filter(ee.Filter.gt("CLOUD_COVER", cloud_cover_perc)) # Percentage cloud cover (0-100)
                        .map(landsat578_cloud())
                        .map(ndvi(nir= "SR_B4", red = "SR_B3", bandname = "ndvi"))
                        .map(ndwi(nir = "SR_B4", swir = "SR_B5", bandname="ndwi"))
                        .map(msavi(nir = "SR_B4", red = "SR_B3", G = 2, H = 8, L = 1, bandname="msavi"))
                        .map(evi(nir = "SR_B4", red = "SR_B3", blue = "SR_B1", G = 2.5, C1 = 6, C2 = 7.5, L=1, bandname='evi'))
                        .map(nirv(nir = "SR_B4", red = "SR_B3", bandname="nirv"))
                        .select(["ndvi", "msavi", "evi", "nirv", "ndwi"])) # masking out dilutedcloud, cloud, cirrus, and shadow

    # landsat = landsat.map(lambda image: clip_aoi(image, box))

    return landsat

def make_composite(collection, startMonth, endMonth, box):
    collection = ee.ImageCollection(collection)
    # startMonth = ee.Number(startMonth)
    # endMonth = ee.Number(endMonth)

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



# ---------------------------------------------------------------------------------------------------------------------------
def get_modis46a_500_collection(dateIni, 
                                    dateEnd, 
                                    box, 
                                    quality_mask = False, 
                                    other_mask = None, 
                                    other_mask_parameter = None):
    
    '''Function collects modis43a4 500m images
    The MCD43A4 V6 Nadir Bidirectional Reflectance Distribution Function Adjusted Reflectance 
    (NBAR) product provides 500 meter reflectance data of the MODIS "land" bands 1-7. 
    These are adjusted using a bidirectional reflectance distribution function to model the values as if they were collected from a nadir view. The data are produced daily based on a 16-day retrieval period, with the image's date occurring on the 9th day. This product combines data from both the Terra and Aqua spacecrafts, choosing the best representative pixel from the 16-day period.
    
    more on: https://developers.google.com/earth-engine/datasets/catalog/MODIS_006_MCD43A4#description
    
    Parameters
    
    ----------
            
    dateIni: EE date
    type: chr
    format: '1900-01-01'
    
    dateEnd: EE date
    type: chr
    format: '1900-01-01'
    
    box : Area of interest
    type: ee.Geometry or ee.FeatureCollection

    quality_mask: 
        (Optional) use the quality assurance flags associated with each pixel to pick the best pixels (e.g., clouds will be masked out)
    type: boolean (optional). False by default.  

    other_mask: 
        (Optional) Image mask. Useful if there is need for landcover mask or other custom made masks. All values 0 in the other mask will be masked out in the result
    type: ee.Image
    
    other_mask_parameter: 
        (Optional) a list of pixel values to mask. These values will be masked out in the result. 
    type: list
    format: [10, 20, 40]
    
    -----------

    RETURN: the best quality modis43a4 image collection 
    rtype: ee.ImageCollection
    
    '''
        
    dateIni = ee.Date(dateIni)
    dateEnd = ee.Date(dateEnd)
    
    modis43A = (ee.ImageCollection('MODIS/006/MCD43A4')
                        .filterBounds(box)
                        .filterDate(dateIni, dateEnd)
                        .map(modis43A_scale_factor))

    if quality_mask is True:
        modis43A = modis43A.map(modis43A_cloud())

    if other_mask and other_mask_parameter:
        if not isinstance (other_mask, ee.Image):
            raise TypeError("other_mask expects ee.Image where pixel values 0 will return invalid")
        if not isinstance (other_mask_parameter, list):
            raise TypeError("other_mask_parameter expects python style list of pixel values to mask")
        if other_mask and not other_mask_parameter:
            raise ValueError("other_mask_parameter is expected")
        if not other_mask and other_mask_parameter:
            raise ValueError("other_mask is expected")

        modis43A = modis43A.map(image_mask(other_mask, other_mask_parameter))
    
    return modis43A

def get_era5_collection(dateIni, 
                        dateEnd, 
                        box, 
                        bandnames, 
                        other_mask = None, 
                        other_mask_parameter = None):
    
    '''Function collects modis43a4 500m images

    ERA5-Land is a reanalysis dataset providing a consistent view of the evolution of land variables over several decades 
    at an enhanced resolution compared to ERA5. ERA5-Land has been produced by replaying the land component of the ECMWF 
    ERA5 climate reanalysis. 

    More on: https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY#description
    
    Parameters
    
    ----------
            
    dateIni: EE date
    type: chr
    format: '1900-01-01'
    
    dateEnd: EE date
    type: chr
    format: '1900-01-01'
    
    box : Area of interest
    type: ee.Geometry or ee.FeatureCollection

    bandnames: 
        Band names to select from ERA5
    type: list 

    other_mask: 
        (Optional) Image mask. Useful if there is need for landcover mask or other custom made masks. All values 0 in the other mask will be masked out in the result
    type: ee.Image
    
    other_mask_parameter: 
        (Optional) a list of pixel values to mask. These values will be masked out in the result. 
    type: list
    format: [10, 20, 40]
    
    -----------

    RETURN: the best quality modis43a4 image collection 
    rtype: ee.ImageCollection
    
    '''
        
    dateIni = ee.Date(dateIni)
    dateEnd = ee.Date(dateEnd)
    bandnames = bandnames


    era5 = (ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
                .filterBounds(box)
                .filterDate(dateIni, dateEnd)
                .select(bandnames))

    if other_mask and other_mask_parameter:
        if not isinstance (other_mask, ee.Image):
            raise TypeError("other_mask expects ee.Image where pixel values 0 will return invalid")
        if not isinstance (other_mask_parameter, list):
            raise TypeError("other_mask_parameter expects python style list of pixel values to mask")
        if other_mask and not other_mask_parameter:
            raise ValueError("other_mask_parameter is expected")
        if not other_mask and other_mask_parameter:
            raise ValueError("other_mask is expected")

        era5 = era5.map(image_mask(other_mask, other_mask_parameter))
    
    return era5