# coding=utf-8
""" Functions for masks """
from concurrent.futures.process import _MAX_WINDOWS_WORKERS
import ee
import utils

#----------------------------------------------------------------------------------------------------------------------------------------

def image_mask(from_image, mask_parameter = None):

    """
    create mask from ee.Image
    USE CASE
    .. code:: python
        # use in a collection
        col = ee.ImageCollection(ID)
        masked = col.map(mask.mask_from_image("B4", "B3"))
        # use in a single image
        img = ee.Image(ID)
        masked = img.mask.mask_from_image()
    
    
    RETURN: The function to apply a map() over a collection
    :rtype: function
    """

    if not isinstance(from_image, ee.Image): 
        raise ValueError('from_iamge has to be ee.Image')

    if not mask_parameter: 
        raise ValueError('mask_parameter has to be list of pixel values e.g., [10, 20]')

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

def apply_modis_lc_mask(mask_parameter = [11, 12, 13, 14, 15, 17], lc_type = "LC_Type1"):

    """
    Create Function to use it for Map(). Function creates mask from MODIS yearly landcover (2001-2020)
    and applies to each image in image collection with respect to image-year. If image year is before 2001, the landcover
    map for 2001 is be used. Similarly, if image year is after 2020, the 2020 landcover map is used.  

    More: https://developers.google.com/earth-engine/datasets/catalog/MODIS_006_MCD12Q1?hl=en#description

    The MCD12Q1 V6 product provides global land cover types at yearly intervals (2001-2016) derived 
    from six different classification schemes. It is derived using supervised classifications of 
    MODIS Terra and Aqua reflectance data. The supervised classifications then undergo additional 
    post-processing that incorporate prior knowledge and ancillary information to further refine specific classes.

    USE CASE
    .. code:: python
        # use in a collection
        col = ee.ImageCollection(ID)
        masked = col.map(mask.apply_modis_lc_mask())
        # use in a single image
        img = ee.Image(ID)
        masked = img.mask.apply_modis_lc_mask()
    
    
    Parameters:
    -----------------------------------------------------------------------

    mask_parameter: 
        (Optional) a list of pixel values to mask out.
    type: list

    lc_type:
        (Optional) a landcover type
    type: str


    RETURN: The function to apply a map() over a collection
    :rtype: function
    """

    # if not isinstance(from_image, ee.Image): 
    #     raise ValueError('from_iamge has to be ee.Image')

    if not mask_parameter: 
        raise ValueError('mask_parameter has to be list of pixel values e.g., [10, 20]')

    def apply_mask(image):
        
        mask_value_list = ee.List(mask_parameter)

        year = ee.Date(image.date().format('YYYY'))

        if year is ee.Date("2021-01-01"):
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

def landsat578_cloud(masks = ['dilutedCloud', 'cirrus', 'cloud', 'shadow']):

    """ Function to mask out clouds and shadow in Landsat 5, 7 ,8 TOA C2:
    'LANDSAT/LC08/C02/T1_L2', 'LANDSAT/LE07/C02/T1_L2', 'LANDSAT/LT05/C02/T1_L2'

    param masks: list of mask to compute
    type masks: list
    RETURN: The function to apply a map() over a collection
    rtype: function
    
    """

    def apply_mask(image): 

        options = ee.List(masks)
        
        qa = image.select('QA_PIXEL')

        dilutedCloud = utils.bitwiseExtract(qa, 1, 1, 'dilutedCloud').eq(0) # dilated Cloud
        cirrus = utils.bitwiseExtract(qa, 2, 2, 'cirrus').eq(0) # Cirrus
        cloud = utils.bitwiseExtract(qa, 3, 3, 'cloud').eq(0) # cloud
        cloudShadow = utils.bitwiseExtract(qa, 4, 4, 'cloudShadow').eq(0) # cloud shadow

        # Bits 1 is diluted cloud; 3 cloud, and 5 cloud shadow
        # dilutedCloud = (1 << 1)
        # cirrus = (1 << 2)
        # cloud = (1 << 3)
        # cloudShadow = (1 << 4)

        # # Flags should be set to zero, indicating clear conditions.
        # bad_pixel = (qa.bitwiseAnd(dilutedCloud).eq(0)
        #                     .Or(qa.bitwiseAnd(cirrus).eq(0)) 
        #                     .Or(qa.bitwiseAnd(cloud).eq(0)) 
        #                     .Or(qa.bitwiseAnd(cloudShadow).eq(0)))

        # mask_image = bad_pixel.Not()

        cloud_dict = ee.Dictionary({
            'dilutedCloud' : dilutedCloud,
            'cirrus' : cirrus,
            'cloud' : cloud,
            'cloudShadow' : cloudShadow
        })
        
        masks_list = utils.get_from_dict(options, cloud_dict)

        def compute(img, previous):
            previous = ee.Image(previous)
            return previous.And(img)

        # all pixel with values 0 becomes invalid
        mask_image = ee.Image(masks_list.iterate(compute, masks_list.get(0))) 

        return image.updateMask(mask_image).copyProperties(image, ['system:time_start'])
    
    return apply_mask

def modis43A_cloud(masks = [
        'BRDF_Albedo_Band_Mandatory_Quality_Band1',
        'BRDF_Albedo_Band_Mandatory_Quality_Band2',
        'BRDF_Albedo_Band_Mandatory_Quality_Band3',
        'BRDF_Albedo_Band_Mandatory_Quality_Band4',
        'BRDF_Albedo_Band_Mandatory_Quality_Band5',
        'BRDF_Albedo_Band_Mandatory_Quality_Band6',
        'BRDF_Albedo_Band_Mandatory_Quality_Band7'
    ]):

    """ Function to mask out clouds and shadow in Landsat 5, 7 ,8 TOA C2:
    'LANDSAT/LC08/C02/T1_L2', 'LANDSAT/LE07/C02/T1_L2', 'LANDSAT/LT05/C02/T1_L2'

    param masks: list of mask to compute
    type masks: list
    RETURN: The function to apply a map() over a collection
    rtype: function
    
    """
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
        
        band1 = image.select('BRDF_Albedo_Band_Mandatory_Quality_Band1').eq(0)
        band2 = image.select('BRDF_Albedo_Band_Mandatory_Quality_Band2').eq(0)
        band3 = image.select('BRDF_Albedo_Band_Mandatory_Quality_Band3').eq(0)
        band4 = image.select('BRDF_Albedo_Band_Mandatory_Quality_Band4').eq(0)
        band5 = image.select('BRDF_Albedo_Band_Mandatory_Quality_Band5').eq(0)
        band6 = image.select('BRDF_Albedo_Band_Mandatory_Quality_Band6').eq(0)
        band7 = image.select('BRDF_Albedo_Band_Mandatory_Quality_Band7').eq(0)

        cloud_dict = ee.Dictionary({
            'BRDF_Albedo_Band_Mandatory_Quality_Band1': band1,
            'BRDF_Albedo_Band_Mandatory_Quality_Band2': band2,
            'BRDF_Albedo_Band_Mandatory_Quality_Band3': band3,
            'BRDF_Albedo_Band_Mandatory_Quality_Band4': band4,
            'BRDF_Albedo_Band_Mandatory_Quality_Band5': band5,
            'BRDF_Albedo_Band_Mandatory_Quality_Band6': band6,
            'BRDF_Albedo_Band_Mandatory_Quality_Band7': band7
        })
        
        masks_list = utils.get_from_dict(options, cloud_dict)

        def compute(img, previous):
            previous = ee.Image(previous)
            return previous.And(img)

        # all pixel with values 0 becomes invalid
        mask_image = ee.Image(masks_list.iterate(compute, masks_list.get(0))) 

        return image.updateMask(mask_image).copyProperties(image, ['system:time_start'])
    
    return apply_mask


def sentinel_cloud_mask(masks = ['cloud', 'cirrus']):

    """ Function to mask out clouds and cirrus in Harmonized Sentinel-2:
    'COPERNICUS/S2_SR_HARMONIZED'

    param masks: list of mask to compute
    type masks: list
    RETURN: The function to apply a map() over a collection
    rtype: function
    
    """

    def apply_mask(image): 

        options = ee.List(masks)
        
        qa = image.select('QA60')

        cloud = utils.bitwiseExtract(qa, 10, 10, 'cloud').eq(0) # cloud
        cirrus = utils.bitwiseExtract(qa, 11, 11, 'cirrus').eq(0) # Cirrus

        cloud_dict = ee.Dictionary({
            'cloud' : cloud,
            'cirrus' : cirrus
        })
        
        masks_list = utils.get_from_dict(options, cloud_dict)

        def compute(img, previous):
            previous = ee.Image(previous)
            return previous.And(img)

        # all pixel with values 0 becomes invalid
        mask_image = ee.Image(masks_list.iterate(compute, masks_list.get(0))) 

        return image.updateMask(mask_image).copyProperties(image, ['system:time_start'])
    
    return apply_mask

def modis_8days_cloud_mask(masks = ['cloud', 'shadow', 'cirrus']):

    """ Function to mask out clouds and cirrus in Modis 8-day composite
    'MODIS/061/MOD09A1'

    param masks: list of mask to compute
    type masks: list
    RETURN: The function to apply a map() over a collection
    rtype: function
    
    """

    def apply_mask(image): 

        options = ee.List(masks)
        
        qa = image.select('StateQA')

        cloud = utils.bitwiseExtract(qa, 0, 1, 'cloud').eq(0) # cloud
        shadow = utils.bitwiseExtract(qa, 2, 2, 'shadow').eq(0) # shadow
        cirrus = utils.bitwiseExtract(qa, 8, 9, 'cirrus').eq(0) # Cirrus

        cloud_dict = ee.Dictionary({
            'cloud' : cloud,
            'shadow' : shadow,
            'cirrus' : cirrus       
        })
        
        masks_list = utils.get_from_dict(options, cloud_dict)

        def compute(img, previous):
            previous = ee.Image(previous)
            return previous.And(img)

        # all pixel with values 0 becomes invalid
        mask_image = ee.Image(masks_list.iterate(compute, masks_list.get(0))) 

        return image.updateMask(mask_image).copyProperties(image, ['system:time_start'])
    
    return apply_mask
