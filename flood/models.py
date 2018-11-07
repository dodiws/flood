from django.contrib.gis.db import models
from geodb.models import AfgShedaLvl4

class FloodRiskExposure(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.CharField(max_length=255, blank=True)
    code = models.CharField(max_length=255, blank=True)
    class Meta:
        managed = True
        db_table = 'FloodRiskExposure'

class AfgFldzonea100KNciaV2029Cm(models.Model):
    ogc_fid = models.IntegerField(primary_key=True)
    wkb_geometry = models.MultiPolygonField(dim=3, blank=True, null=True)
    id = models.IntegerField(blank=True, null=True)
    deeperthan = models.CharField(max_length=255, blank=True)
    province_n = models.CharField(max_length=255, blank=True)
    district_n = models.CharField(max_length=255, blank=True)
    basinname = models.CharField(max_length=255, blank=True)
    near_fid = models.IntegerField(blank=True, null=True)
    near_dist = models.FloatField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    objects = models.GeoManager()
    class Meta:
        managed = True
        db_table = 'afg_fldzonea_100k_ncia_v2_029cm'

class AfgFldzonea100KNciaV2121Cm(models.Model):
    ogc_fid = models.IntegerField(primary_key=True)
    wkb_geometry = models.MultiPolygonField(dim=3, blank=True, null=True)
    id = models.IntegerField(blank=True, null=True)
    deeperthan = models.CharField(max_length=255, blank=True)
    province_n = models.CharField(max_length=255, blank=True)
    district_n = models.CharField(max_length=255, blank=True)
    basinname = models.CharField(max_length=255, blank=True)
    shape_length = models.FloatField(blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    objects = models.GeoManager()
    class Meta:
        managed = True
        db_table = 'afg_fldzonea_100k_ncia_v2_121cm'

class AfgFldzonea100KNciaV2271Cm(models.Model):
    ogc_fid = models.IntegerField(primary_key=True)
    wkb_geometry = models.MultiPolygonField(dim=3, blank=True, null=True)
    id = models.IntegerField(blank=True, null=True)
    deeperthan = models.CharField(max_length=255, blank=True)
    province_n = models.CharField(max_length=255, blank=True)
    district_n = models.CharField(max_length=255, blank=True)
    basinname = models.CharField(max_length=255, blank=True)
    shape_length = models.FloatField(blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    objects = models.GeoManager()
    class Meta:
        managed = True
        db_table = 'afg_fldzonea_100k_ncia_v2_271cm'

class AfgFldzonea100KNciaV2Risk25Mbuffer(models.Model):
    ogc_fid = models.IntegerField(primary_key=True)
    wkb_geometry = models.MultiPolygonField(blank=True, null=True)
    deeperthan = models.CharField(max_length=255, blank=True)
    dist_code = models.IntegerField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    objects = models.GeoManager()
    class Meta:
        managed = True
        db_table = 'afg_fldzonea_100k_ncia_v2_risk_25mbuffer'

class AfgFldzonea100KRiskLandcoverPop(models.Model):
    ogc_fid = models.IntegerField(primary_key=True)
    wkb_geometry = models.MultiPolygonField(blank=True, null=True)
    deeperthan = models.CharField(max_length=255, blank=True)
    dist_code = models.IntegerField(blank=True, null=True)
    basin_id = models.FloatField(blank=True, null=True)
    aggcode_simplified = models.CharField(max_length=255, blank=True)
    agg_simplified_description = models.CharField(max_length=255, blank=True)
    area_population = models.FloatField(blank=True, null=True)
    area_buildings = models.IntegerField(blank=True, null=True)
    vuid = models.CharField(max_length=255, blank=True)
    lccs_main_description = models.CharField(max_length=255, blank=True)
    lccsuslb_simplified = models.CharField(max_length=255, blank=True)
    vuid_buildings = models.FloatField(blank=True, null=True)
    vuid_population = models.FloatField(blank=True, null=True)
    vuid_pop_per_building = models.FloatField(blank=True, null=True)
    type_settlement = models.CharField(max_length=255, blank=True)
    prov_code = models.IntegerField(blank=True, null=True)
    aggcode = models.CharField(max_length=255, blank=True)
    fldarea_sqm = models.FloatField(blank=True, null=True)
    fldarea_population = models.FloatField(blank=True, null=True)
    mitigated_pop = models.FloatField(blank=True, null=True)
    mitigated_area_sqm = models.FloatField(blank=True, null=True)
    vuid_area_sqm = models.FloatField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    basinmember = models.ForeignKey(AfgShedaLvl4, related_name='basinmembers')
    objects = models.GeoManager()
    class Meta:
        managed = True
        db_table = 'afg_fldzonea_100k_risk_landcover_pop'

class AfgFldzonea100KRiskMitigatedAreas(models.Model):
    ogc_fid = models.IntegerField(primary_key=True)
    wkb_geometry = models.MultiPolygonField(dim=3, blank=True, null=True)
    aggcode = models.CharField(max_length=255, blank=True)
    aggcode_simplified = models.CharField(max_length=255, blank=True)
    agg_simplified_description = models.CharField(max_length=255, blank=True)
    vuid = models.CharField(max_length=255, blank=True)
    vuid_buildings = models.FloatField(blank=True, null=True)
    vuid_population = models.FloatField(blank=True, null=True)
    vuid_pop_per_building = models.FloatField(blank=True, null=True)
    name_en = models.CharField(max_length=255, blank=True)
    type_settlement = models.CharField(max_length=255, blank=True)
    dist_code = models.IntegerField(blank=True, null=True)
    dist_na_en = models.CharField(max_length=255, blank=True)
    prov_na_en = models.CharField(max_length=255, blank=True)
    prov_code_1 = models.IntegerField(blank=True, null=True)
    deeperthan = models.CharField(max_length=255, blank=True)
    mitigated_fld_pop = models.FloatField(blank=True, null=True)
    mitigated_fld_area_sqm = models.FloatField(blank=True, null=True)
    mitigated = models.IntegerField(blank=True, null=True)
    mitigated_zone = models.IntegerField(blank=True, null=True)
    note = models.CharField(max_length=1023, blank=True)
    mitigation_type = models.CharField(max_length=255, blank=True)
    basin_id = models.FloatField(blank=True, null=True)
    area_buildings = models.IntegerField(blank=True, null=True)
    lccs_main_description = models.CharField(max_length=1023, blank=True)
    lccsuslb_simplified = models.CharField(max_length=255, blank=True)
    shape_length = models.FloatField(blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    objects = models.GeoManager()
    class Meta:
        managed = True
        db_table = 'afg_fldzonea_100k_risk_mitigated_areas'

class FlashFloodForecastedHistory(models.Model):
    vuid = models.CharField(max_length=255, blank=True)
    basin_id = models.FloatField(blank=True, null=True)
    datadate = models.DateField(blank=True, null=True)
    flashflood_forecast_verylow_pop = models.FloatField(blank=True, null=True)
    flashflood_forecast_low_pop = models.FloatField(blank=True, null=True)
    flashflood_forecast_med_pop = models.FloatField(blank=True, null=True)
    flashflood_forecast_high_pop = models.FloatField(blank=True, null=True)
    flashflood_forecast_veryhigh_pop = models.FloatField(blank=True, null=True)
    flashflood_forecast_extreme_pop = models.FloatField(blank=True, null=True)
    class Meta:
        managed = True
        db_table = 'flash_flood_forecasted_history'

class Glofasintegrated(models.Model):
    id = models.IntegerField(primary_key=True)
    basin_id = models.BigIntegerField(blank=True, null=True)
    datadate = models.DateField(blank=True, null=True)
    lon = models.FloatField(blank=True, null=True)
    lat = models.FloatField(blank=True, null=True)
    rl2 = models.FloatField(blank=True, null=True)
    rl5 = models.FloatField(blank=True, null=True)
    rl20 = models.FloatField(blank=True, null=True)
    rl2_dis_percent = models.IntegerField(blank=True, null=True)
    rl2_avg_dis_percent = models.IntegerField(blank=True, null=True)
    rl5_dis_percent = models.IntegerField(blank=True, null=True)
    rl5_avg_dis_percent = models.IntegerField(blank=True, null=True)
    rl20_dis_percent = models.IntegerField(blank=True, null=True)
    rl20_avg_dis_percent = models.IntegerField(blank=True, null=True)
    class Meta:
        managed = True
        db_table = 'glofasintegrated'

class RiverFloodForecastedHistory(models.Model):
    vuid = models.CharField(max_length=255, blank=True)
    basin_id = models.FloatField(blank=True, null=True)
    datadate = models.DateField(blank=True, null=True)
    riverflood_forecast_verylow_pop = models.FloatField(blank=True, null=True)
    riverflood_forecast_low_pop = models.FloatField(blank=True, null=True)
    riverflood_forecast_med_pop = models.FloatField(blank=True, null=True)
    riverflood_forecast_high_pop = models.FloatField(blank=True, null=True)
    riverflood_forecast_veryhigh_pop = models.FloatField(blank=True, null=True)
    riverflood_forecast_extreme_pop = models.FloatField(blank=True, null=True)
    class Meta:
        managed = True
        db_table = 'river_flood_forecasted_history'

