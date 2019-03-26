import gdal
from gdalconst import GA_ReadOnly

data = gdal.Open ('data/hillshade.tif', GA_ReadOnly)
geoTransform = data.GetGeoTransform()
minx = geoTransform[0]
maxy = geoTransform[3]
maxx = minx + geoTransform[1] * data.RasterXSize
miny = maxy + geoTransform[5] * data.RasterYSize
print [minx, miny, maxx, maxy]
