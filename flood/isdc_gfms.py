from __future__ import absolute_import

import logging
import os
import datetime
import calendar
import struct
import re
import requests
from bs4 import BeautifulSoup as bs
from dataqs.helpers import gdal_translate
from dataqs.processor_base import GeoDataProcessor
from osgeo import gdal

from datetime import timedelta
import subprocess, sys

from geodb.models import AfgShedaLvl4, Forcastedvalue, forecastedLastUpdate
import csv

import fiona
from shapely.geometry import shape, mapping
import rtree

# ISDC
from dataqs.gfms.gfms import GFMSProcessor
from django.apps import apps
import geodb
from geodb.views import GS_TMP_DIR, initial_data_path, gdal_path

logger = logging.getLogger("dataqs.processors")

class ISDC_GFMSProcessor(GFMSProcessor):
    """
    Class for processing data from the Global Flood Management System
    """

    rows = 800
    cols = 2458

    header = """ncols        {cols}
    nrows        {rows}
    xllcorner    -128.5
    yllcorner    -50.0
    cellsize     0.125
    NODATA_value -9999
    """.format(cols=cols, rows=rows)

    base_url = "http://eagle2.umd.edu/flood/download/"
    layer_future = "gfms_latest"
    layer_current = "gfms_current"
    layer_current_24h = "gfms_current_24H"
    layer_current_48h = "gfms_current_48H"
    prefix = 'Flood_byStor_'
    
    # initial_data_path = "/Users/budi/Documents/iMMAP/DRR-datacenter/geodb/initialdata/" # in developement
    # gdal_path = '/usr/local/bin/' # development
    
    # initial_data_path = os.path.join(os.path.dirname(geodb.__file__), 'initialdata') # Production
    # gdal_path = '/usr/bin/' # production

    def get_most_current_24h(self):
        """
        Get the URL for the image of projected flood intensity,
        closest to current date/time
        :return: URL of the current image
        """
        today = datetime.datetime.utcnow()
        today = today+timedelta(days=1)
        month = today.strftime("%m")
        year = today.strftime("%Y")
        day = today.strftime("%d")
        hour = today.strftime("%H")

        if int(hour) > 21:
            hour = 21
        else:
            hour = int(hour) - (int(hour) % 3)
        hour = '{0:02d}'.format(hour)    

        base_url = self.base_url + "{year}/{year}{month}".format(
            year=year, month=month)
        latest_img = "{prefix}{year}{month}{day}{hour}.bin".format(
            prefix=self.prefix, year=year, month=month, day=day, hour=hour)
        img_url = "{}/{}".format(base_url, latest_img)
        return img_url   
        
    def get_most_current_48h(self):
        """
        Get the URL for the image of projected flood intensity,
        closest to current date/time
        :return: URL of the current image
        """
        today = datetime.datetime.utcnow()
        today = today+timedelta(days=2)
        month = today.strftime("%m")
        year = today.strftime("%Y")
        day = today.strftime("%d")
        hour = today.strftime("%H")

        if int(hour) > 21:
            hour = 21
        else:
            hour = int(hour) - (int(hour) % 3)
        hour = '{0:02d}'.format(hour)

        base_url = self.base_url + "{year}/{year}{month}".format(
            year=year, month=month)
        latest_img = "{prefix}{year}{month}{day}{hour}.bin".format(
            prefix=self.prefix, year=year, month=month, day=day, hour=hour)
        img_url = "{}/{}".format(base_url, latest_img)
        return img_url     

    def import_current(self):
        """
        Retrieve and process the GFMS image closest to the current date/time.
        """
        img_url = self.get_most_current()
        img_file = self.download(img_url)
        tif_file = self.convert(img_file)
        new_title = self.parse_title(tif_file)
        # self.post_geoserver(tif_file, self.layer_current)
        # self.update_geonode(self.layer_current, title=new_title)
        # self.truncate_gs_cache(self.layer_current)

    def import_current_24h(self):
        """
        Retrieve and process the GFMS image closest to the current date/time.
        """
        img_url = self.get_most_current_24h()
        img_file = self.download(img_url)
        tif_file = self.convert(img_file)
        new_title = self.parse_title(tif_file)
        self.post_geoserver(tif_file, self.layer_current_24h)
        self.update_geonode(self.layer_current_24h, title=new_title)
        self.truncate_gs_cache(self.layer_current_24h)

    def import_current_48h(self):
        """
        Retrieve and process the GFMS image closest to the current date/time.
        """
        img_url = self.get_most_current_48h()
        img_file = self.download(img_url)
        tif_file = self.convert(img_file)
        new_title = self.parse_title(tif_file)
        self.post_geoserver(tif_file, self.layer_current_48h)
        self.update_geonode(self.layer_current_48h, title=new_title)
        self.truncate_gs_cache(self.layer_current_48h)     

    def cropRaster(self, rasterIn, rasterOut):
        # subprocess.call([os.path.join(gdal_path,'gdalwarp'), '-cutline', os.path.join(initial_data_path,'afg_admbnda_int.shp'),'-crop_to_cutline', rasterIn, rasterOut])     
        # subprocess.call([os.path.join(gdal_path,'gdalwarp'), '-te 60 29 75 39','-srcnodata -9999', '-dstnodata -9999', rasterIn,  os.path.join(self.tmp_dir, 'outcroppedproc.tif')]) 
        subprocess.call('%s -overwrite -te 60 29 75 39 -srcnodata -9999 -dstnodata -9999 %s %s' %(os.path.join(gdal_path,'gdalwarp'), rasterIn, os.path.join(self.tmp_dir, 'outcroppedproc.tif')),shell=True)
        subprocess.call([os.path.join(gdal_path,'gdal_translate'), '-of', 'GTiff','-a_nodata', '0', os.path.join(self.tmp_dir, 'outcroppedproc.tif'),  rasterOut]) 
        return rasterOut

    def GetMossaic(self, file1, file2, file3, file4, outFile):
        subprocess.call('%s -A %s -B %s -C %s -D %s --outfile=%s --calc=\'maximum(maximum(maximum(A,B),C),D)\' --overwrite' %(os.path.join(gdal_path,'gdal_calc.py'),file1, file2, file3, file4, outFile),shell=True)
        return outFile    

    def run(self):
        """
        Retrieve and process both current and future GFMS images
        :return:
        """
        # working downloader
        img_url = self.get_most_current()
        img_file1 = self.download(img_url)
        tif_file1 = self.convert(img_file1)
        print tif_file1

        img_url = self.get_most_current_24h()
        try:
            img_file2 = self.download(img_url)
            tif_file2 = self.convert(img_file2)
        except:
            tif_file2 = tif_file1      
        print tif_file2

        img_url = self.get_most_current_48h()
        try:
            img_file3 = self.download(img_url)
            tif_file3 = self.convert(img_file3)
        except:
            tif_file3 = tif_file1
        print tif_file3

        img_url = self.get_latest_future()
        img_file4 = self.download(img_url)
        tif_file4 = self.convert(img_file4)
        print tif_file4
        
        out1 = self.cropRaster(os.path.join(self.tmp_dir, tif_file1), os.path.join(self.tmp_dir, 'outcropped1.tif'))
        out2 = self.cropRaster(os.path.join(self.tmp_dir, tif_file2), os.path.join(self.tmp_dir, 'outcropped2.tif'))
        out3 = self.cropRaster(os.path.join(self.tmp_dir, tif_file3), os.path.join(self.tmp_dir, 'outcropped3.tif'))
        out4 = self.cropRaster(os.path.join(self.tmp_dir, tif_file4), os.path.join(self.tmp_dir, 'outcropped4.tif'))

        targetfile = self.GetMossaic(out1, out2, out3, out4, os.path.join(self.tmp_dir, 'out.tif'))

        out = self.reclassification(targetfile, os.path.join(self.tmp_dir, 'out.tif')); 

        subprocess.call('%s %s -f "ESRI Shapefile" %s' %(os.path.join(gdal_path,'gdal_polygonize.py'), out, os.path.join(self.tmp_dir, 'out.shp')),shell=True)
        
        self.customIntersect(os.path.join(self.tmp_dir,'out.shp'), os.path.join(initial_data_path,'water.shp'))
        # print self.tmp_dir
        self.cleanup()

    def reclassification(self, fileIN, fileOUT):
        driver = gdal.GetDriverByName('GTiff')
        file1 = gdal.Open(fileIN)
        band = file1.GetRasterBand(1)
        lista = band.ReadAsArray()

        # reclassification
        for j in  range(file1.RasterXSize):
            for i in  range(file1.RasterYSize):
                # if lista[i,j] <= 0:
                #     lista[i,j] = 0
                # el
                if 0 < lista[i,j] <= 10:
                    lista[i,j] = 1
                elif 10 < lista[i,j] <= 20:
                    lista[i,j] = 2
                elif 20 < lista[i,j] <= 50:
                    lista[i,j] = 3
                elif 50 < lista[i,j] <= 100:
                    lista[i,j] = 4
                elif 100 < lista[i,j] <= 200:
                    lista[i,j] = 5        
                elif lista[i,j] > 200:
                    lista[i,j] = 6

        # create new file
        file2 = driver.Create(fileOUT, file1.RasterXSize , file1.RasterYSize , 1)
        file2.GetRasterBand(1).WriteArray(lista)

        # spatial ref system
        proj = file1.GetProjection()
        georef = file1.GetGeoTransform()
        file2.SetProjection(proj)
        file2.SetGeoTransform(georef)
        file2.FlushCache()
        return fileOUT

    def customIntersect(self,bufSHP,ctSHP):
        year = datetime.datetime.utcnow().strftime("%Y")
        month = datetime.datetime.utcnow().strftime("%m")
        day = datetime.datetime.utcnow().strftime("%d")
        hour = datetime.datetime.utcnow().strftime("%H")
        minute = datetime.datetime.utcnow().strftime("%M")
        with fiona.open(bufSHP, 'r') as layer1:
            with fiona.open(ctSHP, 'r') as layer2:
                # We copy schema and add the  new property for the new resulting shp
                schema = layer2.schema.copy()
                schema['properties']['uid'] = 'int:10'
                # We open a first empty shp to write new content from both others shp
                # with fiona.open(intSHP, 'w', 'ESRI Shapefile', schema) as layer3:
                index = rtree.index.Index()
                for feat1 in layer1:
                    fid = int(feat1['id'])
                    # print feat1['properties']['DN']
                    geom1 = shape(feat1['geometry'])
                    if feat1['properties']['DN']>0:
                        index.insert(fid, geom1.bounds)

                for feat2 in layer2:
                    geom2 = shape(feat2['geometry'])
                    for fid in list(index.intersection(geom2.bounds)):
                        if fid != int(feat2['id']):
                            feat1 = layer1[fid]
                            geom1 = shape(feat1['geometry'])
                            if geom1.intersects(geom2):
                                # We take attributes from ctSHP
                                props = feat2['properties']
                                props2 = feat1['properties']
                                # print props['value']
                                # print props2['DN']

                                basin = AfgShedaLvl4.objects.get(value=props['value']) 

                                recordExists = Forcastedvalue.objects.all().filter(datadate=year+'-'+month+'-'+day,forecasttype='riverflood',basin=basin)  
                                if recordExists.count() > 0:
                                    if recordExists[0].riskstate < props2['DN']:
                                        c = Forcastedvalue(pk=recordExists[0].pk,basin=basin)  
                                        c.riskstate = props2['DN']
                                        c.datadate = recordExists[0].datadate
                                        c.forecasttype = recordExists[0].forecasttype
                                        c.save()
                                    #     print 'riverflood modified'
                                    # print 'riverflood skip'    
                                else:
                                    c = Forcastedvalue(basin=basin)  
                                    c.datadate = year+'-'+month+'-'+day
                                    c.forecasttype = 'riverflood'
                                    c.riskstate = props2['DN'] 
                                    c.save()
                                    # print 'riverflood added'
        ff = forecastedLastUpdate(datadate=year+'-'+month+'-'+day+' '+hour+':'+minute,forecasttype='riverflood')
        ff.save()

if __name__ == '__main__':

    import django 
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "geonode.settings")
    if not apps.ready:
        django.setup()

    processor = ISDC_GFMSProcessor()
    processor.run()
