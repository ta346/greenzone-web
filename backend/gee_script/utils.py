import ee 
import pandas as pd

def create_reduce_region_function(geometry,
                                  reducer,
                                  scale=1000,
                                  crs='EPSG:4326',
                                  bestEffort=True,
                                  maxPixels=1e13,
                                  tileScale=4):
  """Creates a region reduction function.

  Creates a region reduction function intended to be used as the input function
  to ee.ImageCollection.map() for reducing pixels intersecting a provided region
  to a statistic for each image in a collection. See ee.Image.reduceRegion()
  documentation for more details.

  Args:
    geometry:
      An ee.Geometry that defines the region over which to reduce data.
    reducer:
      Optional; An ee.Reducer that defines the reduction method.
    scale:
      Optional; A number that defines the nominal scale in meters of the
      projection to work in.
    crs:
      Optional; An ee.Projection or EPSG string ('EPSG:5070') that defines
      the projection to work in.
    bestEffort:
      Optional; A Boolean indicator for whether to use a larger scale if the
      geometry contains too many pixels at the given scale for the operation
      to succeed.
    maxPixels:
      Optional; A number specifying the maximum number of pixels to reduce.
    tileScale:
      Optional; A number representing the scaling factor used to reduce
      aggregation tile size; using a larger tileScale (e.g. 2 or 4) may enable
      computations that run out of memory with the default.

  Returns:
    A function that accepts an ee.Image and reduces it by region, according to
    the provided arguments.
  """

  def reduce_region_function(img):
    """Applies the ee.Image.reduceRegion() method.

    Args:
      img:
        An ee.Image to reduce to a statistic by region.

    Returns:
      An ee.Feature that contains properties representing the image region
      reduction results per band and the image timestamp formatted as
      milliseconds from Unix epoch (included to enable time series plotting).
    """

    stat = img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=scale,
        crs=crs,
        bestEffort=bestEffort,
        maxPixels=maxPixels,
        tileScale=tileScale)

    return ee.Feature(geometry, stat).set({'millis': img.date().millis()})
  return reduce_region_function

def reduce_regions_function(reduction_regions,
                                  reducerAll = True, 
                                  scale=1000,
                                  crs='EPSG:4326',
                                  tileScale=1):
  """Creates multiple regions reduction function.

  Creates multiple regions reduction function intended to be used as the input function
  to ee.ImageCollection.map() for reducing pixels intersecting a provided region
  to a statistic for each image in a collection. See ee.Image.reduceRegions()
  documentation for more details.

  Args:
    collection:
      FeatureCollection - The features to reduce over
    reducer:
      Optional; An ee.Reducer that defines the reduction method.
    scale:
      Optional; A number that defines the nominal scale in meters of the
      projection to work in.
    crs:
      Optional; An ee.Projection or EPSG string ('EPSG:5070') that defines
      the projection to work in.
    tileScale:
      Optional; A number representing the scaling factor used to reduce
      aggregation tile size; using a larger tileScale (e.g. 2 or 4) may enable
      computations that run out of memory with the default.

  Returns:
    A function that accepts an ee.Image and reduces it by region, according to
    the provided arguments.
  """

  

  if reducerAll is True:
    reducerAll = (ee.Reducer.mean().combine(ee.Reducer.median(), '', True) 
              .combine(ee.Reducer.minMax(), '', True) 
              .combine(ee.Reducer.stdDev(), '', True) 
              .combine(ee.Reducer.intervalMean(10, 90).setOutputs(['int_mean_10_90']), '', True) 
              .combine(ee.Reducer.count(),'', True))
  else:
    reducerAll = (ee.Reducer.mean().combine(ee.Reducer.median(), '', True))

  def reduce_regions_function(image):
    """Applies the ee.Image.reduceRegion() method.

    Args:
      img:
        An ee.Image to reduce to a statistic by region.

    Returns:
      An ee.Feature that contains properties representing the image region
      reduction results per band and the image timestamp formatted as
      milliseconds from Unix epoch (included to enable time series plotting).
    """

    fc = image.reduceRegions(
        collection=reduction_regions,
        reducer=reducerAll,
        scale=scale,
        crs = crs,
        tileScale = tileScale
        ).set({'millis': image.date().millis()})
        
    filtered = fc.filter(ee.Filter.notNull(fc.first().propertyNames()))

    return filtered
    
  return reduce_regions_function

# Function to transfer feature properties to a dictionary.
def fc_to_dict(fc):
    """Creates multiple regions reduction function.

        Creates multiple regions reduction function intended to be used as the input function
        to ee.ImageCollection.map() for reducing pixels intersecting a provided region
        to a statistic for each image in a collection. See ee.Image.reduceRegions()
        documentation for more details.

        Args:
            collection:
            FeatureCollection - The features to reduce over
            reducer:
            Optional; An ee.Reducer that defines the reduction method.
            scale:
            Optional; A number that defines the nominal scale in meters of the
            projection to work in.
            crs:
            Optional; An ee.Projection or EPSG string ('EPSG:5070') that defines
            the projection to work in.
            tileScale:
            Optional; A number representing the scaling factor used to reduce
            aggregation tile size; using a larger tileScale (e.g. 2 or 4) may enable
            computations that run out of memory with the default.

        Returns:
            A function that accepts an ee.Image and reduces it by region, according to
            the provided arguments.
    """
    prop_names = fc.first().propertyNames()
    prop_lists = fc.reduceColumns(
        reducer=ee.Reducer.toList().repeat(prop_names.size()),
        selectors=prop_names).get('list')
    return ee.Dictionary.fromLists(prop_names, prop_lists)


# Function to add date variables to DataFrame.
def add_date_info(df):
    df['Timestamp'] = pd.to_datetime(df['millis'], unit='ms')
    df['Year'] = pd.DatetimeIndex(df['Timestamp']).year
    df['Month'] = pd.DatetimeIndex(df['Timestamp']).month
    df['Day'] = pd.DatetimeIndex(df['Timestamp']).day
    df['DOY'] = pd.DatetimeIndex(df['Timestamp']).dayofyear
    return df

def bitwiseExtract(img, fromBit, toBit, new_name):

  """ Function to extract the values from specific bits

  param img: image or number to compute
  type img: ee.Number() or ee.Image()

  param fromBit: start bit
  type fromBit: int

  param toBit: end bit
  type toBit: int

  """
  fromBit = ee.Number(fromBit)
  toBit = ee.Number(toBit)
  new_name = ee.String(new_name)

  maskSize = ee.Number(1).add(toBit).subtract(fromBit)
  mask = ee.Number(1).leftShift(maskSize).subtract(1)
  
  return img.rename([new_name]).rightShift(fromBit).bitwiseAnd(mask)
  
def get_from_dict(a_list, a_dict):
    
    """ Get a list of Dict's values from a list object. Keys must be unique
    :param a_list: list of keys
    :type a_list: ee.List
    :param a_dict: dict to get the values for list's keys
    :type a_dict: ee.Dictionary
    :return: a list of values
    :rtype: ee.List
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

# Applies scaling factors.
def applyScaleFactors(image):
    opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2).toFloat()
    thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0).toFloat()
    return (image.addBands(opticalBands, overwrite = True)
                .addBands(thermalBands, overwrite = True)
                )
def modis_scale_factor(img):
    bands = img.select('sur_ref1_b.').multiply(0.0001)
    return img.addBands(bands, overwrite = True)

def modis43A_scale_factor(img):
    bands = img.select('Nadir_Reflectance_Band.').multiply(0.0001)
    return img.addBands(bands, overwrite = True)

#6.1 Write harmonization between sensors function 
def harmonizationRoy_fromETM_OLI(img):
    '''
    harmonize TM (landsat 5) to OLI (Landsat 8)
    Slope and intercept from: Roy, D.P., Kovalskyy, V., Zhang, H.K., Vermote, E.F., Yan, L., Kumar, S.S, Egorov, A., 2016, 
    Characterization of Landsat-7 to Landsat-8 reflective wavelength and normalized difference vegetation index continuity, 
    Remote Sensing of Environment, 185, 57-70.(http:#dx.doi.Org/10.1016/j.rse.2015.12.024); Table 2 - reduced major axis (RMA) regression coefficients

    '''
    slopes = ee.Image.constant([0.9785, 0.9542, 0.9825, 1.0073, 1.0171, 0.9949])  # RMA - create an image of slopes per band for L7 TO L8 regression line - David Roy
    constants = ee.Image.constant([-0.0095, -0.0016, -0.0022, -0.0021, -0.0030, 0.0029])  # RMA - create an image of y-intercepts per band for L7 TO L8 regression line - David Roy
    y = img.select(['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7']).multiply(slopes).add(constants)  # select TM bands 1-5,7 and apply slope and intercept to band values
    
    return img.addBands(y, overwrite = True)

def harmonizationRoy_fromETMplus_OLI(img):
    '''
    harmonize ETM+ (Landsat 7) to OLI (Landsat 8)
    Slope and intercept from: Roy, D.P., Kovalskyy, V., Zhang, H.K., Vermote, E.F., Yan, L., Kumar, S.S, Egorov, A., 2016, 
    Characterization of Landsat-7 to Landsat-8 reflective wavelength and normalized difference vegetation index continuity, 
    Remote Sensing of Environment, 185, 57-70.(http:#dx.doi.Org/10.1016/j.rse.2015.12.024); Table 2 - reduced major axis (RMA) regression coefficients

    '''
    slopes = ee.Image.constant([0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071]) 
    constants = ee.Image.constant([0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172]) 
    y = img.select(['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7']).multiply(slopes).add(constants)  
    
    return img.addBands(y, overwrite = True)

def clip_aoi(image, box):
   return image.clip(box)

def get_image_metadata(image):

    crs = image.projection().getInfo()['crs']
    crs_transform = image.projection().getInfo()['transform']
    dimensions = image.getInfo()['bands'][0]['dimensions']

    return ee.Dictionary({
        'crs': crs,
        'crs_transform': crs_transform,
        'dimensions': dimensions
    })