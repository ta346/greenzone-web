# coding=utf-8
""" Functions for landsat data acquisition """
from concurrent.futures.process import _MAX_WINDOWS_WORKERS
import errno
from logging.config import valid_ident
from multiprocessing import reduction
from multiprocessing.sharedctypes import Value
from xmlrpc.client import Boolean, boolean

import ee
import mask
import indices
import utils
import math

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
                            .map(utils.applyScaleFactors)) # apply scale factors (refer to Google Earth Engine Data Catalogue Document
    
    if harmonization is True: 

        landsat7 = (ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
                        .map(utils.applyScaleFactors) # apply scale factors (refer to Google Earth Engine Data Catalogue Document
                        .map(utils.harmonizationRoy_fromETMplus_OLI))
        
        landsat5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
                        .map(utils.applyScaleFactors) # apply scale factors (refer to Google Earth Engine Data Catalogue Document
                        .map(utils.harmonizationRoy_fromETM_OLI))
    else:
        landsat7 = (ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
                        .map(utils.applyScaleFactors)) # apply scale factors (refer to Google Earth Engine Data Catalogue Document)
        landsat5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
                        .map(utils.applyScaleFactors))

    landsat_dict = ee.Dictionary({
        'LC08' : landsat8,
        'LE07' : landsat7,
        'LT05' : landsat5
    })

    # get a list of image collection
    collection_list = utils.get_from_dict(sensor_list, landsat_dict)

    # function to merge a list of image collection to image collection
    def merge_ic(ic, previous):
        merged = ee.ImageCollection(ic).merge(ee.ImageCollection(previous))
        return ee.ImageCollection(merged)

    landsat = (ee.ImageCollection(collection_list.iterate(merge_ic, collection_list.get(0)))
                        .filterBounds(box) # boundary
                        .filterDate(dateIni, dateEnd)
                        .filter(ee.Filter.gt("CLOUD_COVER", cloud_cover_perc)) # Percentage cloud cover (0-100)
                        .map(mask.landsat578_cloud())
                        .map(indices.ndvi(nir= "SR_B4", red = "SR_B3", bandname = "ndvi"))
                        .map(indices.ndwi(nir = "SR_B4", swir = "SR_B5", bandname="ndwi"))
                        .map(indices.msavi(nir = "SR_B4", red = "SR_B3", G = 2, H = 8, L = 1, bandname="msavi"))
                        .map(indices.evi(nir = "SR_B4", red = "SR_B3", blue = "SR_B1", G = 2.5, C1 = 6, C2 = 7.5, L=1, bandname='evi'))
                        .map(indices.nirv(nir = "SR_B4", red = "SR_B3", bandname="nirv"))
                        .select(["ndvi", "msavi", "evi", "nirv", "ndwi"])) # masking out dilutedcloud, cloud, cirrus, and shadow

    return landsat

def make_composite(collection, startMonth, endMonth, box):
    # function takes startYear, endYear, landcover mask (1985-1999: maskLC2000, 2000-2009: maskLC2010, 2010-2020: maskLC2020), shp = bag or soum, file name: str, folder_name: str (google drive folder to download to)
    collection = ee.ImageCollection(collection)
    startMonth = ee.Number(startMonth)
    endMonth = ee.Number(endMonth)

    # get range of years in the collection
    collection_sorted = collection.sort('system:time_start')
    range_date = collection_sorted.reduceColumns(ee.Reducer.minMax(), ['system:time_start'])
    startYear = int(ee.Date(range_date.get('min')).format('YYYY').getInfo())
    endYear = int(ee.Date(range_date.get('max')).format('YYYY').getInfo())
    stepList = ee.List.sequence(startYear, endYear)
    
    def get_annual_median_composite(year):

        startDate = ee.Date.fromYMD(year,startMonth,1)
        endDate = ee.Date.fromYMD(year,endMonth,31)
        
        composite = (collection_sorted.filterBounds(box)
                            .filterDate(startDate, endDate))
        
        composite_i = composite.median().clip(box).set('system:time_start', startDate)
        
        return composite_i
    
    filterCollection = stepList.map(get_annual_median_composite)

    yearlyComposites = ee.ImageCollection.fromImages(filterCollection) #return single image for each year
    
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
                        .map(utils.modis43A_scale_factor))

    if quality_mask is True:
        modis43A = modis43A.map(mask.modis43A_cloud())

    if other_mask and other_mask_parameter:
        if not isinstance (other_mask, ee.Image):
            raise TypeError("other_mask expects ee.Image where pixel values 0 will return invalid")
        if not isinstance (other_mask_parameter, list):
            raise TypeError("other_mask_parameter expects python style list of pixel values to mask")
        if other_mask and not other_mask_parameter:
            raise ValueError("other_mask_parameter is expected")
        if not other_mask and other_mask_parameter:
            raise ValueError("other_mask is expected")

        modis43A = modis43A.map(mask.image_mask(other_mask, other_mask_parameter))
    
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

        era5 = era5.map(mask.image_mask(other_mask, other_mask_parameter))
    
    return era5

def download_img_col_stats_to_csv_yearly(collection, 
                            bandnames, 
                            box,  
                            feat_id = None, 
                            scale = 500, 
                            crs = 'EPSG:4326',
                            tileScale = 1,
                            masks = None, 
                            masks_parameter = None,
                            file_name = "stats_", 
                            folder_name = "GEE_OUTPUT"):

    """ Function downloads common stats for each image in image collection to csv in google drive by each year
    stats: mean, median, minMAx, stdDev, IntervalMean(10, 90), count

    Parameters
    -----------------------------------------------------------------------------------
    
    collection: Image collection to download features
    type: ee.ImageCollection

    bandnames: band names to reduce
    type: list

    box :  shapefile or boundary features to export. Unique code for features can be given in feat_name argument 
    type:  ee.FeatureCollections or ee.Geometry 

    reducerAll: if True, reduce selected bands to mean, median, stdDev, minMax, and intervalMean(10,90)
                if False, reduce to only mean and median
    type: Bool 

    feat_name = specify region which will be use to reduce over
    type: str

    scale:
        Optional; A number that defines the nominal scale in meters of the projection to work in.
    type: nominal

    crs:
      (Optional) An ee.Projection or EPSG string ('EPSG:5070') that defines
      the projection to work in.
    
    tileScale:
      (Optional) A number representing the scaling factor used to reduce
      aggregation tile size; using a larger tileScale (e.g. 2 or 4) may enable
      computations that run out of memory with the default.
    
    other_mask: 
        (Optional) Image mask. Useful if there is need for landcover mask or other custom made masks. All values 0 in the other mask will be masked out in the result
    type: ee.Image
    
    other_mask_parameter: 
        (Optional) a list of pixel values to mask. These values will be masked out in the result.

    file_name: 
        (Optional) file name for export files. A respective year will be attached to the end automatically
        By default, stats_year
    type: str
    
    folder_name: 
        (Optional) name for Google drive folder to store exported files
        By default, GEE_OUTPUT
    type: str

    --------------------------------------------------------------------

    RETURN: ee.Task to downlaod landsat collection per year to google drive folder 
    rtype: task.start()
    
    """
    collection = collection
    bandnames = bandnames
    box = box
    feat_name = feat_id
    scale = scale
    tileScale = tileScale
    file_name = file_name
    folder_name = folder_name
    other_mask = masks
    other_mask_parameter = masks_parameter


    if not isinstance(collection, ee.ImageCollection):
        raise TypeError("collection: ee.ImageCollection is expected")
    if not isinstance(bandnames, list):
        raise TypeError("bandnames: a list of band names is expected")
    if not isinstance(box, ee.FeatureCollection):
        raise TypeError("box: ee.FeatureCollection or ee.Geometry is expected")
    if not isinstance(feat_name, str):
        raise TypeError("feat_name: string is expected")
    if other_mask and other_mask_parameter:
        if not isinstance (other_mask, ee.Image):
            raise TypeError("other_mask expects ee.Image where pixel values 0 will return invalid")
        if not isinstance (other_mask_parameter, list):
            raise TypeError("other_mask_parameter expects python style list of pixel values to mask")
    if other_mask and not other_mask_parameter:
        raise ValueError("other_mask_parameter is expected")
    if not other_mask and other_mask_parameter:
        raise ValueError("other_mask is expected")
    
    if feat_name is None:
        reduction_boundary = box
    else:
        reduction_boundary = box.select(feat_name)
    
    # get range of years in the collection
    collection = ee.ImageCollection(collection).sort('system:time_start')
    range_date = collection.reduceColumns(ee.Reducer.minMax(), ['system:time_start'])
    start = int(ee.Date(range_date.get('min')).format('YYYY').getInfo())
    end = int(ee.Date(range_date.get('max')).format('YYYY').getInfo())

    # loop through each year and reduce to regions and donwload to csv
    for loopYear in range(start, end+1, 1):
        
        dateIni = ee.Date.fromYMD(loopYear, 1, 1)
        dateEnd = dateIni.advance(1, 'year')
        # dateEnd = ee.Date.fromYMD(loopYear, endMonth, 31)
        
        #filter by each year, and select bandnames
        fc_collection = (collection.filter(ee.Filter.date(dateIni, dateEnd))
                                .select(bandnames)
                                .map(mask.image_mask(other_mask, other_mask_parameter))
                                .map(utils.reduce_regions_function(reduction_boundary, scale = 30, crs = crs))
                                .flatten()) # select bands to export
        
        #drop unnecessary geometry information
        out = fc_collection.select(['.*'], None, False) #FeatureCollection

        #give name to final output file
        filename = file_name + "_" + str(loopYear)
        
        # give name to GoogleDrive folder
        folder = folder_name      

        # Create task to download resulting feature of collection as csv and save in Google Drive
        task = ee.batch.Export.table.toDrive(collection = out,
                                    description= filename,
                                    folder = folder,
                                    fileFormat = 'CSV')
        #run task
        task.start()


def download_img_col_to_csv_monthly(collection, 
                                        startYear, 
                                        endYear, 
                                        startMonth, 
                                        endMonth, 
                                        bandnames, 
                                        box, 
                                        reducerAll, 
                                        feat_name = None, 
                                        scale = 9000, 
                                        crs = 'EPSG:4326',
                                        tileScale = 1,
                                        other_mask = None, 
                                        other_mask_parameter = None,
                                        file_name = "stats_", 
                                        folder_name = "GEE_OUTPUT"):

    """ Function downloads common stats for each image in image collection to csv in google drive by each month
    stats: mean, median, minMAx, stdDev, IntervalMean(10, 90), count

    Parameters
    -----------------------------------------------------------------------------------
    
    collection: Image collection to download features
    type: ee.ImageCollection

    startYear: start year
    type: int

    endYear: end year
    type: int

    startMonth: start month
    type: int

    endMonth: end month
    type: int

    bandnames: band names to reduce
    type: list

    box :  shapefile or boundary features to export. Unique code for features can be given in feat_name argument 
    type:  ee.FeatureCollections or ee.Geometry 

    reducerAll: if True, reduce selected bands to mean, median, stdDev, minMax, and intervalMean(10,90)
                if False, reduce to only mean and median
    type: Bool 

    feat_name = specify region which will be use to reduce over
    type: str

    scale:
        Optional; A number that defines the nominal scale in meters of the projection to work in.
    type: nominal

    other_mask: 
        (Optional) Image mask. Useful if there is need for landcover mask or other custom made masks. All values 0 in the other mask will be masked out in the result
    type: ee.Image
    
    other_mask_parameter: 
        (Optional) a list of pixel values to mask. These values will be masked out in the result.

    crs:
      (Optional) An ee.Projection or EPSG string ('EPSG:5070') that defines
      the projection to work in.
    
    tileScale:
      (Optional) A number representing the scaling factor used to reduce
      aggregation tile size; using a larger tileScale (e.g. 2 or 4) may enable
      computations that run out of memory with the default.

    file_name: 
        (Optional) file name for export files. A respective year will be attached to the end automatically
        By default, stats_year
    type: str
    
    folder_name: 
        (Optional) name for Google drive folder to store exported files
        By default, GEE_OUTPUT
    type: str

    --------------------------------------------------------------------

    RETURN: ee.Task to downlaod landsat collection per year to google drive folder 
    rtype: task.start()
    
    """
    collection = collection
    startYear = startYear
    endYear = endYear
    startMonth = startMonth
    endMonth = endMonth
    bandnames = bandnames
    box = box
    feat_name = feat_name
    scale = scale
    tileScale = tileScale
    other_mask = other_mask, 
    other_mask_parameter = other_mask_parameter
    file_name = file_name
    folder_name = folder_name
    reducerAll = reducerAll


    if not isinstance(collection, ee.ImageCollection):
        raise TypeError("collection: ee.ImageCollection is expected")
    if not isinstance(bandnames, list):
        raise TypeError("bandnames: a list is expected")
    if not isinstance(box, ee.FeatureCollection):
        raise TypeError("box: ee.FeatureCollection or ee.Geometry is expected")
    if not isinstance(reducerAll, bool):
        raise TypeError("reducerAll: string is expected")
    if not isinstance(feat_name, str):
        raise TypeError("feat_name: string is expected")


    
    if feat_name is None:
        reduction_boundary = box
    else:
        reduction_boundary = box.select(feat_name)

    if bool(reducerAll):
        reducerAll = True
    else:
        reducerAll = False
    
    for loopyear in range(startYear, endYear+1, 1):
        for month in range(startMonth, endMonth+1, 1):
            
            dateIni = ee.Date.fromYMD(loopyear, month, 1)
            dateEnd = dateIni.advance(1, 'month')

            # filterMonth = ee.Filter.calendarRange(month,month,'month')
#             dateIni = ee.Date.fromYMD(loopyear, month, 30)
#             dateEnd = ee.Date.fromYMD(loopyear, month, endDay)
            
            #filter by each year, and select bandnames
            df = (collection.filter(ee.Filter.date(dateIni, dateEnd))
                                    .select(bandnames)) # select bands to export
                
            if other_mask and other_mask_parameter:
                if other_mask and not other_mask_parameter:
                    raise ValueError("other_mask_parameter is expected")
                if not other_mask and other_mask_parameter:
                    raise ValueError("other_mask is expected")
                other_mask = ee.Image(other_mask)
                df = df.map(mask.image_mask(other_mask, other_mask_parameter))

            output = df.map(utils.reduce_regions_function(reduction_boundary, 
                                                                    reducerAll = reducerAll,
                                                                    scale = scale, 
                                                                    crs = crs, 
                                                                    tileScale=tileScale)).flatten()
            #drop unnecessary geometry information
            out = output.select(['.*'], None, False) #FeatureCollection

            #give name to final output file
            filename = file_name + "_" + str(loopyear) + "_" + str(month)
            
            # give name to GoogleDrive folder
            folder = folder_name      

            # Create task to download resulting feature of collection as csv and save in Google Drive
            task = ee.batch.Export.table.toDrive(collection = out,
                                        description= filename,
                                        folder = folder,
                                        fileFormat = 'CSV')
            #run task
            task.start()

# Deprecated functions ----------------------------------------------------------------------------

def landsat_to_csv(startYear, 
                    endYear, 
                    box, 
                    file_name, 
                    folder_name, 
                    feat_name = None, 
                    cloud_percentage = 50, 
                    other_mask = None, 
                    other_mask_parameter = None):
    

    '''Function reduce landsat ImageCollection to the features of region and export as CSV file per year to Google drive folder
    Note: this function doesn't aggregate or mosaic image collections. Only available images. 
    
    Parameters
    ------------------------------------------------------------------
            
    startYear: start year
    type: int
    format: 1984
    
    endYear: end year 
    type: int
    format: 2021
    
    box :  shapefile or boundary features to export. Unique code for features can be given in feat_name argument 
    type:  ee.FeatureCollections or ee.Geometry 

    file_name: name for export. A respective year will be attached to the end automatically
    type: chr
    
    folder_name: Google drive foler name to store exports
    type: chr

    feat_name: unique name for features. By default, none. 
    type: chr

    cloud_percentage: Percentage cloud cover (0-100). By default, greater than 50
    type: int

    other_mask: image mask i.e., landcover or other custom made. All values 0 in the other mask will be masked out in the result
    type: ee.Image
    
    other_mask_parameter: a list of pixel values to mask. These values will be masked out in the result. 
    type: list
    format: [10, 20, 40]

    --------------------------------------------------------------------

    RETURN: ee.Task to downlaod landsat collection per year to google drive folder 
    rtype: task.start()
    
    '''
    
    startYear = startYear
    endYear = endYear
    box = box

    if not isinstance (other_mask, ee.Image):
        raise ValueError("other_mask expects ee.Image where pixel values 0 will return invalid")
    if not isinstance (other_mask_parameter, list):
        raise ValueError("other_mask_parameter expects python style list of pixel values to mask from other_mask")
    if other_mask and not other_mask_parameter:
        raise ValueError("other_mask_parameter is expected")
    if not other_mask and other_mask_parameter:
        raise ValueError("other_mask is expected")
    if startYear < 1984:
        raise ValueError("startYear is out of range")
    
    other_mask = ee.Image(other_mask)

    for loopYear in range(startYear, endYear + 1, 1):
        
        # take the dates in range
        # filterYear = ee.Filter.calendarRange(loopYear, loopYear, 'year')
        # filterMonth = ee.Filter.calendarRange(startMonth, endMonth, 'month')
        dateIni = ee.Date.fromYMD(loopYear, 1, 1)
        dateEnd = dateIni.advance(1, 'year')
        # dateEnd = ee.Date.fromYMD(loopYear, endMonth, 31)
        
        landsat_collection = get_landsat_collection(dateIni, dateEnd, box, cloud_percentage, harmonization=True)

        if other_mask and other_mask_parameter:
            landsat_collection = landsat_collection.map(mask.image_mask(other_mask, other_mask_parameter))
        
        # apply indices functions and select only those bands
        landsat_collection = (landsat_collection.map(indices.ndvi(nir= "SR_B4", red = "SR_B3", bandname = "ndvi"))
                                   .map(indices.evi(nir = "SR_B4", red = "SR_B3", blue = "SR_B1", bandname='evi'))
                                   .map(indices.savi(nir = "SR_B4", red = "SR_B3", G = 1.5, L = 5000, bandname="savi"))
                                   .map(indices.msavi(nir = "SR_B4", red = "SR_B3", G = 2, H = 8, L = 10000, bandname="msavi"))
                                   .map(indices.nirv(nir = "SR_B4", red = "SR_B3", bandname="nirv"))
                                   .map(indices.ndwi(nir = "SR_B4", swir = "SR_B5", bandname="ndwi"))
                                   .select('ndvi', 'evi', 'savi', 'msavi', 'nirv', 'ndwi'))

        # function to reduce by the area of interest
        # this function loops over each image collected in landsat_collections, 
        # and apply reduce statistics for every feature in area of interest. 
        # More about reducer: https://developers.google.com/earth-engine/guides/reducers_intro
        # i.e., take mean pixels from all the pixels within each soum or bag's polygon. 
        
        # statistics to reduce: mean, median, minMax, stdDev, 10 and 90 mean interval, and count of pixels per polygon
        reducer2 = ee.Reducer.mean() \
            .combine(ee.Reducer.median(), '', True) \
            .combine(ee.Reducer.minMax(), '', True) \
            .combine(ee.Reducer.stdDev(), '', True) \
            .combine(ee.Reducer.intervalMean(10, 90).setOutputs(['int_mean_10_90']), '', True) \
            .combine(ee.Reducer.count(),'', True)

        # function to reduce by polygon
        def reduce_regions_function(image):
            return image.reduceRegions(
                collection=box.select(feat_name),
                reducer=reducer2,
                scale=30
                ).filter(ee.Filter.neq('ndvi_mean', None)) \
                    .filter(ee.Filter.neq('msavi_mean', None)) \
                        .filter(ee.Filter.neq('nirv_mean', None)) \
                            .filter(ee.Filter.neq('ndwi_mean', None)) \
                                .filter(ee.Filter.neq('evi_mean', None)) \
                                    .filter(ee.Filter.neq('savi_mean', None))  #when reducing image, the first image has to have a value. Otherwise, the function will return empty cells. 


        #apply the reduce function and flatten to export in CSV format
        output = landsat_collection.map(reduce_regions_function).flatten()

        #drop unnecessary geometry information
        out = output.select(['.*'], None, False) #FeatureCollection

        #give name to final output file
        filename = file_name + str(loopYear)
        
        # give name to GoogleDrive folder
        folder = folder_name      

        # Create task to download resulting feature of collection as csv and save in Google Drive
        task = ee.batch.Export.table.toDrive(collection = out,
                                    description= filename,
                                    folder = folder,
                                    fileFormat = 'CSV')
        #run task
        task.start()