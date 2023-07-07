# coding=utf-8
""" Functions for calculation indices """
import ee

# FORMULAS = {
#     'NDVI': '(NIR-RED)/(NIR+RED)',
#     'EVI': 'G*((NIR-RED)/(NIR+(C1*RED)-(C2*BLUE)+L))',
#     'SAVI': '1.5 * (NIR - RED) / (NIR + RED + N)',
#     'MSAVI': '(2 * NIR + 10000 - sqrt(pow((2 * NIR + 10000), 2) - 8*(NIR - RED)))/2',
#     'NIRv': 'NIR * ((NIR - RED) / (NIR + RED))',
#     'NBR': '(NIR-SWIR2)/(NIR+SWIR2)',
#     'NBR2': '(SWIR-SWIR2)/(SWIR+SWIR2)',
#     'NDWI': '(NIR-SWIR)/(NIR+SWIR)'
# }

# AVAILABLE = FORMULAS.keys()

def ndvi(nir, red, bandname ='ndvi'):
    
    """ Calculates NDVI index: '(NIR-RED)/(NIR+RED)'

    :USE:
    .. code:: python
        # use in a collection
        col = ee.ImageCollection(ID)
        ndvi = col.map(indices.ndvi("B4", "B3"))
        # use in a single image
        img = ee.Image(ID)
        ndvi = Indices.ndvi("NIR", "RED")(img)
    :param nir: name of the Near Infrared () band
    :type nir: str
    :param red: name of the red () band
    :type red: str
    :param addBand: if True adds the index band to the others, otherwise
        returns just the index band
    :type addBand: bool
    :return: The function to apply a map() over a collection
    :rtype: function
    """
    
    def compute(image):
        ndvi = image.expression(
            '(NIR-RED)/(NIR+RED)', {
                'NIR': image.select(nir),
                'RED': image.select(red)}).rename(bandname)
        return image.addBands(ndvi)
    
    return compute

def evi(nir, red, blue, G=2.5, C1=6, C2=7.5, L=1, bandname='evi', scale_factor = 0.0000275, offset = -0.2):
    """ Calculates EVI index : 'G*((NIR-RED)/(NIR+(C1*RED)-(C2*BLUE)+L))'

    :param nir: name of the Near Infrared () band
    :type nir: str
    :param red: name of the red () band
    :type red: str
    :param blue: name of the blue () band
    :type blue: str
    :param G: G coefficient for the EVI index
    :type G: float
    :param C1: C1 coefficient for the EVI index
    :type C1: float
    :param C2: C2 coefficient for the EVI index
    :type C2: float
    :param L: L coefficient for the EVI index
    :type L: float
    :param addBand: if True adds the index band to the others, otherwise
        returns just the index band
    :return: The function to apply a map() over a collection
    :rtype: function
    """
    # L = float(L*scale_factor + offset)
    L = float(L)
    G = float(G)
    C1 = float(C1)
    C2 = float(C2)

    def compute(image):
        ndvi = image.expression(
            'G*((NIR-RED)/(NIR+(C1*RED)-(C2*BLUE)+L))', {
                'NIR': image.select(nir),
                'RED': image.select(red),
                'BLUE': image.select(blue),
                'G': G,
                'C1': C1,
                'C2': C2,
                'L': L
                }).rename(bandname)

        return image.addBands(ndvi)
    
    return compute

def savi(nir, red, L=0.5, G = 1.5, bandname='savi'):
    """ Calculates SAVI index: ((NIR - R) / (NIR + R + L)) * (1 + L)
    scaled using .multiply(0.0000275).add(-0.2)
    :param nir: name of the Near Infrared () band
    :type nir: str
    :param red: name of the red () band
    :type red: str
    :param G: G coefficient for the SAVI index
    :type G: float
    :param L: L coefficient for the SAVI index
    :type L: float
    :param addBand: if True adds the index band to the others, otherwise
        returns just the index band
    :return: The function to apply a map() over a collection
    :rtype: function
    """
    L = float(L)
    # G = float(G*scale_factor + offset)
    G = float(G)


    def compute(image):
        savi = image.expression(
            "((NIR - RED) / (NIR + RED + L)) * G", {
                'NIR': image.select(nir),
                'RED': image.select(red),
                'L': L,
                'G' : G
                }).rename(bandname)
        return image.addBands(savi)
    return compute

def msavi(nir, red, G=2, H=8, L=1, bandname='msavi'):
    """ Calculates SAVI index '(G * NIR + L - sqrt(pow((G * NIR + L), 2) - H*(NIR - RED)))/2'

    :param nir: name of the Near Infrared () band
    :type nir: str
    :param red: name of the red () band
    :type red: str
    :param G: G coefficient for the MSAVI index
    :type G: float
    :param H: H coefficient for the MSAVI index
    :type H: float
    :param L: L coefficient for the MSAVI index
    :type L: float
    :param addBand: if True adds the index band to the others, otherwise
        returns just the index band
    :return: The function to apply a map() over a collection
    :rtype: function
    """
    G = float(G)
    # L = float(L*scale_factor + offset)
    L = float(L)
    H = float(H)

    def compute(image):
        msavi = image.expression(
            '(G * NIR + L - sqrt(pow((G * NIR + L), 2) - H*(NIR - RED)))/2', {
                'NIR': image.select(nir),
                'RED': image.select(red),
                'L': L,
                'G' : G,
                'H': H
                }).rename(bandname)
        return image.addBands(msavi)
    return compute

def nirv(nir, red, bandname='nirv'):
    """ Calculates SAVI index: 'NIRv': 'NIR * ((NIR - RED) / (NIR + RED) - C)'

    reference paper: NIRv and SIF better estimate phenology than NDVI and EVI
    https://doi.org/10.1016/j.agrformet.2022.108819

    Canopy near-infrared reflectance and terrestrial photosynthesis
    DOI: 10.1126/sciadv.1602244

    :param nir: name of the Near Infrared () band
    :type nir: str
    :param red: name of the red () band
    :type red: str
    :param addBand: if True adds the index band to the others, otherwise
        returns just the index band
    :return: The function to apply a map() over a collection
    :rtype: function
    """

    def compute(image):
        nirv = image.expression(
            'NIR * ((NIR - RED) / (NIR + RED))', {
                'NIR': image.select(nir),
                'RED': image.select(red)
                }).rename(bandname)
        return image.addBands(nirv)

    return compute

'(NIR - SWIR) / (NIR + SWIR)'

def ndwi(nir, swir, bandname='ndwi'):
    """ Calculates SAVI index: '(NIR - SWIR) / (NIR + SWIR)''

    :param nir: name of the Near Infrared () band
    :type nir: str
    :param swir: name of the red () band
    :type swir: str
    :param addBand: if True adds the index band to the others, otherwise
        returns just the index band
    :return: The function to apply a map() over a collection
    :rtype: function
    """

    def compute(image):
        ndwi = image.expression(
            '(NIR - SWIR) / (NIR + SWIR)', {
                'NIR': image.select(nir),
                'SWIR': image.select(swir),
                }).rename(bandname)
        return image.addBands(ndwi)
        
    return compute

        