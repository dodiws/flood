from django.shortcuts import render
from .models import (
	AfgFldzonea100KRiskLandcoverPop,
	FloodRiskExposure,
	Glofasintegrated,
	)
from geodb.models import (
	AfgAdmbndaAdm1,
	AfgAdmbndaAdm2,
	AfgAirdrmp,
	# AfgAvsa,
	AfgCapaGsmcvr,
	AfgCaptAdm1ItsProvcImmap,
	AfgCaptAdm1NearestProvcImmap,
	AfgCaptAdm2NearestDistrictcImmap,
	AfgCaptAirdrmImmap,
	AfgCaptHltfacTier1Immap,
	AfgCaptHltfacTier2Immap,
	AfgCaptHltfacTier3Immap,
	AfgCaptHltfacTierallImmap,
	AfgHltfac,
	# AfgIncidentOasis,
	AfgLndcrva,
	AfgPplp,
	AfgRdsl,
	districtsummary,
	# earthquake_events,
	# earthquake_shakemap,
	forecastedLastUpdate,
	LandcoverDescription,
	provincesummary,
	tempCurrentSC,
	# villagesummaryEQ,
	)
from geodb.geo_calc import (
	getBaseline,
	getCommonUse,
	# getFloodForecastBySource,
	# getFloodForecastMatrix,
	getGeoJson,
	getProvinceSummary_glofas,
	getProvinceSummary_glofas_formatter,
	getProvinceSummary,
	getRawBaseLine,
	# getRawFloodRisk,
	# getSettlementAtFloodRisk,
	getShortCutData,
	getTotalArea,
	getTotalBuildings,
	getTotalPop,
	getTotalSettlement,
	getRiskNumber,
	getShortCutDataFormatter,
	)
from geodb.views import (
	get_nc_file_from_ftp,
	getCommonVillageData,
	)
# from geodb.geoapi import getRiskExecuteExternal
# from .riverflood import getFloodForecastBySource
from django.db import connection, connections
from django.db.models import Count, Sum
from geonode.maps.views import _resolve_map, _PERMISSION_MSG_VIEW
from geonode.utils import include_section, none_to_zero, query_to_dicts, RawSQL_nogroupby, ComboChart, merge_dict, div_by_zero_is_zero, dict_ext, list_ext
from matrix.models import matrix
from pprint import pprint
from pytz import timezone, all_timezones
from tastypie.cache import SimpleCache
from tastypie.resources import ModelResource, Resource
from urlparse import urlparse
from django.conf import settings
from netCDF4 import Dataset, num2date
from django.utils.translation import ugettext as _
from graphos.renderers import flot, gchart
from graphos.sources.simple import SimpleDataSource
from django.shortcuts import render_to_response
from django.template import RequestContext

import json
import time, datetime
import timeago
from geodb.enumerations import HEALTHFAC_TYPES, LANDCOVER_TYPES, LIKELIHOOD_INDEX, LIKELIHOOD_TYPES, DEPTH_TYPES, DEPTH_TYPES_INVERSE, LANDCOVER_TYPES_INVERSE, LIKELIHOOD_INDEX_INVERSE, LANDCOVER_TYPES_GROUP, DEPTH_INDEX, DEPTH_TYPES, DEPTH_TYPES_SIMPLE

gchart.ComboChart = ComboChart

def get_dashboard_meta(*args,**kwargs):
	# if page_name == 'floodforecast':
	# 	return {'function':dashboard_floodforecast, 'template':'dash_fforecast.html'}
	# elif page_name == 'floodrisk':
	# 	return {'function':dashboard_floodrisk, 'template':'dash_frisk.html'}
	response = {
		'pages': [
			{
				'name': 'floodforecast',
				'function': dashboard_floodforecast, 
				'template': 'dash_fforecast.html',
				'menutitle': 'Flood Forecast',
			},
			{
				'name': 'floodrisk',
				'function': dashboard_floodrisk, 
				'template': 'dash_frisk.html',
				'menutitle': 'Flood Risk',
			},
		],
		'menutitle': 'Flood',
	}
	return response

def getQuickOverview(request, filterLock, flag, code, includes=[], excludes=[]):
	response = {}
	response.update(getFloodForecast(request, filterLock, flag, code, excludes=['getCommonUse','detail']))
	response.update(getRawFloodRisk(filterLock, flag, code, excludes=['landcoverfloodrisk']))
	return response

# from geodb.geo_calc

def getFloodForecast(request, filterLock, flag, code, includes=[], excludes=[], rf_types=None, date=''):
	response = dict_ext()

	try:
		YEAR, MONTH, DAY = date.split('-')
	except Exception as e:
		YEAR, MONTH, DAY = datetime.datetime.utcnow().strftime("%Y %m %d").split()
		
	reverse_date = datetime.datetime(year=int(YEAR), month=int(MONTH), day=int(DAY)) - datetime.timedelta(days=1)

	targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all()
	targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')

	spt_filter = request.GET.get('filter') or 'NULL'

	response['rf_types'] = rf_types = rf_types or ['gfms','glofas','gfms_glofas',]
	for rf_type in rf_types:
		if include_section('riverflood', includes, excludes):
			response.path('bysource')[rf_type] = getFloodForecastBySource(rf_type, targetRisk, spt_filter, flag, code, YEAR, MONTH, DAY, formatted=True)
		if include_section('detail', includes, excludes):
			if rf_type == 'gfms':
				response.path('child_bysource')[rf_type] = getProvinceSummary(filterLock, flag, code)
			if rf_type == 'glofas':
				response.path('child_bysource')[rf_type] = getProvinceSummary_glofas(filterLock, flag, code, reverse_date.strftime("%Y"), reverse_date.strftime("%m"), reverse_date.strftime("%d"), False, formatted=False)
			if rf_type == 'gfms_glofas':
				response.path('child_bysource')[rf_type] = getProvinceSummary_glofas(filterLock, flag, code, YEAR, MONTH, int(DAY), True, formatted=False)

	if include_section('GeoJson', includes, excludes):
		response['GeoJson'] = getGeoJson(request, flag, code)

	if include_section('flashflood', includes, excludes):

		basequery = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY))
		counts =  getRiskNumber(basequery, filterLock, 'basinmember__basins__riskstate', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, 'afg_fldzonea_100k_risk_landcover_pop')

		sliced = {c['basinmember__basins__riskstate']:c['count'] for c in counts}
		response['pop_flashflood_likelihood'] = {v:sliced.get(v) or 0 for k,v in LIKELIHOOD_INDEX.items()}
		response['pop_flashflood_likelihood_total'] = sum(response.path('floodforecast','pop_flashflood_likelihood').values())

		sliced = {c['basinmember__basins__riskstate']:c['areaatrisk'] for c in counts}
		response['area_flashflood_likelihood'] = {v:round((sliced.get(v) or 0)/1000000,0) for k,v in LIKELIHOOD_INDEX.items()}
		response['area_flashflood_likelihood_total'] = sum(response.path('floodforecast','area_flashflood_likelihood').values())

		sliced = {c['basinmember__basins__riskstate']:c['houseatrisk'] for c in counts}
		response['building_flashflood_likelihood'] = {v:sliced.get(v) or 0 for k,v in LIKELIHOOD_INDEX.items()}
		response['building_flashflood_likelihood_total'] = sum(response.path('floodforecast','building_flashflood_likelihood').values())

		r = response
		f = response.path('bysource')[next(iter(response.path('bysource')))] # get first forecast
		r['pop_likelihood_total'] = f['pop_riverflood_likelihood_total'] + r['pop_flashflood_likelihood_total']
		r['area_likelihood_total'] = f['area_riverflood_likelihood_total'] + r['area_flashflood_likelihood_total']

		response = dict_ext(none_to_zero(response))

		px = none_to_zero(getFloodForecastRisk(filterLock, flag, code, targetRisk, YEAR, MONTH, DAY, floodtype='flashflood'))

		response['pop_flashflood_likelihood_depth']={l:{d:0 for d in DEPTH_TYPES} for l in LIKELIHOOD_INDEX_INVERSE}
		response['building_flashflood_likelihood_depth']={l:{d:0 for d in DEPTH_TYPES} for l in LIKELIHOOD_INDEX_INVERSE}

		for row in px:
			likelihood = LIKELIHOOD_INDEX[row['basinmember__basins__riskstate']]
			depth = DEPTH_TYPES_INVERSE[row['deeperthan']]
			response['pop_flashflood_likelihood_depth'][likelihood][depth]=round(row['population'] or 0,0)
			response['building_flashflood_likelihood_depth'][likelihood][depth]=round(row['building'] or 0,0)

	if include_section('lastupdated', includes, excludes):

		try:
			row = forecastedLastUpdate.objects.filter(forecasttype='snowwater').latest('datadate')
		except forecastedLastUpdate.DoesNotExist:
			response.path('lastupdated')["snowwater"] = None
		else:
			response.path('lastupdated')["snowwater"] = timeago.format(row.datadate, datetime.datetime.utcnow())   #tempSW.strftime("%d-%m-%Y %H:%M")

		try:
			row = forecastedLastUpdate.objects.filter(forecasttype='riverflood').latest('datadate')
		except forecastedLastUpdate.DoesNotExist:
			response.path('lastupdated')["riverflood"] = None
		else:
			response.path('lastupdated')["riverflood"] = timeago.format(row.datadate, datetime.datetime.utcnow())  #tempRF.strftime("%d-%m-%Y %H:%M")

	return response

def getFloodForecast_ORIG(request, filterLock, flag, code, includes=[], excludes=[]):
	response = {}
	if include_section('getCommonUse', includes, excludes):
		response = getCommonUse(request, flag, code)

	includeDetailState = True
	if 'date' in request.GET:
		curdate = datetime.datetime(int(request.GET['date'].split('-')[0]), int(request.GET['date'].split('-')[1]), int(request.GET['date'].split('-')[2]), 00, 00)
		includeDetailState = False
	else:
		curdate = datetime.datetime.utcnow()

	YEAR = curdate.strftime("%Y")
	MONTH = curdate.strftime("%m")
	DAY = curdate.strftime("%d")
	reverse_date = curdate - datetime.timedelta(days=1)

	targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all()
	targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')

	flood_parent = getFloodForecastMatrix(filterLock, flag, code)
	for i in flood_parent:
		response[i]=flood_parent[i]

	spt_filter = 'NULL'
	if 'filter' in request.GET:
		spt_filter = request.GET['filter']

	gfms_glofas_parent = getFloodForecastBySource('GFMS + GLOFAS', targetRisk, spt_filter, flag, code, YEAR, MONTH, DAY)
	for i in gfms_glofas_parent:
		response['gfms_glofas_'+i]=gfms_glofas_parent[i]

	glofas_parent = getFloodForecastBySource('GLOFAS only', targetRisk, spt_filter, flag, code, YEAR, MONTH, DAY)
	for i in glofas_parent:
		response['glofas_'+i]=glofas_parent[i] or 0

	if includeDetailState:
		if include_section('detail', includes, excludes):
			data = getProvinceSummary(filterLock, flag, code)
			response['lc_child']=data

			data = getProvinceSummary_glofas(filterLock, flag, code, reverse_date.strftime("%Y"), reverse_date.strftime("%m"), reverse_date.strftime("%d"), False)
			response['glofas_child']=data

			data = getProvinceSummary_glofas(filterLock, flag, code, YEAR, MONTH, int(DAY), True)
			response['glofas_gfms_child']=data

	if include_section('GeoJson', includes, excludes):
		response['GeoJson'] = json.dumps(getGeoJson(request, flag, code))

	return response

def getFloodRisk(request, filterLock, flag, code, includes=[], excludes=[]):
	
	# response = dict_ext(getCommonUse(request, flag, code))
	response = dict_ext()

	targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all()
	targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')
	targetBase = AfgLndcrva.objects.all()

	if include_section(['baseline','pop_depth','area_depth','building_depth'], includes, excludes):
		response = getBaseline(request, filterLock, flag, code, includes, excludes, baselineonly=False)
		cached = flag in ['entireAfg','currentProvince']
		if cached:

			# separate query for building_depth because not cached
			counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0), filterLock, 'deeperthan', None, None, 'area_buildings', flag, code, None)
			sliced = {c['deeperthan']:c['houseatrisk'] for c in counts}
			response.path('floodrisk')['building_depth'] = {k:(sliced.get(v) or 0) for k,v in DEPTH_TYPES.items()}

		else:
			# response['baseline'] = getBaseline(filterLock, flag, code, includes=['pop_lc','area_lc','building_lc'])

			counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0), filterLock, 'deeperthan', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, None)

			sliced = {c['deeperthan']:c['count'] for c in counts}
			response.path('floodrisk')['pop_depth'] = {k:(sliced.get(v) or 0) for k,v in DEPTH_TYPES.items()}

			sliced = {c['deeperthan']:c['areaatrisk'] for c in counts}
			response.path('floodrisk')['area_depth'] = {k:round((sliced.get(v) or 0)/1000000,1) for k,v in DEPTH_TYPES.items()}

			sliced = {c['deeperthan']:c['houseatrisk'] for c in counts}
			response.path('floodrisk')['building_depth'] = {k:(sliced.get(v) or 0) for k,v in DEPTH_TYPES.items()}
			# response.path('floodrisk')['building_total'] = sum([c['houseatrisk'] for c in counts if c['deeperthan'] in DEPTH_TYPES_INVERSE])

			counts =  getRiskNumber(targetRiskIncludeWater.exclude(mitigated_pop__gt=0), filterLock, 'agg_simplified_description', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, None)

			sliced = {c['agg_simplified_description']:c['count'] for c in counts}
			response.path('floodrisk')['pop_lc'] = {k:sliced.get(v) or 0 for k,v in LANDCOVER_TYPES.items()}

			sliced = {c['agg_simplified_description']:c['areaatrisk'] for c in counts}
			response.path('floodrisk')['area_lc'] = {k:round((sliced.get(v) or 0)/1000000, 1) for k,v in LANDCOVER_TYPES.items()}

			response.path('floodrisk')['settlement_likelihood_total'] = getSettlementAtFloodRisk(filterLock, flag, code)

		response.path('floodrisk')['pop_lcgroup'] = {k:sum([response['floodrisk']['pop_lc'].get(i) or 0 for i in v]) for k,v in LANDCOVER_TYPES_GROUP.items()}
		response.path('floodrisk')['area_lcgroup'] = {k:sum([response['floodrisk']['area_lc'].get(i) or 0 for i in v]) for k,v in LANDCOVER_TYPES_GROUP.items()}
		
		response.path('floodrisk')['pop_total'] = sum(response['floodrisk']['pop_depth'].values())
		response.path('floodrisk')['area_total'] = sum(response['floodrisk']['area_depth'].values())
		response.path('floodrisk')['building_total'] = sum(response['floodrisk']['building_depth'].values())

	if include_section(['mitigatedpop_depth'], includes, excludes):
		counts = getRiskNumber(targetRisk.exclude(mitigated_pop=0), filterLock, 'deeperthan', 'mitigated_pop', 'fldarea_sqm', 'area_buildings', flag, code, None)

		sliced = {c['deeperthan']:c['count'] for c in counts}
		response.path('floodrisk')['mitigatedpop_depth'] = {k:sliced.get(v) or 0 for k,v in DEPTH_TYPES.items()}
		response.path('floodrisk')['mitigatedpop_depth_total'] = sum(response['floodrisk']['mitigatedpop_depth'].values())

	response.path('floodrisk')['pop_depth_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['pop_total'])*100, 0) for k,v in response['floodrisk']['pop_depth'].items()}
	response.path('floodrisk')['pop_depth_percent_total'] = sum(response.path('floodrisk')['pop_depth_percent'].values())

	response.path('floodrisk')['area_depth_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['area_total'])*100, 0) for k,v in response['floodrisk']['area_depth'].items()}
	response.path('floodrisk')['area_depth_percent_total'] = sum(response.path('floodrisk')['area_depth_percent'].values())

	response.path('floodrisk')['building_depth_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['building_total'])*100, 0) for k,v in response['floodrisk']['building_depth'].items()}
	response.path('floodrisk')['building_depth_percent_total'] = sum(response.path('floodrisk')['building_depth_percent'].values())

	response.path('floodrisk')['pop_lc_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['pop_lc'][k])*100, 0) for k,v in response['floodrisk']['pop_lc'].items()}
	response.path('floodrisk')['area_lc_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['area_lc'][k])*100, 0) for k,v in response['floodrisk']['area_lc'].items()}

	response.path('floodrisk')['settlement_likelihood_total_percent'] = int(round((div_by_zero_is_zero((response.path('floodrisk')['settlement_likelihood_total'] or 0),(response.path('baseline')['settlement_total'] or 1)))*100,0))
	# response.path('floodrisk')['pop_depth_percent'] = {k:int(round((div_by_zero_is_zero((v or 0),(response['floodrisk']['pop_total'] or 1)))*100,0)) for k,v in response.path('floodrisk')['pop_depth'].items()}
	response.path('floodrisk')['pop_lcgroup_percent'] = {k:int(round((div_by_zero_is_zero((v or 0),(response['floodrisk']['pop_lcgroup'][k] or 1)))*100,0)) for k,v in response.path('floodrisk')['pop_lcgroup'].items()}
	response.path('floodrisk')['area_lcgroup_percent'] = {k:int(round((div_by_zero_is_zero((v or 0),(response['floodrisk']['area_lcgroup'][k] or 1)))*100,0)) for k,v in response.path('floodrisk')['area_lcgroup'].items()}

	#if include_section('GeoJson', includes, excludes):
	# response['GeoJson'] = json.dumps(getGeoJson(request, flag, code))

	return response

def getFloodRisk_ORIG(request, filterLock, flag, code, includes=[], excludes=[]):
	targetBase = AfgLndcrva.objects.all()
	response = getCommonUse(request, flag, code)

	if flag not in ['entireAfg','currentProvince']:
		response['Population']=getTotalPop(filterLock, flag, code, targetBase)
		response['Area']=getTotalArea(filterLock, flag, code, targetBase)
		response['Buildings']=getTotalBuildings(filterLock, flag, code, targetBase)
		response['settlement']=getTotalSettlement(filterLock, flag, code, targetBase)
	else :
		tempData = getShortCutData(flag,code)
		response['Population']= tempData['Population']
		response['Area']= tempData['Area']
		response['Buildings']= tempData['total_buildings']
		response['settlement']= tempData['settlements']

	rawBaseline = getRawBaseLine(filterLock, flag, code)
	rawFloodRisk = getRawFloodRisk(filterLock, flag, code)

	for i in rawBaseline:
		response[i]=rawBaseline[i]

	for i in rawFloodRisk:
		response[i]=rawFloodRisk[i]

	response = none_to_zero(response)

	if response['Population']==0:
		response['Population'] = 0.000001
	if response['Buildings']==0:
		response['Buildings'] = 0.000001
	if response['built_up_pop']==0:
		response['built_up_pop'] = 0.000001
	if response['built_up_area']==0:
		response['built_up_area'] = 0.000001
	if response['cultivated_pop']==0:
		response['cultivated_pop'] = 0.000001
	if response['cultivated_area']==0:
		response['cultivated_area'] = 0.000001
	if response['barren_pop']==0:
		response['barren_pop'] = 0.000001
	if response['barren_area']==0:
		response['barren_area'] = 0.000001

	response['settlement_at_floodrisk'] = getSettlementAtFloodRisk(filterLock, flag, code)
	response['settlement_at_floodrisk_percent'] = int(round(((response['settlement_at_floodrisk'] or 0)/(response['settlement'] or 1))*100,0))

	response['total_pop_atrisk_percent'] = int(round(((response['total_risk_population'] or 0)/(response['Population'] or 1))*100,0))
	response['total_area_atrisk_percent'] = int(round(((response['total_risk_area'] or 0)/(response['Area'] or 1))*100,0))

	response['total_pop_high_atrisk_percent'] = int(round(((response['high_risk_population'] or 0)/(response['Population'] or 1))*100,0))
	response['total_pop_med_atrisk_percent'] = int(round(((response['med_risk_population'] or 0)/(response['Population'] or 1))*100,0))
	response['total_pop_low_atrisk_percent'] = int(round(((response['low_risk_population'] or 0)/(response['Population'] or 1))*100,0))

	response['built_up_pop_risk_percent'] = int(round(((response['built_up_pop_risk'] or 0)/(response['built_up_pop'] or 1))*100,0))
	response['built_up_area_risk_percent'] = int(round(((response['built_up_area_risk'] or 0)/(response['built_up_area'] or 1))*100,0))

	response['cultivated_pop_risk_percent'] = int(round(((response['cultivated_pop_risk'] or 0)/(response['cultivated_pop'] or 1))*100,0))
	response['cultivated_area_risk_percent'] = int(round(((response['cultivated_area_risk'] or 0)/(response['cultivated_area'] or 0))*100,0))

	response['barren_pop_risk_percent'] = int(round(((response['barren_pop_risk'] or 0)/(response['barren_pop'] or 1))*100,0))
	response['barren_area_risk_percent'] = int(round(((response['barren_area_risk'] or 0)/(response['barren_area'] or 1))*100,0))

	data1 = []
	data1.append(['agg_simplified_description','area_population'])
	data1.append(['',response['total_risk_population']])
	data1.append(['',response['Population']-response['total_risk_population']])
	# response['total_pop_atrisk_chart'] = gchart.PieChart(SimpleDataSource(data=data1), html_id="pie_chart1", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	data2 = []
	data2.append(['agg_simplified_description','area_population'])
	data2.append(['',response['high_risk_population']])
	data2.append(['',response['Population']-response['high_risk_population']])
	# response['high_pop_atrisk_chart'] = gchart.PieChart(SimpleDataSource(data=data2), html_id="pie_chart2", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	data3 = []
	data3.append(['agg_simplified_description','area_population'])
	data3.append(['',response['med_risk_population']])
	data3.append(['',response['Population']-response['med_risk_population']])
	# response['med_pop_atrisk_chart'] = gchart.PieChart(SimpleDataSource(data=data3), html_id="pie_chart3", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	data4 = []
	data4.append(['agg_simplified_description','area_population'])
	data4.append(['',response['low_risk_population']])
	data4.append(['',response['Population']-response['low_risk_population']])
	# response['low_pop_atrisk_chart'] = gchart.PieChart(SimpleDataSource(data=data4), html_id="pie_chart4", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	data = getProvinceSummary(filterLock, flag, code)

	for i in data:
		if i['Population']==0:
			i['Population'] = 0.000001
		if i['built_up_pop']==0:
			i['built_up_pop'] = 0.000001
		if i['built_up_area']==0:
			i['built_up_area'] = 0.000001
		if i['cultivated_pop']==0:
			i['cultivated_pop'] = 0.000001
		if i['cultivated_area']==0:
			i['cultivated_area'] = 0.000001
		if i['barren_pop']==0:
			i['barren_pop'] = 0.000001
		if i['barren_area']==0:
			i['barren_area'] = 0.000001

		i['settlement_at_floodrisk_percent'] = int(round((i['settlements_at_risk'] or 0)/(i['settlements'] or 1)*100,0))
		i['total_pop_atrisk_percent'] = int(round((i['total_risk_population'] or 0)/(i['Population'] or 1)*100,0))
		i['total_area_atrisk_percent'] = int(round((i['total_risk_area'] or 0)/(i['Area'] or 1)*100,0))
		i['built_up_pop_risk_percent'] = int(round((i['built_up_pop_risk'] or 0)/(i['built_up_pop'] or 1)*100,0))
		i['built_up_area_risk_percent'] = int(round((i['built_up_area_risk'] or 0)/(i['built_up_area'] or 1)*100,0))
		i['cultivated_pop_risk_percent'] = int(round((i['cultivated_pop_risk'] or 0)/(i['cultivated_pop'] or 1)*100,0))
		i['cultivated_area_risk_percent'] = int(round((i['cultivated_area_risk'] or 0)/(i['cultivated_area'] or 1)*100,0))
		i['barren_pop_risk_percent'] = int(round((i['barren_pop_risk'] or 0)/(i['barren_pop'] or 1)*100,0))
		i['barren_area_risk_percent'] = int(round((i['barren_area_risk'] or 0)/(i['barren_area'] or 1)*100,0))

	response['lc_child']=data

	#if include_section('GeoJson', includes, excludes):
	response['GeoJson'] = json.dumps(getGeoJson(request, flag, code))

	return response

def getRawFloodRisk(filterLock, flag, code, includes=[], excludes=[]):
	# deprecated; instead use getFloodRisk(include={pop_depth','area_depth','building_depth})
	response = {}
	targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all()
	targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')

	# Flood Risk
	counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0), filterLock, 'deeperthan', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, None)

	# pop at risk level
	temp = dict([(c['deeperthan'], c['count']) for c in counts])
	response['high_risk_population']=round(temp.get('271 cm', 0) or 0,0)
	response['med_risk_population']=round(temp.get('121 cm', 0) or 0, 0)
	response['low_risk_population']=round(temp.get('029 cm', 0) or 0,0)
	response['total_risk_population']=response['high_risk_population']+response['med_risk_population']+response['low_risk_population']

	# building at risk level
	temp = dict([(c['deeperthan'], c['houseatrisk']) for c in counts])
	response['high_risk_buildings']=round(temp.get('271 cm', 0) or 0,0)
	response['med_risk_buildings']=round(temp.get('121 cm', 0) or 0, 0)
	response['low_risk_buildings']=round(temp.get('029 cm', 0) or 0,0)
	response['total_risk_buildings']=response['high_risk_buildings']+response['med_risk_buildings']+response['low_risk_buildings']


	# area at risk level
	temp = dict([(c['deeperthan'], c['areaatrisk']) for c in counts])
	response['high_risk_area']=round((temp.get('271 cm', 0) or 0)/1000000,1)
	response['med_risk_area']=round((temp.get('121 cm', 0) or 0)/1000000,1)
	response['low_risk_area']=round((temp.get('029 cm', 0) or 0)/1000000,1)
	response['total_risk_area']=round(response['high_risk_area']+response['med_risk_area']+response['low_risk_area'],2)

	if include_section('landcoverfloodrisk', includes, excludes):
		counts =  getRiskNumber(targetRiskIncludeWater.exclude(mitigated_pop__gt=0), filterLock, 'agg_simplified_description', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, None)

		# landcover/pop/atrisk
		temp = dict([(c['agg_simplified_description'], c['count']) for c in counts])
		response['built_up_pop_risk'] = round(temp.get('Build Up', 0) or 0,0)
		response['cultivated_pop_risk'] = round(temp.get('Fruit Trees', 0) or 0,0)+round(temp.get('Irrigated Agricultural Land', 0) or 0,0)+round(temp.get('Rainfed', 0) or 0,0)+round(temp.get('Vineyards', 0) or 0,0)
		response['barren_pop_risk'] = round(temp.get('Barren land', 0) or 0,0)+round(temp.get('Snow', 0) or 0,0) +round(temp.get('Rangeland', 0) or 0,0)+round(temp.get('Sand Covered Areas', 0) or 0,0)+round(temp.get('Forest & Shrub', 0) or 0,0)+round(temp.get('Sand Dunes', 0) or 0,0)

		temp = dict([(c['agg_simplified_description'], c['areaatrisk']) for c in counts])
		response['built_up_area_risk'] = round((temp.get('Build Up', 0) or 0)/1000000,1)
		response['cultivated_area_risk'] = round((temp.get('Fruit Trees', 0) or 0)/1000000,1)+round((temp.get('Irrigated Agricultural Land', 0) or 0)/1000000,1)+round((temp.get('Rainfed', 0) or 0)/1000000,1)+round((temp.get('Vineyards', 0) or 0)/1000000,1)
		response['barren_area_risk'] = round((temp.get('Barren land', 0) or 0)/1000000,1)+round((temp.get('Snow', 0) or 0)/1000000,1)+round((temp.get('Rangeland', 0) or 0)/1000000,1)+round((temp.get('Sand Covered Areas', 0) or 0)/1000000,1)+round((temp.get('Forest & Shrub', 0) or 0)/1000000,1)+round((temp.get('Sand Dunes', 0) or 0)/1000000,1)

	return response

def getFloodForecastMatrix(filterLock, flag, code, includes=[], excludes=[]):
	response = {}

	YEAR = datetime.datetime.utcnow().strftime("%Y")
	MONTH = datetime.datetime.utcnow().strftime("%m")
	DAY = datetime.datetime.utcnow().strftime("%d")

	targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all()
	targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')

	if include_section('risk_mitigated_population', includes, excludes):
		counts =  getRiskNumber(targetRisk.exclude(mitigated_pop=0), filterLock, 'deeperthan', 'mitigated_pop', 'fldarea_sqm', 'area_buildings', flag, code, None)
		temp = dict([(c['deeperthan'], c['count']) for c in counts])
		response['high_risk_mitigated_population']=round(temp.get('271 cm', 0) or 0,0)
		response['med_risk_mitigated_population']=round(temp.get('121 cm', 0) or 0, 0)
		response['low_risk_mitigated_population']=round(temp.get('029 cm', 0) or 0,0)
		response['total_risk_mitigated_population']=response['high_risk_mitigated_population']+response['med_risk_mitigated_population']+response['low_risk_mitigated_population']

	# River Flood Forecasted
	if include_section('riverflood_forecast', includes, excludes):
		counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='riverflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY)), filterLock, 'basinmember__basins__riskstate', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, 'afg_fldzonea_100k_risk_landcover_pop')
		temp = dict([(c['basinmember__basins__riskstate'], c['count']) for c in counts])
		response['riverflood_forecast_verylow_pop']=round(temp.get(1, 0) or 0,0)
		response['riverflood_forecast_low_pop']=round(temp.get(2, 0) or 0,0)
		response['riverflood_forecast_med_pop']=round(temp.get(3, 0) or 0,0)
		response['riverflood_forecast_high_pop']=round(temp.get(4, 0) or 0,0)
		response['riverflood_forecast_veryhigh_pop']=round(temp.get(5, 0) or 0,0)
		response['riverflood_forecast_extreme_pop']=round(temp.get(6, 0) or 0,0)
		response['total_riverflood_forecast_pop']=response['riverflood_forecast_verylow_pop'] + response['riverflood_forecast_low_pop'] + response['riverflood_forecast_med_pop'] + response['riverflood_forecast_high_pop'] + response['riverflood_forecast_veryhigh_pop'] + response['riverflood_forecast_extreme_pop']

		temp = dict([(c['basinmember__basins__riskstate'], c['areaatrisk']) for c in counts])
		response['riverflood_forecast_verylow_area']=round(temp.get(1, 0)/1000000,0)
		response['riverflood_forecast_low_area']=round(temp.get(2, 0)/1000000,0)
		response['riverflood_forecast_med_area']=round(temp.get(3, 0)/1000000,0)
		response['riverflood_forecast_high_area']=round(temp.get(4, 0)/1000000,0)
		response['riverflood_forecast_veryhigh_area']=round(temp.get(5, 0)/1000000,0)
		response['riverflood_forecast_extreme_area']=round(temp.get(6, 0)/1000000,0)
		response['total_riverflood_forecast_area']=response['riverflood_forecast_verylow_area'] + response['riverflood_forecast_low_area'] + response['riverflood_forecast_med_area'] + response['riverflood_forecast_high_area'] + response['riverflood_forecast_veryhigh_area'] + response['riverflood_forecast_extreme_area']

		temp = dict([(c['basinmember__basins__riskstate'], c['houseatrisk']) for c in counts])
		response['riverflood_forecast_verylow_buildings']=round(temp.get(1, 0) or 0,0)
		response['riverflood_forecast_low_buildings']=round(temp.get(2, 0) or 0,0)
		response['riverflood_forecast_med_buildings']=round(temp.get(3, 0) or 0,0)
		response['riverflood_forecast_high_buildings']=round(temp.get(4, 0) or 0,0)
		response['riverflood_forecast_veryhigh_buildings']=round(temp.get(5, 0) or 0,0)
		response['riverflood_forecast_extreme_buildings']=round(temp.get(6, 0) or 0,0)
		response['total_riverflood_forecast_buildings']=response['riverflood_forecast_verylow_buildings'] + response['riverflood_forecast_low_buildings'] + response['riverflood_forecast_med_buildings'] + response['riverflood_forecast_high_buildings'] + response['riverflood_forecast_veryhigh_buildings'] + response['riverflood_forecast_extreme_buildings']

	# flood risk and riverflood forecast matrix
	if include_section('riverflood_forecast_risk_pop', includes, excludes):
		px = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='riverflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY))

		if flag=='entireAfg':
			# px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
			#     select={
			#         'pop' : 'SUM(fldarea_population)',
			#     	'building' : 'SUM(area_buildings)'
			#     }).values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
			px = px.\
				annotate(counter=Count('ogc_fid')).\
				annotate(pop=Sum('fldarea_population')).\
				annotate(building=Sum('area_buildings')).\
				values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		elif flag=='currentProvince':
			if len(str(code)) > 2:
				ff0001 =  "dist_code  = '"+str(code)+"'"
			else :
				if len(str(code))==1:
					ff0001 =  "left(cast(dist_code as text),1)  = '"+str(code)+"'"
				else:
					ff0001 =  "left(cast(dist_code as text),2)  = '"+str(code)+"'"
			px = px.\
				annotate(counter=Count('ogc_fid')).\
				annotate(pop=Sum('fldarea_population')).\
				annotate(building=Sum('area_buildings')).\
				extra(
					where={
						ff0001
					}).\
				values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		elif flag=='drawArea':
			px = px.\
				annotate(counter=Count('ogc_fid')).\
				annotate(pop=RawSQL_nogroupby('SUM(  \
							case \
								when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then fldarea_population \
								else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* fldarea_population end \
					)',())).\
				annotate(building=RawSQL_nogroupby('SUM(  \
							case \
								when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then fldarea_population \
								else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* fldarea_population end \
					)',())).\
				extra(
					where = {
						'ST_Intersects(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
					}).\
				values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		else:
			px = px.\
				annotate(counter=Count('ogc_fid')).\
				annotate(pop=Sum('fldarea_population')).\
				annotate(building=Sum('area_buildings')).\
				extra(
					where = {
						'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
					}).\
				values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')

		response['px'] = list(px)
		# response['px_sql'] = str(px.query)
		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 1 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_verylow_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_verylow_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_verylow_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_verylow_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_verylow_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_verylow_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 2 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_low_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_low_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_low_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_low_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_low_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_low_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 3 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_med_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_med_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_med_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_med_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_med_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_med_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 4 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_high_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_high_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_high_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_high_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_high_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_high_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 5 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_veryhigh_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_veryhigh_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_veryhigh_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_veryhigh_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_veryhigh_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_veryhigh_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 6 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_extreme_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_extreme_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_extreme_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_extreme_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_extreme_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_extreme_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

	# Flash Flood Forecasted
	if include_section('flashflood_forecast_pop', includes, excludes):
		# AfgFldzonea100KRiskLandcoverPop.objects.all().select_related("basinmembers").values_list("agg_simplified_description","basinmember__basins__riskstate")
		counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY)), filterLock, 'basinmember__basins__riskstate', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, 'afg_fldzonea_100k_risk_landcover_pop')
		temp = dict([(c['basinmember__basins__riskstate'], c['count']) for c in counts])

		response['flashflood_forecast_verylow_pop']=round(temp.get(1, 0) or 0,0)
		response['flashflood_forecast_low_pop']=round(temp.get(2, 0) or 0,0)
		response['flashflood_forecast_med_pop']=round(temp.get(3, 0) or 0,0)
		response['flashflood_forecast_high_pop']=round(temp.get(4, 0) or 0,0)
		response['flashflood_forecast_veryhigh_pop']=round(temp.get(5, 0) or 0,0)
		response['flashflood_forecast_extreme_pop']=round(temp.get(6, 0) or 0,0)
		response['total_flashflood_forecast_pop']=response['flashflood_forecast_verylow_pop'] + response['flashflood_forecast_low_pop'] + response['flashflood_forecast_med_pop'] + response['flashflood_forecast_high_pop'] + response['flashflood_forecast_veryhigh_pop'] + response['flashflood_forecast_extreme_pop']

		temp = dict([(c['basinmember__basins__riskstate'], c['houseatrisk']) for c in counts])
		response['flashflood_forecast_verylow_buildings']=round(temp.get(1, 0) or 0,0)
		response['flashflood_forecast_low_buildings']=round(temp.get(2, 0) or 0,0)
		response['flashflood_forecast_med_buildings']=round(temp.get(3, 0) or 0,0)
		response['flashflood_forecast_high_buildings']=round(temp.get(4, 0) or 0,0)
		response['flashflood_forecast_veryhigh_buildings']=round(temp.get(5, 0) or 0,0)
		response['flashflood_forecast_extreme_buildings']=round(temp.get(6, 0) or 0,0)
		response['total_flashflood_forecast_buildings']=response['flashflood_forecast_verylow_buildings'] + response['flashflood_forecast_low_buildings'] + response['flashflood_forecast_med_buildings'] + response['flashflood_forecast_high_buildings'] + response['flashflood_forecast_veryhigh_buildings'] + response['flashflood_forecast_extreme_buildings']

		temp = dict([(c['basinmember__basins__riskstate'], c['areaatrisk']) for c in counts])
		response['flashflood_forecast_verylow_area']=round(temp.get(1, 0) or 0/1000000,0)
		response['flashflood_forecast_low_area']=round(temp.get(2, 0) or 0/1000000,0)
		response['flashflood_forecast_med_area']=round(temp.get(3, 0) or 0/1000000,0)
		response['flashflood_forecast_high_area']=round(temp.get(4, 0) or 0/1000000,0)
		response['flashflood_forecast_veryhigh_area']=round(temp.get(5, 0) or 0/1000000,0)
		response['flashflood_forecast_extreme_area']=round(temp.get(6, 0) or 0/1000000,0)
		response['total_flashflood_forecast_area']=response['flashflood_forecast_verylow_area'] + response['flashflood_forecast_low_area'] + response['flashflood_forecast_med_area'] + response['flashflood_forecast_high_area'] + response['flashflood_forecast_veryhigh_area'] + response['flashflood_forecast_extreme_area']

		response['total_flood_forecast_pop'] = response['total_riverflood_forecast_pop'] + response['total_flashflood_forecast_pop']
		response['total_flood_forecast_area'] = response['total_riverflood_forecast_area'] + response['total_flashflood_forecast_area']

	# flood risk and flashflood forecast matrix
	if include_section('flashflood_forecast_risk_pop', includes, excludes):
		# px = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY))
		# # px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
		# #     select={
		# #         'pop' : 'SUM(fldarea_population)'
		# #     }).values('basinmember__basins__riskstate','deeperthan', 'pop')
		# if flag=='entireAfg':
		#     # px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
		#     #     select={
		#     #         'pop' : 'SUM(fldarea_population)',
		#     #         'building' : 'SUM(area_buildings)'
		#     #     }).values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		#     px = px.\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(pop=Sum('fldarea_population')).\
		#         annotate(building=Sum('area_buildings')).\
		#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		# elif flag=='currentProvince':
		#     if len(str(code)) > 2:
		#         ff0001 =  "dist_code  = '"+str(code)+"'"
		#     else :
		#         if len(str(code))==1:
		#             ff0001 =  "left(cast(dist_code as text),1)  = '"+str(code)+"'"
		#         else:
		#             ff0001 =  "left(cast(dist_code as text),2)  = '"+str(code)+"'"
		#     px = px.\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(pop=Sum('fldarea_population')).\
		#         annotate(building=Sum('area_buildings')).\
		#         extra(
		#             where={
		#                 ff0001
		#             }).\
		#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		# elif flag=='drawArea':
		#     px = px.\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(pop=RawSQL_nogroupby('SUM(  \
		#                     case \
		#                         when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then fldarea_population \
		#                         else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* fldarea_population end \
		#                 )')).\
		#         annotate(building=RawSQL_nogroupby('SUM(  \
		#                     case \
		#                         when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then area_buildings \
		#                         else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* area_buildings end \
		#                 )',())).\
		#         extra(
		#             where = {
		#                 'ST_Intersects(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
		#             }).\
		#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		# else:
		#     px = px.\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(pop=Sum('fldarea_population')).\
		#         annotate(building=Sum('area_buildings')).\
		#         extra(
		#             where = {
		#                 'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
		#             }).\
		#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')

		px = none_to_zero(getFlashFloodForecastRisk(filterLock, flag, code, targetRisk, YEAR, MONTH, DAY))

		for row in px:
			if (row['basinmember__basins__riskstate'] in LIKELIHOOD_INDEX) and (row['deeperthan'] in DEPTH_TYPES_INVERSE):
				likelihood_type = LIKELIHOOD_INDEX[row['basinmember__basins__riskstate']]
				depth_type = DEPTH_TYPES_INVERSE[row['deeperthan']]
				response['flashflood_forecast_%s_risk_%s_pop'%(likelihood_type, depth_type)]=round(row['deeperthan'] or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 1 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_verylow_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_verylow_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_verylow_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_verylow_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_verylow_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_verylow_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 2 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_low_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_low_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_low_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_low_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_low_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_low_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 3 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_med_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_med_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_med_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_med_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_med_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_med_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 4 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_high_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_high_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_high_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_high_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_high_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_high_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 5 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_veryhigh_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_veryhigh_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_veryhigh_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_veryhigh_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_veryhigh_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_veryhigh_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 6 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_extreme_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_extreme_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_extreme_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_extreme_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_extreme_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_extreme_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

	return response

def getSettlementAtFloodRisk(filterLock, flag, code):
	response = {}
	targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all()
	targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')

	# Number settlement at risk of flood
	if flag=='drawArea':
		countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			select={
				'numbersettlementsatrisk': 'count(distinct vuid)'},
			where = {'st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*fldarea_sqm > 1 and ST_Intersects(wkb_geometry, '+filterLock+')'}).values('numbersettlementsatrisk')
	elif flag=='entireAfg':
		countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			select={
				'numbersettlementsatrisk': 'count(distinct vuid)'}).values('numbersettlementsatrisk')
	elif flag=='currentProvince':
		if len(str(code)) > 2:
			ff0001 =  "dist_code  = '"+str(code)+"'"
		else :
			ff0001 =  "prov_code  = '"+str(code)+"'"
		countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			select={
				'numbersettlementsatrisk': 'count(distinct vuid)'},
			where = {ff0001}).values('numbersettlementsatrisk')
	elif flag=='currentBasin':
		countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			select={
				'numbersettlementsatrisk': 'count(distinct vuid)'},
			where = {"vuid = '"+str(code)+"'"}).values('numbersettlementsatrisk')
	else:
		countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			select={
				'numbersettlementsatrisk': 'count(distinct vuid)'},
			where = {'ST_Within(wkb_geometry, '+filterLock+')'}).values('numbersettlementsatrisk')

	return round((countsBase[0]['numbersettlementsatrisk'] or 0),0)

# from geodb.views

def getFloodInfoVillages(request):
	template = './floodInfo.html'
	village = request.GET["v"]
	currentdate = datetime.datetime.utcnow()
	year = currentdate.strftime("%Y")
	month = currentdate.strftime("%m")
	day = currentdate.strftime("%d")

	context_dict = getCommonVillageData(village)

	targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all().filter(vuid=village)
	targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')

	# riverflood
	currRF = targetRisk.select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='riverflood',basinmember__basins__datadate='%s-%s-%s' %(year,month,day))
	currRF = currRF.values('basinmember__basins__riskstate').annotate(pop=Sum('fldarea_population'), area=Sum('fldarea_sqm')).values('basinmember__basins__riskstate','pop', 'area')
	temp = dict([(c['basinmember__basins__riskstate'], c['pop']) for c in currRF])
	context_dict['riverflood_forecast_verylow_pop']=round(temp.get(1, 0) or 0,0)
	context_dict['riverflood_forecast_low_pop']=round(temp.get(2, 0) or 0,0)
	context_dict['riverflood_forecast_med_pop']=round(temp.get(3, 0) or 0,0)
	context_dict['riverflood_forecast_high_pop']=round(temp.get(4, 0) or 0,0)
	context_dict['riverflood_forecast_veryhigh_pop']=round(temp.get(5, 0) or 0,0)
	context_dict['riverflood_forecast_extreme_pop']=round(temp.get(6, 0) or 0,0)

	currFF = targetRisk.select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(year,month,day))
	currFF = currFF.values('basinmember__basins__riskstate').annotate(pop=Sum('fldarea_population'), area=Sum('fldarea_sqm')).values('basinmember__basins__riskstate','pop', 'area')
	temp = dict([(c['basinmember__basins__riskstate'], c['pop']) for c in currFF])
	context_dict['flashflood_forecast_verylow_pop']=round(temp.get(1, 0) or 0,0)
	context_dict['flashflood_forecast_low_pop']=round(temp.get(2, 0) or 0,0)
	context_dict['flashflood_forecast_med_pop']=round(temp.get(3, 0) or 0,0)
	context_dict['flashflood_forecast_high_pop']=round(temp.get(4, 0) or 0,0)
	context_dict['flashflood_forecast_veryhigh_pop']=round(temp.get(5, 0) or 0,0)
	context_dict['flashflood_forecast_extreme_pop']=round(temp.get(6, 0) or 0,0)

	floodRisk = targetRisk.values('deeperthan').annotate(pop=Sum('fldarea_population'), area=Sum('fldarea_sqm')).values('deeperthan','pop', 'area')
	temp = dict([(c['deeperthan'], c['pop']) for c in floodRisk])
	context_dict['high_risk_population']=round(temp.get('271 cm', 0) or 0,0)
	context_dict['med_risk_population']=round(temp.get('121 cm', 0) or 0, 0)
	context_dict['low_risk_population']=round(temp.get('029 cm', 0) or 0,0)
	context_dict['total_risk_population']=context_dict['high_risk_population']+context_dict['med_risk_population']+context_dict['low_risk_population']
	temp = dict([(c['deeperthan'], c['area']) for c in floodRisk])
	context_dict['high_risk_area']=round((temp.get('271 cm', 0) or 0)/1000000,1)
	context_dict['med_risk_area']=round((temp.get('121 cm', 0) or 0)/1000000,1)
	context_dict['low_risk_area']=round((temp.get('029 cm', 0) or 0)/1000000,1)


	floodRiskLC = targetRiskIncludeWater.values('agg_simplified_description').annotate(pop=Sum('fldarea_population'), area=Sum('fldarea_sqm')).values('agg_simplified_description','pop', 'area')
	temp = dict([(c['agg_simplified_description'], c['pop']) for c in floodRiskLC])
	context_dict['water_body_pop_risk']=round(temp.get('Water body and Marshland', 0) or 0,0)
	context_dict['barren_land_pop_risk']=round(temp.get('Barren land', 0) or 0,0)
	context_dict['built_up_pop_risk']=round(temp.get('Build Up', 0) or 0,0)
	context_dict['fruit_trees_pop_risk']=round(temp.get('Fruit Trees', 0) or 0,0)
	context_dict['irrigated_agricultural_land_pop_risk']=round(temp.get('Irrigated Agricultural Land', 0) or 0,0)
	context_dict['permanent_snow_pop_risk']=round(temp.get('Snow', 0) or 0,0)
	context_dict['rainfed_agricultural_land_pop_risk']=round(temp.get('Rainfed', 0) or 0,0)
	context_dict['rangeland_pop_risk']=round(temp.get('Rangeland', 0) or 0,0)
	context_dict['sandcover_pop_risk']=round(temp.get('Sand Covered Areas', 0) or 0,0)
	context_dict['vineyards_pop_risk']=round(temp.get('Vineyards', 0) or 0,0)
	context_dict['forest_pop_risk']=round(temp.get('Forest & Shrub', 0) or 0,0)
	context_dict['sand_dunes_pop_risk']=round(temp.get('Sand Dunes', 0) or 0,0)
	temp = dict([(c['agg_simplified_description'], c['area']) for c in floodRiskLC])
	context_dict['water_body_area_risk']=round(temp.get('Water body and Marshland', 0)/1000000,1)
	context_dict['barren_land_area_risk']=round(temp.get('Barren land', 0)/1000000,1)
	context_dict['built_up_area_risk']=round(temp.get('Build Up', 0)/1000000,1)
	context_dict['fruit_trees_area_risk']=round(temp.get('Fruit Trees', 0)/1000000,1)
	context_dict['irrigated_agricultural_land_area_risk']=round(temp.get('Irrigated Agricultural Land', 0)/1000000,1)
	context_dict['permanent_snow_area_risk']=round(temp.get('Snow', 0)/1000000,1)
	context_dict['rainfed_agricultural_land_area_risk']=round(temp.get('Rainfed', 0)/1000000,1)
	context_dict['rangeland_area_risk']=round(temp.get('Rangeland', 0)/1000000,1)
	context_dict['sandcover_area_risk']=round(temp.get('Sand Covered Areas', 0)/1000000,1)
	context_dict['vineyards_area_risk']=round(temp.get('Vineyards', 0)/1000000,1)
	context_dict['forest_area_risk']=round(temp.get('Forest & Shrub', 0)/1000000,1)
	context_dict['sand_dunes_area_risk']=round(temp.get('Sand Dunes', 0),0)

	data = []
	data.append(['floodtype',_('Very Low'), _('Low'), _('Moderate'), _('High'), _('Very High'), _('Extreme'), _('Population at flood risk'), _('Population')])
	data.append(['',0,0,0,0,0,0,context_dict['total_risk_population'], round(context_dict['vuid_population'] or 0, 0)])
	data.append([_('River Flood'),context_dict['riverflood_forecast_verylow_pop'], context_dict['riverflood_forecast_low_pop'], context_dict['riverflood_forecast_med_pop'], context_dict['riverflood_forecast_high_pop'], context_dict['riverflood_forecast_veryhigh_pop'], context_dict['riverflood_forecast_extreme_pop'], context_dict['total_risk_population'], round(context_dict['vuid_population'] or 0, 0)])
	data.append([_('Flash Flood'),context_dict['flashflood_forecast_verylow_pop'], context_dict['flashflood_forecast_low_pop'], context_dict['flashflood_forecast_med_pop'], context_dict['flashflood_forecast_high_pop'], context_dict['flashflood_forecast_veryhigh_pop'], context_dict['flashflood_forecast_extreme_pop'], context_dict['total_risk_population'], round(context_dict['vuid_population'] or 0, 0)])
	data.append(['',0,0,0,0,0,0,context_dict['total_risk_population'], round(context_dict['vuid_population'] or 0, 0)])
	context_dict['combo_pop_chart'] = gchart.ComboChart(SimpleDataSource(data=data), html_id="combo_chart", options={'vAxis': {'title': _('Number of population')},'legend': {'position': 'top', 'maxLines':2}, 'colors': ['#b9c246', '#e49307', '#e49307', '#e7711b', '#e2431e', '#d3362d', 'red', 'green' ], 'title': _("Flood Prediction Exposure"), 'seriesType': 'bars', 'series': {6: {'type': 'area', 'lineDashStyle': [2, 2, 20, 2, 20, 2]}, 7: {'type': 'area', 'lineDashStyle':[10, 2]}}, 'isStacked': 'false'})

	dataFLRiskPop = []
	dataFLRiskPop.append([_('Flood Risk'),'Population'])
	dataFLRiskPop.append([_('Low'),context_dict['low_risk_population']])
	dataFLRiskPop.append([_('Moderate'),context_dict['med_risk_population']])
	dataFLRiskPop.append([_('High'),context_dict['high_risk_population']])
	context_dict['floodrisk_pop_chart'] = gchart.PieChart(SimpleDataSource(data=dataFLRiskPop), html_id="pie_chart1", options={'slices': {0:{'color': 'blue'},1:{'color': 'orange'},2:{'color': 'red'}}, 'title': _("Flood Risk Population Exposure"), 'width': 225,'height': 225, 'pieSliceText': _('percentage'),'legend': {'position': 'top', 'maxLines':3}})

	dataFLRiskPop = []
	dataFLRiskPop.append([_('Lancover Type'),'Population'])
	dataFLRiskPop.append([_('water body'),context_dict['water_body_pop_risk']])
	dataFLRiskPop.append([_('barren land'),context_dict['barren_land_pop_risk']])
	dataFLRiskPop.append([_('built up'),context_dict['built_up_pop_risk']])
	dataFLRiskPop.append([_('fruit trees'),context_dict['fruit_trees_pop_risk']])
	dataFLRiskPop.append([_('irrigated agricultural'),context_dict['irrigated_agricultural_land_pop_risk']])
	dataFLRiskPop.append([_('permanent snow'),context_dict['permanent_snow_pop_risk']])
	dataFLRiskPop.append([_('rainfeld agricultural'),context_dict['rainfed_agricultural_land_pop_risk']])
	dataFLRiskPop.append([_('rangeland'),context_dict['rangeland_pop_risk']])
	dataFLRiskPop.append([_('sandcover'),context_dict['sandcover_pop_risk']])
	dataFLRiskPop.append([_('vineyards'),context_dict['vineyards_pop_risk']])
	dataFLRiskPop.append([_('forest'),context_dict['forest_pop_risk']])
	dataFLRiskPop.append([_('sand dunes'),context_dict['sand_dunes_pop_risk']])
	context_dict['floodriskLC_pop_chart'] = gchart.PieChart(SimpleDataSource(data=dataFLRiskPop), html_id="pie_chart2", options={'title': _("Flood Risk Population Exposure by Landcover type"), 'width': 225,'height': 225, 'pieSliceText': _('percentage'),'legend': {'position': 'top', 'maxLines':3}})

	dataFLRiskArea = []
	dataFLRiskArea.append([_('Flood Risk'),'Area'])
	dataFLRiskArea.append([_('Low'),context_dict['low_risk_area']])
	dataFLRiskArea.append([_('Moderate'),context_dict['med_risk_area']])
	dataFLRiskArea.append([_('High'),context_dict['high_risk_area']])
	print 'dataFLRiskArea', dataFLRiskArea
	context_dict['floodrisk_area_chart'] = gchart.PieChart(SimpleDataSource(data=dataFLRiskArea), html_id="pie_chart3", options={'slices': {0:{'color': 'blue'},1:{'color': 'orange'},2:{'color': 'red'}},'title': _("Flood Risk Area Exposure"), 'width': 225,'height': 225, 'pieSliceText': _('percentage'),'legend': {'position': 'top', 'maxLines':3}})

	dataFLRiskPop = []
	dataFLRiskPop.append([_('Lancover Type'),'Area'])
	dataFLRiskPop.append([_('water body'),context_dict['water_body_area_risk']])
	dataFLRiskPop.append([_('barren land'),context_dict['barren_land_area_risk']])
	dataFLRiskPop.append([_('built up'),context_dict['built_up_area_risk']])
	dataFLRiskPop.append([_('fruit trees'),context_dict['fruit_trees_area_risk']])
	dataFLRiskPop.append([_('irrigated agricultural'),context_dict['irrigated_agricultural_land_area_risk']])
	dataFLRiskPop.append([_('permanent snow'),context_dict['permanent_snow_area_risk']])
	dataFLRiskPop.append([_('rainfeld agricultural'),context_dict['rainfed_agricultural_land_area_risk']])
	dataFLRiskPop.append([_('rangeland'),context_dict['rangeland_area_risk']])
	dataFLRiskPop.append([_('sandcover'),context_dict['sandcover_area_risk']])
	dataFLRiskPop.append([_('vineyards'),context_dict['vineyards_area_risk']])
	dataFLRiskPop.append([_('forest'),context_dict['forest_area_risk']])
	dataFLRiskPop.append([_('sand dunes'),context_dict['sand_dunes_pop_risk']])
	context_dict['floodriskLC_area_chart'] = gchart.PieChart(SimpleDataSource(data=dataFLRiskPop), html_id="pie_chart4", options={'title': _("Flood Risk Area Exposure by Landcover type"), 'width': 225,'height': 225, 'pieSliceText': _('percentage'),'legend': {'position': 'top', 'maxLines':3}})

	context_dict.pop('position')
	print context_dict
	return render_to_response(template,
								  RequestContext(request, context_dict))

def getGlofasChart(request):

	date = request.GET['date']
	lat = float(request.GET['lat'])
	lon = float(request.GET['lon'])

	filename = "%s%s00.nc" % (getattr(settings, 'GLOFAS_NC_FILES'),date)
	nc = Dataset(filename, 'r', Format='NETCDF4')

	# get coordinates variables
	lats = nc.variables['lat'][:]
	lons = nc.variables['lon'][:]
	times= nc.variables['time'][:]

	lat_idx = np.where(lats==lat)[0]
	lon_idx = np.where(lons==lon)[0]

	coord_idx = list(set(lat_idx) & set(lon_idx))[0]

	d = np.array(nc.variables['dis'])

	rl2= nc.variables['rl2'][:]
	rl5= nc.variables['rl5'][:]
	rl20= nc.variables['rl20'][:]

	units = nc.variables['time'].units

	dates = num2date(times[:], units=units, calendar='365_day')
	date_arr = []

	median = []
	mean75 = []
	mean25 = []
	rl2_arr = []
	rl5_arr = []
	rl20_arr = []
	maximum = []

	date_number = []
	date_number_label = []
	month_name = []

	first_date_even = False

	for i in dates:
		date_number.append(i.day)
		month_name.append(i.month)

	if date_number[0] % 2 == 0:
		first_date_even = True
	for i in dates:
		if first_date_even:
			if i.day % 2 == 0:
				date_number_label.append(i.day)
		else:
			if i.day % 2 != 0:
				date_number_label.append(i.day)


	for i in range(len(date_number)):
		date_arr.append(i)
		# get median line
		median.append(np.mean(list(d[i,:,coord_idx])))
		maximum.append(np.max(list(d[i,:,coord_idx])))
		mean75.append(np.percentile(list(d[i,:,coord_idx]),75))
		mean25.append(np.percentile(list(d[i,:,coord_idx]),25))
		rl2_arr.append(rl2[coord_idx])
		rl5_arr.append(rl5[coord_idx])
		rl20_arr.append(rl20[coord_idx])

	fig=Figure(dpi=120)

	plt=fig.add_subplot(111)

	plt.fill_between(date_arr, rl2_arr, rl5_arr, color='#fff68f', alpha=1, label="2 years return period")
	plt.fill_between(date_arr, rl5_arr, rl20_arr, color='#ffaeb9', alpha=1, label="5 years return period")
	plt.fill_between(date_arr, rl20_arr, np.max(maximum)+100, color='#ffbbff', alpha=1, label="20 years return period")


	plt.plot(date_arr, median, c='black', alpha=1, linestyle='solid', label="EPS mean")
	plt.plot(date_arr, mean75, color='black', alpha=1, linestyle='dashed', label="25% - 75%")
	plt.plot(date_arr, mean25, color='black', alpha=1, linestyle='dashed')

	for i in range(51):
		plt.fill_between(date_arr, median, list(d[:,i,coord_idx]), color='#178bff', alpha=0.25)

	# print 'rl 2  ',rl2[coord_idx]
	# print 'rl 5  ',rl5[coord_idx]
	# print 'rl 20  ',rl20[coord_idx]



	plt.margins(x=0,y=0,tight=True)

	# plt.xticks(date_arr, date_number, rotation=45)
	major_ticks = np.arange(min(date_number)-1, max(date_number), 2)
	minor_ticks = np.arange(min(date_number)-1, max(date_number), 1)

	plt.set_xticks(major_ticks)
	plt.set_xticks(minor_ticks, minor=True)
	plt.set_xticklabels(date_number_label)
	plt.set_ylabel('discharge (m$^3$/s)')

	if max(month_name)==min(month_name):
		plt.set_xlabel('Period of '+get_month_name(max(month_name)))
	else:
		plt.set_xlabel('Period of '+get_month_name(min(month_name))+' - '+get_month_name(max(month_name)))

	plt.grid(which='both')
	plt.grid(True, 'major', 'y', ls='--', lw=.5, c='k', alpha=.2)

	plt.grid(True, 'major', 'x', ls='--', lw=.5, c='k', alpha=.2)
	plt.grid(True, 'minor', 'x', lw=.3, c='k', alpha=.2)

	leg = plt.legend(prop={'size':6})
	leg.get_frame().set_alpha(0)

	canvas=FigureCanvas(fig)

	response=HttpResponse(content_type='image/jpeg')
	canvas.print_png(response)
	return response

def getGlofasPointsJSON(request):
	date = request.GET['date']
	cursor = connections['geodb'].cursor()
	cursor.execute("\
		SELECT row_to_json(fc) \
 FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features \
 FROM (SELECT 'Feature' As type \
	, ST_AsGeoJSON(ST_SetSRID(ST_MakePoint(lg.lon, lg.lat),4326))::json As geometry \
	, row_to_json(lp) As properties \
   FROM glofasintegrated As lg \
		 INNER JOIN (select distinct \
		id, round(lon, 2) as lon, \
		round(lat, 2) as lat, \
		rl2, \
		rl5, \
		rl20, \
		rl2_dis_percent, \
		rl2_avg_dis_percent, \
		rl5_dis_percent, \
		rl5_avg_dis_percent, \
		rl20_dis_percent, \
		rl20_avg_dis_percent, \
		ST_SetSRID(ST_MakePoint(lon, lat),4326) as geom \
		from glofasintegrated where datadate = '"+date+"' and rl5_dis_percent > 25) As lp \
	   ON lg.id = lp.id  ) As f )  As fc;\
	")
	currPoints = cursor.fetchone()
	cursor.close()
	if currPoints[0]["features"] is None:
		currPoints[0]["features"] = []
	return HttpResponse(json.dumps(currPoints[0]), content_type='application/json')

def calculate_glofas_params(date):
	date_arr = date.split('-')
	filename = getattr(settings, 'GLOFAS_NC_FILES')+date_arr[0]+date_arr[1]+date_arr[2]+"00.nc"
	# print Glofasintegrated.objects.latest('datadate').date

	nc = Dataset(filename, 'r', Format='NETCDF4')

	# get coordinates variables
	lats = nc.variables['lat'][:]
	lons = nc.variables['lon'][:]

	rl2= nc.variables['rl2'][:]
	rl5= nc.variables['rl5'][:]
	rl20= nc.variables['rl20'][:]
	times = nc.variables['time'][:]
	essemble = nc.variables['ensemble'][:]

	# convert date, how to store date only strip away time?
	# print "Converting Dates"
	units = nc.variables['time'].units
	dates = num2date (times[:], units=units, calendar='365_day')

	d = np.array(nc.variables['dis'])
	# header = ['Latitude', 'Longitude', 'rl2', 'rl5', 'rl20', 'rl2_dis_percent', 'rl2_avg_dis_percent', 'rl5_dis_percent', 'rl5_avg_dis_percent', 'rl20_dis_percent', 'rl20_avg_dis_percent']
	times_index=[]
	for i,j in enumerate(times):
		times_index.append(i)

	coord_index = 0
	refactor = getRefactorData()

	for lat, lon, rl2, rl5, rl20 in zip(lats, lons, rl2, rl5, rl20):

		try:
			# print refactor[str(lat)][str(lon)]
			rl2_temp = rl2*float(refactor[str(lat)][str(lon)]['rl2_factor'])
			rl5_temp = rl5*float(refactor[str(lat)][str(lon)]['rl5_factor'])
			rl20_temp = rl20*float(refactor[str(lat)][str(lon)]['rl20_factor'])
		except:
			rl2_temp = rl2
			rl5_temp = rl5
			rl20_temp = rl20

		rl2 = rl2_temp
		rl5 = rl5_temp
		rl20 = rl20_temp

		data_in = []
		data_in.append(lat)
		data_in.append(lon)
		data_in.append(rl2)
		data_in.append(rl5)
		data_in.append(rl20)

		rl2_dis_percent = []
		rl5_dis_percent = []
		rl20_dis_percent = []

		rl2_avg_dis = []
		rl5_avg_dis = []
		rl20_avg_dis = []

		for i in times_index:
			data = d[i,:,coord_index]

			dis_data = []
			for l in data:
				dis_data.append(l)

			# dis_avg = sum(dis_data)/float(51)
			dis_avg = np.median(dis_data)

			count = sum(1 for x in data if x>rl2)
			percent_rl2 = round(float(count)/float(51)*100)
			rl2_avg_dis.append(round(float(dis_avg)/float(rl2)*100))
			rl2_dis_percent.append(percent_rl2)

			count = sum(1 for x in data if x>rl5)
			percent_rl5 = round(float(count)/float(51)*100)
			rl5_avg_dis.append(round(float(dis_avg)/float(rl5)*100))
			rl5_dis_percent.append(percent_rl5)

			count = sum(1 for x in data if x>rl20)
			percent_rl20 = round(float(count)/float(51)*100)
			rl20_avg_dis.append(round(float(dis_avg)/float(rl20)*100))
			rl20_dis_percent.append(percent_rl20)
			if i>=19:
				break

		# print rl2_avg_dis
		data_in.append(max(rl2_dis_percent))
		temp_avg_dis=[]
		for index, item in enumerate(rl2_dis_percent):
			if item == max(rl2_dis_percent):
				# print index, item
				temp_avg_dis.append(rl2_avg_dis[index])
		data_in.append(max(temp_avg_dis))
		rl2_avg_dis_percent = max(temp_avg_dis)

		data_in.append(max(rl5_dis_percent))
		temp_avg_dis=[]
		for index, item in enumerate(rl5_dis_percent):
			if item == max(rl5_dis_percent):
				# print index, item
				temp_avg_dis.append(rl5_avg_dis[index])
		data_in.append(max(temp_avg_dis))
		rl5_avg_dis_percent = max(temp_avg_dis)

		data_in.append(max(rl20_dis_percent))
		temp_avg_dis=[]
		for index, item in enumerate(rl20_dis_percent):
			if item == max(rl20_dis_percent):
				# print index, item
				temp_avg_dis.append(rl20_avg_dis[index])
		data_in.append(max(temp_avg_dis))
		rl20_avg_dis_percent = max(temp_avg_dis)

		if coord_index>2035 and max(rl2_dis_percent)>=25:
			pnt = Point(round(float(lon),2), round(float(lat),2), srid=4326)
			checkdata = AfgBasinLvl4GlofasPoint.objects.filter(geom__intersects=pnt)
			for z in checkdata:
				p = Glofasintegrated(basin_id=z.value, datadate=date, lon=lon, lat=lat, rl2=rl2, rl5=rl5, rl20=rl20, rl2_dis_percent=max(rl2_dis_percent), rl2_avg_dis_percent=rl2_avg_dis_percent, rl5_dis_percent=max(rl5_dis_percent), rl5_avg_dis_percent=rl5_avg_dis_percent, rl20_dis_percent=max(rl20_dis_percent), rl20_avg_dis_percent=rl20_avg_dis_percent)
				p.save()
				# print coord_index, z.value

		coord_index = coord_index+1
		# print data_in

	# print Glofasintegrated.objects.filter(datadate=date).count()
	if Glofasintegrated.objects.filter(datadate=date).count() == 0 :
		Glofasintegrated(datadate=date).save()

	nc.close()
	# GS_TMP_DIR = getattr(settings, 'GS_TMP_DIR', '/tmp')

def runGlofasDownloader():
	delta = datetime.timedelta(days=1)
	try:
		d = Glofasintegrated.objects.latest('datadate').datadate + delta
	except Glofasintegrated.DoesNotExist:
		d = datetime.date.today() - datetime.timedelta(days=5)
	end_date = datetime.date.today() - delta

	while d <= end_date:
		print d.strftime("%Y-%m-%d")
		get_nc_file_from_ftp(d.strftime("%Y-%m-%d"))
		calculate_glofas_params(d.strftime("%Y-%m-%d"))
		d += delta

# from geodb.geoapi

def getRiskExecuteExternal(filterLock, flag, code, yy=None, mm=None, dd=None, rf_type=None, bring=None, init_response=dict_ext()):

	response_tree = dict_ext(init_response)

	date_params = yy and mm and dd
	YEAR, MONTH, DAY = yy, mm, dd if date_params else datetime.datetime.utcnow().strftime("%Y %m %d").split()
	
	targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all()
	targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')
	# targetBase = AfgLndcrva.objects.all()
	# targetAvalanche = AfgAvsa.objects.all()
	# response = response_base

	if flag not in ['entireAfg','currentProvince'] or date_params:

		# #Avalanche Risk
		# counts =  getRiskNumber(targetAvalanche, filterLock, 'avalanche_cat', 'avalanche_pop', 'sum_area_sqm', 'area_buildings', flag, code, None)
		# # pop at risk level
		# temp = dict([(c['avalanche_cat'], c['count']) for c in counts])
		# response['high_ava_population']=round(temp.get('High', 0) or 0,0)
		# response['med_ava_population']=round(temp.get('Moderate', 0) or 0,0)
		# response['low_ava_population']=0
		# response['total_ava_population']=response['high_ava_population']+response['med_ava_population']+response['low_ava_population']

		# # area at risk level
		# temp = dict([(c['avalanche_cat'], c['areaatrisk']) for c in counts])
		# response['high_ava_area']=round((temp.get('High', 0) or 0)/1000000,1)
		# response['med_ava_area']=round((temp.get('Moderate', 0) or 0)/1000000,1)
		# response['low_ava_area']=0    
		# response['total_ava_area']=round(response['high_ava_area']+response['med_ava_area']+response['low_ava_area'],2) 

		# # Number of Building on Avalanche Risk
		# temp = dict([(c['avalanche_cat'], c['houseatrisk']) for c in counts])
		# response['high_ava_buildings']=temp.get('High', 0) or 0
		# response['med_ava_buildings']=temp.get('Moderate', 0) or 0
		# response['total_ava_buildings'] = response['high_ava_buildings']+response['med_ava_buildings']

		# Flood Risk
		counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0), filterLock, 'deeperthan', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, None)
		
		# pop at risk level
		sliced = {c['deeperthan']:c['count'] for c in counts}
		response_tree.path('floodrisk')['pop_depth'] = {k:(sliced.get(v) or 0) for k,v in DEPTH_TYPES.items()}
		response_tree.path('floodrisk')['pop_total'] = sum(response_tree['floodrisk']['pop_depth'].values())
		# temp = dict([(c['deeperthan'], c['count']) for c in counts])
		# response = response_tree['floodrisk']['pop']['table']
		# response['high']=round((temp.get('271 cm', 0) or 0),0)
		# response['med']=round((temp.get('121 cm', 0) or 0), 0)
		# response['low']=round((temp.get('029 cm', 0) or 0),0)
		# response['floodrisk']['pop']['total']=sum(response) 

		# area at risk level
		sliced = {c['deeperthan']:c['areaatrisk'] for c in counts}
		response_tree.path('floodrisk')['area_depth'] = {k:round((sliced.get(v) or 0)/1000000,1) for k,v in DEPTH_TYPES.items()}
		response_tree.path('floodrisk')['area_total'] = sum(response_tree['floodrisk']['area_depth'].values())
		# temp = dict([(c['deeperthan'], c['areaatrisk']) for c in counts])
		# response = response_tree['floodrisk']['area']['table']
		# response['high']=round((temp.get('271 cm', 0) or 0)/1000000,1)
		# response['med']=round((temp.get('121 cm', 0) or 0)/1000000,1)
		# response['low']=round((temp.get('029 cm', 0) or 0)/1000000,1)    
		# response['floodrisk']['area']['total']=sum(response) 

		# buildings at flood risk
		response_tree.path('floodrisk')['building_total'] = sum([c['houseatrisk'] for c in counts if c['deeperthan'] in DEPTH_TYPES_INVERSE])
		# temp = dict([(c['deeperthan'], c['houseatrisk']) for c in counts])
		# response = response_tree['floodrisk']['building']['table']
		# response['total_risk_buildings'] = 0
		# response['total_risk_buildings']+=temp.get('271 cm', 0) or 0
		# response['total_risk_buildings']+=temp.get('121 cm', 0) or 0
		# response['total_risk_buildings']+=temp.get('029 cm', 0) or 0

		counts =  getRiskNumber(targetRiskIncludeWater.exclude(mitigated_pop__gt=0), filterLock, 'agg_simplified_description', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, None)

		# landcover/pop/atrisk
		sliced = {c['agg_simplified_description']:c['count'] for c in counts}
		response_tree.path('floodrisk')['pop_lc'] = {k:sliced.get(v) or 0 for k,v in LANDCOVER_TYPES.items()}
		# temp = dict([(c['agg_simplified_description'], c['count']) for c in counts])
		# for lctype in LANDCOVER_TYPES:
		#     response_tree['floodrisk']['pop']['table'][lctype] = round(temp.get(LANDCOVER_TYPES[lctype], 0) or 0, 0)
		# response = response_tree['floodrisk']['population']['table']
		# response['water_body_pop_risk']=round(temp.get('Water body and Marshland', 0) or 0,0)
		# response['barren_land_pop_risk']=round(temp.get('Barren land', 0) or 0,0)
		# response['built_up_pop_risk']=round(temp.get('Build Up', 0) or 0,0)
		# response['fruit_trees_pop_risk']=round(temp.get('Fruit Trees', 0) or 0,0)
		# response['irrigated_agricultural_land_pop_risk']=round(temp.get('Irrigated Agricultural Land', 0) or 0,0)
		# response['permanent_snow_pop_risk']=round(temp.get('Snow', 0) or 0,0)
		# response['rainfed_agricultural_land_pop_risk']=round(temp.get('Rainfed', 0) or 0,0)
		# response['rangeland_pop_risk']=round(temp.get('Rangeland', 0) or 0,0)
		# response['sandcover_pop_risk']=round(temp.get('Sand Covered Areas', 0) or 0,0)
		# response['vineyards_pop_risk']=round(temp.get('Vineyards', 0) or 0,0)
		# response['forest_pop_risk']=round(temp.get('Forest & Shrub', 0) or 0,0)
		# response['sand_dunes_pop_risk']=round(temp.get('Sand Dunes', 0) or 0,0)

		sliced = {c['agg_simplified_description']:c['areaatrisk'] for c in counts}
		response_tree.path('floodrisk')['area_lc'] = {k:round((sliced.get(v) or 0)/1000000, 1) for k,v in LANDCOVER_TYPES.items()}
		# response_tree['floodrisk']['area']['table'] = {LANDCOVER_TYPES_INVERSE[c['agg_simplified_description']]:round((c['areaatrisk'] or 0)/1000000, 1) for c in counts if c['agg_simplified_description'] in LANDCOVER_TYPES_INVERSE}
		# temp = dict([(c['agg_simplified_description'], c['areaatrisk']) for c in counts])
		# for lctype in LANDCOVER_TYPES:
		#     response_tree['floodrisk']['area']['table'][lctype] = round((temp.get(LANDCOVER_TYPES[lctype]) or 0)/1000000, 1)
		# response = response_tree['floodrisk']['area']['table']
		# response['water_body_area_risk']=round((temp.get('Water body and Marshland', 0) or 0)/1000000,1)
		# response['barren_land_area_risk']=round((temp.get('Barren land', 0) or 0)/1000000,1)
		# response['built_up_area_risk']=round((temp.get('Build Up', 0) or 0)/1000000,1)
		# response['fruit_trees_area_risk']=round((temp.get('Fruit Trees', 0) or 0)/1000000,1)
		# response['irrigated_agricultural_land_area_risk']=round((temp.get('Irrigated Agricultural Land', 0) or 0)/1000000,1)
		# response['permanent_snow_area_risk']=round((temp.get('Snow', 0) or 0)/1000000,1)
		# response['rainfed_agricultural_land_area_risk']=round((temp.get('Rainfed', 0) or 0)/1000000,1)
		# response['rangeland_area_risk']=round((temp.get('Rangeland', 0) or 0)/1000000,1)
		# response['sandcover_area_risk']=round((temp.get('Sand Covered Areas', 0) or 0)/1000000,1)
		# response['vineyards_area_risk']=round((temp.get('Vineyards', 0) or 0)/1000000,1)
		# response['forest_area_risk']=round((temp.get('Forest & Shrub', 0) or 0)/1000000,1)
		# response['sand_dunes_area_risk']=round((temp.get('Sand Dunes', 0) or 0)/1000000,1)

		


		# # landcover all
		# counts =  getRiskNumber(targetBase, filterLock, 'agg_simplified_description', 'area_population', 'area_sqm', 'area_buildings', flag, code, None)
		# temp = dict([(c['agg_simplified_description'], c['count']) for c in counts])
		# response['water_body_pop']=round(temp.get('Water body and Marshland', 0),0)
		# response['barren_land_pop']=round(temp.get('Barren land', 0),0)
		# response['built_up_pop']=round(temp.get('Build Up', 0),0)
		# response['fruit_trees_pop']=round(temp.get('Fruit Trees', 0),0)
		# response['irrigated_agricultural_land_pop']=round(temp.get('Irrigated Agricultural Land', 0),0)
		# response['permanent_snow_pop']=round(temp.get('Snow', 0),0)
		# response['rainfed_agricultural_land_pop']=round(temp.get('Rainfed', 0),0)
		# response['rangeland_pop']=round(temp.get('Rangeland', 0),0)
		# response['sandcover_pop']=round(temp.get('Sand Covered Areas', 0),0)
		# response['vineyards_pop']=round(temp.get('Vineyards', 0),0)
		# response['forest_pop']=round(temp.get('Forest & Shrub', 0),0)
		# response['sand_dunes_pop']=round(temp.get('Sand Dunes', 0),0)

		# temp = dict([(c['agg_simplified_description'], c['areaatrisk']) for c in counts])
		# response['water_body_area']=round(temp.get('Water body and Marshland', 0)/1000000,1)
		# response['barren_land_area']=round(temp.get('Barren land', 0)/1000000,1)
		# response['built_up_area']=round(temp.get('Build Up', 0)/1000000,1)
		# response['fruit_trees_area']=round(temp.get('Fruit Trees', 0)/1000000,1)
		# response['irrigated_agricultural_land_area']=round(temp.get('Irrigated Agricultural Land', 0)/1000000,1)
		# response['permanent_snow_area']=round(temp.get('Snow', 0)/1000000,1)
		# response['rainfed_agricultural_land_area']=round(temp.get('Rainfed', 0)/1000000,1)
		# response['rangeland_area']=round(temp.get('Rangeland', 0)/1000000,1)
		# response['sandcover_area']=round(temp.get('Sand Covered Areas', 0)/1000000,1)
		# response['vineyards_area']=round(temp.get('Vineyards', 0)/1000000,1)
		# response['forest_area']=round(temp.get('Forest & Shrub', 0)/1000000,1)
		# response['sand_dunes_area']=round(temp.get('Sand Dunes', 0)/1000000,1)

		# # total buildings
		# temp = dict([(c['agg_simplified_description'], c['houseatrisk']) for c in counts])
		# response['total_buildings'] = 0
		# response['total_buildings']+=temp.get('Water body and Marshland', 0) or 0
		# response['total_buildings']+=temp.get('Barren land', 0) or 0
		# response['total_buildings']+=temp.get('Build Up', 0) or 0
		# response['total_buildings']+=temp.get('Fruit Trees', 0) or 0
		# response['total_buildings']+=temp.get('Irrigated Agricultural Land', 0) or 0
		# response['total_buildings']+=temp.get('Snow', 0) or 0
		# response['total_buildings']+=temp.get('Rainfed', 0) or 0
		# response['total_buildings']+=temp.get('Rangeland', 0) or 0
		# response['total_buildings']+=temp.get('Sand Covered Areas', 0) or 0
		# response['total_buildings']+=temp.get('Vineyards', 0) or 0
		# response['total_buildings']+=temp.get('Forest & Shrub', 0) or 0
		# response['total_buildings']+=temp.get('Sand Dunes', 0) or 0

		# Number settlement at risk of flood
		if flag=='drawArea':
			countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
				select={
					'numbersettlementsatrisk': 'count(distinct vuid)'}, 
				where = {'st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*fldarea_sqm > 1 and ST_Intersects(wkb_geometry, '+filterLock+')'}).values('numbersettlementsatrisk')
		elif flag=='entireAfg':
			countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
				select={
					'numbersettlementsatrisk': 'count(distinct vuid)'}).values('numbersettlementsatrisk')
		elif flag=='currentProvince':
			if len(str(code)) > 2:
				ff0001 =  "dist_code  = '"+str(code)+"'"
			else :
				ff0001 =  "prov_code  = '"+str(code)+"'"
			countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
				select={
					'numbersettlementsatrisk': 'count(distinct vuid)'}, 
				where = {ff0001}).values('numbersettlementsatrisk')
		elif flag=='currentBasin':
			countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
				select={
					'numbersettlementsatrisk': 'count(distinct vuid)'}, 
				where = {"vuid = '"+str(code)+"'"}).values('numbersettlementsatrisk')    
		else:
			countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
				select={
					'numbersettlementsatrisk': 'count(distinct vuid)'}, 
				where = {'ST_Within(wkb_geometry, '+filterLock+')'}).values('numbersettlementsatrisk')

		# response = response_tree.path('floodrisk','settlement','risk')
		response_tree.path('floodrisk')['settlement_likelihood_total'] = round(countsBase[0]['numbersettlementsatrisk'],0)

		# # number all settlements
		# if flag=='drawArea':
		#     countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#         select={
		#             'numbersettlements': 'count(distinct vuid)'}, 
		#         where = {'st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*area_sqm > 1 and ST_Intersects(wkb_geometry, '+filterLock+')'}).values('numbersettlements')
		# elif flag=='entireAfg':
		#     countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#         select={
		#             'numbersettlements': 'count(distinct vuid)'}).values('numbersettlements')
		# elif flag=='currentProvince':
		#     if len(str(code)) > 2:
		#         ff0001 =  "dist_code  = '"+str(code)+"'"
		#     else :
		#         ff0001 =  "prov_code  = '"+str(code)+"'"
		#     countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#         select={
		#             'numbersettlements': 'count(distinct vuid)'}, 
		#         where = {ff0001}).values('numbersettlements')
		# elif flag=='currentBasin':
		#     countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#         select={
		#             'numbersettlements': 'count(distinct vuid)'}, 
		#         where = {"vuid = '"+str(code)+"'"}).values('numbersettlements')   
		# else:
		#     countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#         select={
		#             'numbersettlements': 'count(distinct vuid)'}, 
		#         where = {'ST_Within(wkb_geometry, '+filterLock+')'}).values('numbersettlements')
		
		# response['settlements'] = round(countsBase[0]['numbersettlements'],0)

		# # All population number
		# if flag=='drawArea':
		#     countsBase = targetBase.extra(
		#         select={
		#             'countbase' : 'SUM(  \
		#                     case \
		#                         when ST_CoveredBy(wkb_geometry,'+filterLock+') then area_population \
		#                         else st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*area_population end \
		#                 )'
		#         },
		#         where = {
		#             'ST_Intersects(wkb_geometry, '+filterLock+')'
		#         }).values('countbase')
		# elif flag=='entireAfg':
		#     countsBase = targetBase.extra(
		#         select={
		#             'countbase' : 'SUM(area_population)'
		#         }).values('countbase')
		# elif flag=='currentProvince':
		#     if len(str(code)) > 2:
		#         ff0001 =  "dist_code  = '"+str(code)+"'"
		#     else :
		#         ff0001 =  "prov_code  = '"+str(code)+"'"
		#     countsBase = targetBase.extra(
		#         select={
		#             'countbase' : 'SUM(area_population)'
		#         },
		#         where = {
		#             ff0001
		#         }).values('countbase')
		# elif flag=='currentBasin':
		#     countsBase = targetBase.extra(
		#         select={
		#             'countbase' : 'SUM(area_population)'
		#         }, 
		#         where = {"vuid = '"+str(code)+"'"}).values('countbase')     
		# else:
		#     countsBase = targetBase.extra(
		#         select={
		#             'countbase' : 'SUM(area_population)'
		#         },
		#         where = {
		#             'ST_Within(wkb_geometry, '+filterLock+')'
		#         }).values('countbase')
					
		# response['Population']=round(countsBase[0]['countbase'],0)

		# if flag=='drawArea':
		#     countsBase = targetBase.extra(
		#         select={
		#             'areabase' : 'SUM(  \
		#                     case \
		#                         when ST_CoveredBy(wkb_geometry,'+filterLock+') then area_sqm \
		#                         else st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*area_sqm end \
		#                 )'
		#         },
		#         where = {
		#             'ST_Intersects(wkb_geometry, '+filterLock+')'
		#         }).values('areabase')
		# elif flag=='entireAfg':
		#     countsBase = targetBase.extra(
		#         select={
		#             'areabase' : 'SUM(area_sqm)'
		#         }).values('areabase')
		# elif flag=='currentProvince':
		#     if len(str(code)) > 2:
		#         ff0001 =  "dist_code  = '"+str(code)+"'"
		#     else :
		#         ff0001 =  "prov_code  = '"+str(code)+"'"
		#     countsBase = targetBase.extra(
		#         select={
		#             'areabase' : 'SUM(area_sqm)'
		#         },
		#         where = {
		#             ff0001
		#         }).values('areabase')
		# elif flag=='currentBasin':
		#     countsBase = targetBase.extra(
		#         select={
		#             'areabase' : 'SUM(area_sqm)'
		#         },
		#         where = {"vuid = '"+str(code)+"'"}).values('areabase')      

		# else:
		#     countsBase = targetBase.extra(
		#         select={
		#             'areabase' : 'SUM(area_sqm)'
		#         },
		#         where = {
		#             'ST_Within(wkb_geometry, '+filterLock+')'
		#         }).values('areabase')

		# response['Area']=round(countsBase[0]['areabase']/1000000,0)

	# else:
	#     if flag=='entireAfg':
	#         px = provincesummary.objects.aggregate(Sum('high_ava_population'),Sum('med_ava_population'),Sum('low_ava_population'),Sum('total_ava_population'),Sum('high_ava_area'),Sum('med_ava_area'),Sum('low_ava_area'),Sum('total_ava_area'), \
	#             Sum('high_risk_population'),Sum('med_risk_population'),Sum('low_risk_population'),Sum('total_risk_population'), Sum('high_risk_area'),Sum('med_risk_area'),Sum('low_risk_area'),Sum('total_risk_area'),  \
	#             Sum('water_body_pop_risk'),Sum('barren_land_pop_risk'),Sum('built_up_pop_risk'),Sum('fruit_trees_pop_risk'),Sum('irrigated_agricultural_land_pop_risk'),Sum('permanent_snow_pop_risk'),Sum('rainfed_agricultural_land_pop_risk'),Sum('rangeland_pop_risk'),Sum('sandcover_pop_risk'),Sum('vineyards_pop_risk'),Sum('forest_pop_risk'), Sum('sand_dunes_pop_risk'), \
	#             Sum('water_body_area_risk'),Sum('barren_land_area_risk'),Sum('built_up_area_risk'),Sum('fruit_trees_area_risk'),Sum('irrigated_agricultural_land_area_risk'),Sum('permanent_snow_area_risk'),Sum('rainfed_agricultural_land_area_risk'),Sum('rangeland_area_risk'),Sum('sandcover_area_risk'),Sum('vineyards_area_risk'),Sum('forest_area_risk'), Sum('sand_dunes_area_risk'), \
	#             Sum('water_body_pop'),Sum('barren_land_pop'),Sum('built_up_pop'),Sum('fruit_trees_pop'),Sum('irrigated_agricultural_land_pop'),Sum('permanent_snow_pop'),Sum('rainfed_agricultural_land_pop'),Sum('rangeland_pop'),Sum('sandcover_pop'),Sum('vineyards_pop'),Sum('forest_pop'), Sum('sand_dunes_pop'), \
	#             Sum('water_body_area'),Sum('barren_land_area'),Sum('built_up_area'),Sum('fruit_trees_area'),Sum('irrigated_agricultural_land_area'),Sum('permanent_snow_area'),Sum('rainfed_agricultural_land_area'),Sum('rangeland_area'),Sum('sandcover_area'),Sum('vineyards_area'),Sum('forest_area'), Sum('sand_dunes_area'), \
	#             Sum('settlements_at_risk'), Sum('settlements'), Sum('Population'), Sum('Area'), Sum('ava_forecast_low_pop'), Sum('ava_forecast_med_pop'), Sum('ava_forecast_high_pop'), Sum('total_ava_forecast_pop'),
	#             Sum('total_buildings'), Sum('total_risk_buildings'), Sum('high_ava_buildings'), Sum('med_ava_buildings'), Sum('total_ava_buildings') )
	#     else:    
	#         if len(str(code)) > 2:
	#             px = districtsummary.objects.filter(district=code).aggregate(Sum('high_ava_population'),Sum('med_ava_population'),Sum('low_ava_population'),Sum('total_ava_population'),Sum('high_ava_area'),Sum('med_ava_area'),Sum('low_ava_area'),Sum('total_ava_area'), \
	#                 Sum('high_risk_population'),Sum('med_risk_population'),Sum('low_risk_population'),Sum('total_risk_population'), Sum('high_risk_area'),Sum('med_risk_area'),Sum('low_risk_area'),Sum('total_risk_area'),  \
	#                 Sum('water_body_pop_risk'),Sum('barren_land_pop_risk'),Sum('built_up_pop_risk'),Sum('fruit_trees_pop_risk'),Sum('irrigated_agricultural_land_pop_risk'),Sum('permanent_snow_pop_risk'),Sum('rainfed_agricultural_land_pop_risk'),Sum('rangeland_pop_risk'),Sum('sandcover_pop_risk'),Sum('vineyards_pop_risk'),Sum('forest_pop_risk'), Sum('sand_dunes_pop_risk'), \
	#                 Sum('water_body_area_risk'),Sum('barren_land_area_risk'),Sum('built_up_area_risk'),Sum('fruit_trees_area_risk'),Sum('irrigated_agricultural_land_area_risk'),Sum('permanent_snow_area_risk'),Sum('rainfed_agricultural_land_area_risk'),Sum('rangeland_area_risk'),Sum('sandcover_area_risk'),Sum('vineyards_area_risk'),Sum('forest_area_risk'), Sum('sand_dunes_area_risk'), \
	#                 Sum('water_body_pop'),Sum('barren_land_pop'),Sum('built_up_pop'),Sum('fruit_trees_pop'),Sum('irrigated_agricultural_land_pop'),Sum('permanent_snow_pop'),Sum('rainfed_agricultural_land_pop'),Sum('rangeland_pop'),Sum('sandcover_pop'),Sum('vineyards_pop'),Sum('forest_pop'), Sum('sand_dunes_pop'), \
	#                 Sum('water_body_area'),Sum('barren_land_area'),Sum('built_up_area'),Sum('fruit_trees_area'),Sum('irrigated_agricultural_land_area'),Sum('permanent_snow_area'),Sum('rainfed_agricultural_land_area'),Sum('rangeland_area'),Sum('sandcover_area'),Sum('vineyards_area'),Sum('forest_area'), Sum('sand_dunes_area'), \
	#                 Sum('settlements_at_risk'), Sum('settlements'), Sum('Population'), Sum('Area'), Sum('ava_forecast_low_pop'), Sum('ava_forecast_med_pop'), Sum('ava_forecast_high_pop'), Sum('total_ava_forecast_pop'),
	#                 Sum('total_buildings'), Sum('total_risk_buildings'), Sum('high_ava_buildings'), Sum('med_ava_buildings'), Sum('total_ava_buildings') )
	#         else :
	#             px = provincesummary.objects.filter(province=code).aggregate(Sum('high_ava_population'),Sum('med_ava_population'),Sum('low_ava_population'),Sum('total_ava_population'),Sum('high_ava_area'),Sum('med_ava_area'),Sum('low_ava_area'),Sum('total_ava_area'), \
	#                 Sum('high_risk_population'),Sum('med_risk_population'),Sum('low_risk_population'),Sum('total_risk_population'), Sum('high_risk_area'),Sum('med_risk_area'),Sum('low_risk_area'),Sum('total_risk_area'),  \
	#                 Sum('water_body_pop_risk'),Sum('barren_land_pop_risk'),Sum('built_up_pop_risk'),Sum('fruit_trees_pop_risk'),Sum('irrigated_agricultural_land_pop_risk'),Sum('permanent_snow_pop_risk'),Sum('rainfed_agricultural_land_pop_risk'),Sum('rangeland_pop_risk'),Sum('sandcover_pop_risk'),Sum('vineyards_pop_risk'),Sum('forest_pop_risk'), Sum('sand_dunes_pop_risk'), \
	#                 Sum('water_body_area_risk'),Sum('barren_land_area_risk'),Sum('built_up_area_risk'),Sum('fruit_trees_area_risk'),Sum('irrigated_agricultural_land_area_risk'),Sum('permanent_snow_area_risk'),Sum('rainfed_agricultural_land_area_risk'),Sum('rangeland_area_risk'),Sum('sandcover_area_risk'),Sum('vineyards_area_risk'),Sum('forest_area_risk'), Sum('sand_dunes_area_risk'), \
	#                 Sum('water_body_pop'),Sum('barren_land_pop'),Sum('built_up_pop'),Sum('fruit_trees_pop'),Sum('irrigated_agricultural_land_pop'),Sum('permanent_snow_pop'),Sum('rainfed_agricultural_land_pop'),Sum('rangeland_pop'),Sum('sandcover_pop'),Sum('vineyards_pop'),Sum('forest_pop'), Sum('sand_dunes_pop'), \
	#                 Sum('water_body_area'),Sum('barren_land_area'),Sum('built_up_area'),Sum('fruit_trees_area'),Sum('irrigated_agricultural_land_area'),Sum('permanent_snow_area'),Sum('rainfed_agricultural_land_area'),Sum('rangeland_area'),Sum('sandcover_area'),Sum('vineyards_area'),Sum('forest_area'), Sum('sand_dunes_area'), \
	#                 Sum('settlements_at_risk'), Sum('settlements'), Sum('Population'), Sum('Area'), Sum('ava_forecast_low_pop'), Sum('ava_forecast_med_pop'), Sum('ava_forecast_high_pop'), Sum('total_ava_forecast_pop'),
	#                 Sum('total_buildings'), Sum('total_risk_buildings'), Sum('high_ava_buildings'), Sum('med_ava_buildings'), Sum('total_ava_buildings') )
		
	#     for p in px:
	#         response[p[:-5]] = px[p]


	# # Avalanche Forecasted
	# sql = ""
	# if flag=='entireAfg':
	#     # cursor = connections['geodb'].cursor()
	#     sql = "select forcastedvalue.riskstate, \
	#         sum(afg_avsa.avalanche_pop) as pop, \
	#         sum(afg_avsa.area_buildings) as building \
	#         FROM afg_avsa \
	#         INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
	#         INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
	#         INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
	#         WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
	#         AND forcastedvalue.datadate = '%s-%s-%s' \
	#         AND forcastedvalue.forecasttype = 'snowwater' ) \
	#         GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY)
	#     # cursor.execute("select forcastedvalue.riskstate, \
	#     #     sum(afg_avsa.avalanche_pop) as pop, \
	#     #     sum(afg_avsa.area_buildings) as building \
	#     #     FROM afg_avsa \
	#     #     INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
	#     #     INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
	#     #     INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
	#     #     WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
	#     #     AND forcastedvalue.datadate = '%s-%s-%s' \
	#     #     AND forcastedvalue.forecasttype = 'snowwater' ) \
	#     #     GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY))  
	#     # row = cursor.fetchall()
	#     # cursor.close()
	# elif flag=='currentProvince':
	#     # cursor = connections['geodb'].cursor()
	#     if len(str(code)) > 2:
	#         ff0001 =  "dist_code  = '"+str(code)+"'"
	#     else :
	#         ff0001 =  "prov_code  = '"+str(code)+"'"

	#     sql = "select forcastedvalue.riskstate, \
	#         sum(afg_avsa.avalanche_pop) as pop, \
	#         sum(afg_avsa.area_buildings) as building \
	#         FROM afg_avsa \
	#         INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
	#         INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
	#         INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
	#         WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
	#         AND forcastedvalue.datadate = '%s-%s-%s' \
	#         AND forcastedvalue.forecasttype = 'snowwater' ) \
	#         and afg_avsa.%s \
	#         GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,ff0001)
	#     # cursor.execute("select forcastedvalue.riskstate, \
	#     #     sum(afg_avsa.avalanche_pop) as pop, \
	#     #     sum(afg_avsa.area_buildings) as building \
	#     #     FROM afg_avsa \
	#     #     INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
	#     #     INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
	#     #     INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
	#     #     WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
	#     #     AND forcastedvalue.datadate = '%s-%s-%s' \
	#     #     AND forcastedvalue.forecasttype = 'snowwater' ) \
	#     #     and afg_avsa.%s \
	#     #     GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,ff0001)) 
	#     # row = cursor.fetchall()
	#     # cursor.close()
	# elif flag=='drawArea':
	#     # cursor = connections['geodb'].cursor()
	#     sql = "select forcastedvalue.riskstate, \
	#         sum(case \
	#             when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.avalanche_pop \
	#             else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* avalanche_pop end \
	#         ) as pop, \
	#         sum(case \
	#             when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.area_buildings \
	#             else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* area_buildings end \
	#         ) as building \
	#         FROM afg_avsa \
	#         INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
	#         INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
	#         INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
	#         WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
	#         AND forcastedvalue.datadate = '%s-%s-%s' \
	#         AND forcastedvalue.forecasttype = 'snowwater' ) \
	#         GROUP BY forcastedvalue.riskstate" %(filterLock,filterLock, filterLock,filterLock,YEAR,MONTH,DAY)
	#     # cursor.execute("select forcastedvalue.riskstate, \
	#     #     sum(case \
	#     #         when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.avalanche_pop \
	#     #         else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* avalanche_pop end \
	#     #     ) as pop, \
	#     #     sum(case \
	#     #         when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.area_buildings \
	#     #         else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* area_buildings end \
	#     #     ) as building \
	#     #     FROM afg_avsa \
	#     #     INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
	#     #     INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
	#     #     INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
	#     #     WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
	#     #     AND forcastedvalue.datadate = '%s-%s-%s' \
	#     #     AND forcastedvalue.forecasttype = 'snowwater' ) \
	#     #     GROUP BY forcastedvalue.riskstate" %(filterLock,filterLock,YEAR,MONTH,DAY)) 
	#     # row = cursor.fetchall()
	#     # cursor.close()
	# else:
	#     # cursor = connections['geodb'].cursor()
	#     sql = "select forcastedvalue.riskstate, \
	#         sum(afg_avsa.avalanche_pop) as pop, \
	#         sum(afg_avsa.area_buildings) as building \
	#         FROM afg_avsa \
	#         INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
	#         INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
	#         INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
	#         WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
	#         AND forcastedvalue.datadate = '%s-%s-%s' \
	#         AND forcastedvalue.forecasttype = 'snowwater' ) \
	#         AND ST_Within(afg_avsa.wkb_geometry, %s) \
	#         GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,filterLock)
	#     # cursor.execute("select forcastedvalue.riskstate, \
	#     #     sum(afg_avsa.avalanche_pop) as pop, \
	#     #     sum(afg_avsa.area_buildings) as building \
	#     #     FROM afg_avsa \
	#     #     INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
	#     #     INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
	#     #     INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
	#     #     WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
	#     #     AND forcastedvalue.datadate = '%s-%s-%s' \
	#     #     AND forcastedvalue.forecasttype = 'snowwater' ) \
	#     #     AND ST_Within(afg_avsa.wkb_geometry, %s) \
	#     #     GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,filterLock))  
	#     # row = cursor.fetchall()
	#     # cursor.close()    
	# cursor = connections['geodb'].cursor()
	# row = query_to_dicts(cursor, sql)
	# counts = []
	# for i in row:
	#     counts.append(i)
	# cursor.close()

	# temp = dict([(c['riskstate'], c['pop']) for c in counts])
	# # response['ava_forecast_low_pop']=round(dict(row).get(1, 0) or 0,0) 
	# # response['ava_forecast_med_pop']=round(dict(row).get(2, 0) or 0,0) 
	# # response['ava_forecast_high_pop']=round(dict(row).get(3, 0) or 0,0) 
	# response['ava_forecast_low_pop']=round(temp.get(1, 0) or 0,0) 
	# response['ava_forecast_med_pop']=round(temp.get(2, 0) or 0,0) 
	# response['ava_forecast_high_pop']=round(temp.get(3, 0) or 0,0) 
	# response['total_ava_forecast_pop']=response['ava_forecast_low_pop'] + response['ava_forecast_med_pop'] + response['ava_forecast_high_pop']

	# # avalanche forecast buildings
	# temp = dict([(c['riskstate'], c['building']) for c in counts])
	# # response['ava_forecast_low_buildings']=round(dict(row).get(1, 0) or 0,0) 
	# # response['ava_forecast_med_buildings']=round(dict(row).get(2, 0) or 0,0) 
	# # response['ava_forecast_high_buildings']=round(dict(row).get(3, 0) or 0,0)
	# response['ava_forecast_low_buildings']=round(temp.get(1, 0) or 0,0) 
	# response['ava_forecast_med_buildings']=round(temp.get(2, 0) or 0,0) 
	# response['ava_forecast_high_buildings']=round(temp.get(3, 0) or 0,0) 
	# response['total_ava_forecast_buildings']=response['ava_forecast_low_buildings'] + response['ava_forecast_med_buildings'] + response['ava_forecast_high_buildings']

	counts =  getRiskNumber(targetRisk.exclude(mitigated_pop=0), filterLock, 'deeperthan', 'mitigated_pop', 'fldarea_sqm', 'area_buildings', flag, code, None)

	sliced = {c['deeperthan']:c['count'] for c in counts}
	response_tree.path('floodrisk')['mitigatedpop_depth'] = {k:sliced.get(v) or 0 for k,v in DEPTH_TYPES.items()}
	# response_tree['floodrisk']['mitigatedpop']['table'] = {DEPTH_TYPES_INVERSE[c['deeperthan']]:(c['count'] or 0) for c in counts if c['deeperthan'] in DEPTH_TYPES_INVERSE}
	response_tree.path('floodrisk')['mitigatedpop_depth_total'] = sum(response_tree['floodrisk']['mitigatedpop_depth'].values())
	# temp = dict([(c['deeperthan'], c['count']) for c in counts])
	# response = response_tree['floodrisk']['area']['table']
	# response['high_risk_mitigated_population']=round(temp.get('271 cm', 0) or 0,0)
	# response['med_risk_mitigated_population']=round(temp.get('121 cm', 0) or 0, 0)
	# response['low_risk_mitigated_population']=round(temp.get('029 cm', 0) or 0,0)
	# response['total_risk_mitigated_population']=response['high_risk_mitigated_population']+response['med_risk_mitigated_population']+response['low_risk_mitigated_population']

	# River Flood Forecasted
	if rf_type == 'GFMS only':
		bring = filterLock    
	temp_result = getFloodForecastBySource(rf_type, targetRisk, bring, flag, code, YEAR, MONTH, DAY, multi_dict_response=True)
	# for item in temp_result:
	#     response[item]=temp_result[item]
	response_tree = dict_ext(merge_dict(response_tree, temp_result))

	# Flash Flood Forecasted
	# AfgFldzonea100KRiskLandcoverPop.objects.all().select_related("basinmembers").values_list("agg_simplified_description","basinmember__basins__riskstate")
	counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY)), filterLock, 'basinmember__basins__riskstate', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, 'afg_fldzonea_100k_risk_landcover_pop')
	
	sliced = {c['basinmember__basins__riskstate']:c['count'] for c in counts}
	# response_tree.path('floodforecast','pop','flashflood')
	# response_tree['floodforecast']['pop']['flashflood']['table'] = {LIKELIHOOD_INDEX_INVERSE[c['basinmember__basins__riskstate']]:(c['count'] or 0) for c in counts if c['basinmember__basins__riskstate'] in LIKELIHOOD_INDEX_INVERSE}
	response_tree.path('floodforecast')['pop_flashflood_likelihood'] = {v:sliced.get(v) or 0 for k,v in LIKELIHOOD_INDEX.items()}
	response_tree.path('floodforecast')['pop_flashflood_likelihood_total'] = sum(response_tree.path('floodforecast','pop_flashflood_likelihood').values())
	# temp = dict([(c['basinmember__basins__riskstate'], c['count']) for c in counts])
	# response = response_tree['floodforecast']['population']['table']
	# response['flashflood_forecast_verylow_pop']=round(temp.get(1, 0) or 0,0) 
	# response['flashflood_forecast_low_pop']=round(temp.get(2, 0) or 0,0) 
	# response['flashflood_forecast_med_pop']=round(temp.get(3, 0) or 0,0) 
	# response['flashflood_forecast_high_pop']=round(temp.get(4, 0) or 0,0) 
	# response['flashflood_forecast_veryhigh_pop']=round(temp.get(5, 0) or 0,0) 
	# response['flashflood_forecast_extreme_pop']=round(temp.get(6, 0) or 0,0) 
	# response['total_flashflood_forecast_pop']=response['flashflood_forecast_verylow_pop'] + response['flashflood_forecast_low_pop'] + response['flashflood_forecast_med_pop'] + response['flashflood_forecast_high_pop'] + response['flashflood_forecast_veryhigh_pop'] + response['flashflood_forecast_extreme_pop']

	sliced = {c['basinmember__basins__riskstate']:c['areaatrisk'] for c in counts}
	response_tree.path('floodforecast')['area_flashflood_likelihood'] = {v:round((sliced.get(v) or 0)/1000000,0) for k,v in LIKELIHOOD_INDEX.items()}
	response_tree.path('floodforecast')['area_flashflood_likelihood_total'] = sum(response_tree.path('floodforecast','area_flashflood_likelihood').values())
	# response_tree['floodforecast']['area'].setdefault('flashflood',{})
	# response_tree['floodforecast']['area']['flashflood']['table'] = {LIKELIHOOD_INDEX_INVERSE[c['basinmember__basins__riskstate']]:round((c['areaatrisk'] or 0)/1000000,0) for c in counts if c['basinmember__basins__riskstate'] in LIKELIHOOD_INDEX_INVERSE}
	# temp = dict([(c['basinmember__basins__riskstate'], c['areaatrisk']) for c in counts])
	# response = response_tree['floodforecast']['area']['table']
	# response['flashflood_forecast_verylow_area']=round((temp.get(1, 0) or 0)/1000000,0) 
	# response['flashflood_forecast_low_area']=round((temp.get(2, 0) or 0)/1000000,0) 
	# response['flashflood_forecast_med_area']=round((temp.get(3, 0) or 0)/1000000,0) 
	# response['flashflood_forecast_high_area']=round((temp.get(4, 0) or 0)/1000000,0) 
	# response['flashflood_forecast_veryhigh_area']=round((temp.get(5, 0) or 0)/1000000,0) 
	# response['flashflood_forecast_extreme_area']=round((temp.get(6, 0) or 0)/1000000,0) 
	# response['total_flashflood_forecast_area']=response['flashflood_forecast_verylow_area'] + response['flashflood_forecast_low_area'] + response['flashflood_forecast_med_area'] + response['flashflood_forecast_high_area'] + response['flashflood_forecast_veryhigh_area'] + response['flashflood_forecast_extreme_area']

	# number of building on flahsflood forecasted
	sliced = {c['basinmember__basins__riskstate']:c['areaatrisk'] for c in counts}
	response_tree.path('floodforecast')['building_flashflood_likelihood'] = {k:sliced.get(v) or 0 for k,v in LIKELIHOOD_INDEX.items()}
	response_tree.path('floodforecast')['building_flashflood_likelihood_total'] = sum(response_tree.path('floodforecast','building_flashflood_likelihood').values())
	# response_tree['floodforecast']['building'].setdefault('flashflood',{})
	# response_tree['floodforecast']['building']['flashflood']['table'] = {LIKELIHOOD_INDEX_INVERSE[c['basinmember__basins__riskstate']]:(c['houseatrisk'] or 0) for c in counts if c['basinmember__basins__riskstate'] in LIKELIHOOD_INDEX_INVERSE}
	# temp = dict([(c['basinmember__basins__riskstate'], c['houseatrisk']) for c in counts])
	# response = response_tree['floodforecast']['building']['table']
	# response['flashflood_forecast_verylow_buildings']=round(temp.get(1, 0) or 0,0) 
	# response['flashflood_forecast_low_buildings']=round(temp.get(2, 0) or 0,0) 
	# response['flashflood_forecast_med_buildings']=round(temp.get(3, 0) or 0,0) 
	# response['flashflood_forecast_high_buildings']=round(temp.get(4, 0) or 0,0) 
	# response['flashflood_forecast_veryhigh_buildings']=round(temp.get(5, 0) or 0,0) 
	# response['flashflood_forecast_extreme_buildings']=round(temp.get(6, 0) or 0,0) 
	# response['total_flashflood_forecast_buildings']=response['flashflood_forecast_verylow_buildings'] + response['flashflood_forecast_low_buildings'] + response['flashflood_forecast_med_buildings'] + response['flashflood_forecast_high_buildings'] + response['flashflood_forecast_veryhigh_buildings'] + response['flashflood_forecast_extreme_buildings']

	r = response_tree.path('floodforecast')
	r['pop_likelihood_total'] = r['pop_riverflood_likelihood_total'] + r['pop_flashflood_likelihood_total']
	r['area_likelihood_total'] = r['area_riverflood_likelihood_total'] + r['area_flashflood_likelihood_total']
	# response = response_tree['floodforecast']['population']['table']
	# response['total_flood_forecast_pop'] = response['total_riverflood_forecast_pop'] + response['total_flashflood_forecast_pop']
	# response = response_tree['floodforecast']['area']['table']
	# response['total_flood_forecast_area'] = response['total_riverflood_forecast_area'] + response['total_flashflood_forecast_area']

	response_tree = dict_ext(none_to_zero(response_tree))

	# # flood risk and flashflood forecast matrix
	# px = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY))
	# # px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
	# #     select={
	# #         'pop' : 'SUM(fldarea_population)'
	# #     }).values('basinmember__basins__riskstate','deeperthan', 'pop') 
	# if flag=='entireAfg': 
	#     px = px.\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(pop=Sum('fldarea_population')).\
	#         annotate(building=Sum('area_buildings')).\
	#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
	# elif flag=='currentProvince':
	#     if len(str(code)) > 2:
	#         ff0001 =  "dist_code  = '"+str(code)+"'"
	#     else :
	#         if len(str(code))==1:
	#             ff0001 =  "left(cast(dist_code as text),1)  = '"+str(code)+"'"
	#         else:
	#             ff0001 =  "left(cast(dist_code as text),2)  = '"+str(code)+"'"   
	#     px = px.\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(pop=Sum('fldarea_population')).\
	#         annotate(building=Sum('area_buildings')).\
	#         extra(
	#             where={
	#                 ff0001
	#             }).\
	#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
	# elif flag=='drawArea':
	#     px = px.\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(pop=RawSQL_nogroupby('SUM(  \
	#                         case \
	#                             when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then fldarea_population \
	#                             else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* fldarea_population end \
	#                     )',())).\
	#         annotate(building=RawSQL_nogroupby('SUM(  \
	#                         case \
	#                             when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then area_buildings \
	#                             else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* area_buildings end \
	#                     )',())).\
	#         extra(
	#             where = {
	#                 'ST_Intersects(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
	#             }).\
	#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')  
	# else:
	#     px = px.\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(pop=Sum('fldarea_population')).\
	#         annotate(building=Sum('area_buildings')).\
	#         extra(
	#             where = {
	#                 'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
	#             }).\
	#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')     

	px = none_to_zero(getFlashFloodForecastRisk(filterLock, flag, code, targetRisk, YEAR, MONTH, DAY))

	response_tree.path('floodforecast')['pop_flashflood_likelihood']={l:{d:0 for d in DEPTH_TYPES} for l in LIKELIHOOD_INDEX_INVERSE}
	response_tree.path('floodforecast')['building_flashflood_likelihood']={l:{d:0 for d in DEPTH_TYPES} for l in LIKELIHOOD_INDEX_INVERSE}

	for row in px:
		likelihood = LIKELIHOOD_INDEX[row['basinmember__basins__riskstate']]
		depth = DEPTH_TYPES_INVERSE[row['deeperthan']]
		response_tree.path('floodforecast')['pop_flashflood_likelihood'][likelihood][depth]=round(row['population'] or 0,0)
		response_tree.path('floodforecast')['building_flashflood_likelihood'][likelihood][depth]=round(row['building'] or 0,0)
		# response_tree['flashflood_forecast_%s_risk_%s_pop'%(likelihood_type, depth_type)]=round(row['deeperthan'] or 0,0)

	# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 1 ]
	# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
	# response = response_tree['floodforecast']['population']['table']
	# response['flashflood_forecast_verylow_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_verylow_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_verylow_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
	# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
	# response = response_tree['floodforecast']['buildings']['table']
	# response['flashflood_forecast_verylow_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_verylow_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_verylow_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

	# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 2 ]
	# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
	# response = response_tree['floodforecast']['population']['table']
	# response['flashflood_forecast_low_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_low_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0) 
	# response['flashflood_forecast_low_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
	# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
	# response = response_tree['floodforecast']['buildings']['table']
	# response['flashflood_forecast_low_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_low_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0) 
	# response['flashflood_forecast_low_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

	# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 3 ]
	# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
	# response = response_tree['floodforecast']['population']['table']
	# response['flashflood_forecast_med_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_med_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_med_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0) 
	# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
	# response = response_tree['floodforecast']['buildings']['table']
	# response['flashflood_forecast_med_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_med_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_med_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

	# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 4 ]
	# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
	# response = response_tree['floodforecast']['population']['table']
	# response['flashflood_forecast_high_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_high_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_high_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
	# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
	# response = response_tree['floodforecast']['buildings']['table']
	# response['flashflood_forecast_high_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_high_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_high_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

	# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 5 ]
	# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
	# response = response_tree['floodforecast']['population']['table']
	# response['flashflood_forecast_veryhigh_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_veryhigh_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_veryhigh_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
	# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
	# response = response_tree['floodforecast']['buildings']['table']
	# response['flashflood_forecast_veryhigh_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_veryhigh_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_veryhigh_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

	# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 6 ]
	# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
	# response = response_tree['floodforecast']['population']['table']
	# response['flashflood_forecast_extreme_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_extreme_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_extreme_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
	# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
	# response = response_tree['floodforecast']['buildings']['table']
	# response['flashflood_forecast_extreme_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
	# response['flashflood_forecast_extreme_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
	# response['flashflood_forecast_extreme_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)
	
	response_tree.path('floodrisk')['pop_depth_percent'] = {k:round(div_by_zero_is_zero(v, response_tree['baseline']['pop_total'])*100, 0) for k,v in response_tree['floodrisk']['pop_depth'].items()}
	response_tree.path('floodrisk')['pop_depth_percent_total'] = sum(response_tree.path('floodrisk')['pop_depth_percent'].values())
	
	# floodrisk = response_tree.path('floodrisk','pop')
	# # baseline = response_tree['baseline']['pop']['table']

	# for level in ['high','med','low']:
	#     floodrisk.path('depth_percent')[level] = round(div_by_zero_is_zero(floodrisk.path('depth',level), response_tree['baseline']['pop']['total'])*100, 0)
	# floodrisk['depth_percent_total'] = sum(floodrisk['depth_percent'].values())

	# try:
	#     floodrisk['percent_total_risk_population'] = round((floodrisk['total_risk_population']/baseline['Population'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_total_risk_population'] = 0
		
	# try:
	#     floodrisk['percent_high_risk_population'] = round((floodrisk['high_risk_population']/baseline['Population'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_high_risk_population'] = 0

	# try:
	#     floodrisk['percent_med_risk_population'] = round((floodrisk['med_risk_population']/baseline['Population'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_med_risk_population'] = 0

	# try:
	#     floodrisk['percent_low_risk_population'] = round((floodrisk['low_risk_population']/baseline['Population'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_low_risk_population'] = 0

	response_tree.path('floodrisk')['area_depth_percent'] = {k:round(div_by_zero_is_zero(v, response_tree['baseline']['area_total'])*100, 0) for k,v in response_tree['floodrisk']['area_depth'].items()}
	response_tree.path('floodrisk')['area_depth_percent_total'] = sum(response_tree.path('floodrisk')['area_depth_percent'].values())

	# floodrisk = dict_ext(response_tree.path('floodrisk','area'))
	# # baseline = response_tree['baseline']['area']['table']

	# for level in ['high','med','low']:
	#     floodrisk.path('depth_percent')[level] = round(div_by_zero_is_zero(floodrisk['depth'][level], response_tree['baseline']['area']['total'])*100, 0)
	# floodrisk['depth_percent_total'] = sum(floodrisk['depth_percent'].values())

	# try:
	#     floodrisk['percent_total_risk_area'] = round((floodrisk['total_risk_area']/baseline['Area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_total_risk_area'] = 0

	# try:
	#     floodrisk['percent_high_risk_area'] = round((floodrisk['high_risk_area']/baseline['Area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_high_risk_area'] = 0

	# try:
	#     floodrisk['percent_med_risk_area'] = round((floodrisk['med_risk_area']/baseline['Area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_med_risk_area'] = 0
	
	# try:
	#     floodrisk['percent_low_risk_area'] = round((floodrisk['low_risk_area']/baseline['Area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_low_risk_area'] = 0

	# avalancherisk = response_tree['avalancherisk']['population']['table']
	# baseline = response_tree['baseline']['population']['table']

	# for level in ['total','high','med','low']:
	#     floodrisk['percent_%s_ava_population'%(level)] = \
	#         round(div_by_zero_is_zero(avalancherisk['%s_ava_population'%(level)], baseline['Population'])*100, 0)

	# try:
	#     response['percent_total_ava_population'] = round((response['total_ava_population']/response['Population'])*100,0)
	# except ZeroDivisionError:
	#     response['percent_total_ava_population'] = 0
	
	# try:
	#     response['percent_high_ava_population'] = round((response['high_ava_population']/response['Population'])*100,0)
	# except ZeroDivisionError:
	#     response['percent_high_ava_population'] = 0    
	
	# try:
	#     response['percent_med_ava_population'] = round((response['med_ava_population']/response['Population'])*100,0)
	# except ZeroDivisionError:
	#     response['percent_med_ava_population'] = 0

	# try:
	#     response['percent_low_ava_population'] = round((response['low_ava_population']/response['Population'])*100,0)
	# except ZeroDivisionError:
	#     response['percent_low_ava_population'] = 0

	# avalancherisk = response_tree['avalancherisk']['area']['table']
	# baseline = response_tree['baseline']['area']['table']

	# for level in ['total','high','med','low']:
	#     floodrisk['percent_%s_ava_area'%(level)] = \
	#         round(div_by_zero_is_zero(avalancherisk['%s_ava_area'%(level)], baseline['Area'])*100, 0)

	# try:
	#     response['percent_total_ava_area'] = round((response['total_ava_area']/response['Area'])*100,0)
	# except ZeroDivisionError:
	#     response['percent_total_ava_area'] = 0

	# try:
	#     response['percent_high_ava_area'] = round((response['high_ava_area']/response['Area'])*100,0)
	# except ZeroDivisionError:
	#     response['percent_high_ava_area'] = 0

	# try:
	#     response['percent_med_ava_area'] = round((response['med_ava_area']/response['Area'])*100,0)
	# except ZeroDivisionError:
	#     response['percent_med_ava_area'] = 0
	# try:
	#     response['percent_low_ava_area'] = round((response['low_ava_area']/response['Area'])*100,0)
	# except ZeroDivisionError:
	#     response['percent_low_ava_area'] = 0    

	# floodrisk = response_tree.path('floodrisk','pop')
	# baseline = response_tree.path('baseline','pop')

	# for lctype in LANDCOVER_TYPES:
	#     floodrisk.path('lc_percent')[lctype] = round(div_by_zero_is_zero(floodrisk.path('lc')[lctype], baseline.path('lc')[lctype])*100, 0)
	response_tree.path('floodrisk')['pop_lc_percent'] = {k:round(div_by_zero_is_zero(v, response_tree['baseline']['pop_lc'][k])*100, 0) for k,v in response_tree['floodrisk']['pop_lc'].items()}

	# Population percentage
	# try:
	#     floodrisk['percent_barren_land_pop_risk'] = round((floodrisk['barren_land_pop_risk']/baseline['barren_land_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_barren_land_pop_risk'] = 0
	# try:
	#     floodrisk['percent_built_up_pop_risk'] = round((floodrisk['built_up_pop_risk']/baseline['built_up_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_built_up_pop_risk'] = 0       
	# try:
	#     floodrisk['percent_fruit_trees_pop_risk'] = round((floodrisk['fruit_trees_pop_risk']/baseline['fruit_trees_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_fruit_trees_pop_risk'] = 0
	# try:
	#     floodrisk['percent_irrigated_agricultural_land_pop_risk'] = round((floodrisk['irrigated_agricultural_land_pop_risk']/baseline['irrigated_agricultural_land_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_irrigated_agricultural_land_pop_risk'] = 0     
	# try:
	#     floodrisk['percent_permanent_snow_pop_risk'] = round((floodrisk['permanent_snow_pop_risk']/baseline['permanent_snow_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_permanent_snow_pop_risk'] = 0 
	# try:
	#     floodrisk['percent_rainfed_agricultural_land_pop_risk'] = round((floodrisk['rainfed_agricultural_land_pop_risk']/baseline['rainfed_agricultural_land_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_rainfed_agricultural_land_pop_risk'] = 0  
	# try:
	#     floodrisk['percent_rangeland_pop_risk'] = round((floodrisk['rangeland_pop_risk']/baseline['rangeland_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_rangeland_pop_risk'] = 0  
	# try:
	#     floodrisk['percent_sandcover_pop_risk'] = round((floodrisk['sandcover_pop_risk']/baseline['sandcover_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_sandcover_pop_risk'] = 0  
	# try:
	#     floodrisk['percent_vineyards_pop_risk'] = round((floodrisk['vineyards_pop_risk']/baseline['vineyards_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_vineyards_pop_risk'] = 0  
	# try:
	#     floodrisk['percent_water_body_pop_risk'] = round((floodrisk['water_body_pop_risk']/baseline['water_body_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_water_body_pop_risk'] = 0     
	# try:
	#     floodrisk['percent_forest_pop_risk'] = round((floodrisk['forest_pop_risk']/baseline['forest_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_forest_pop_risk'] = 0    
	# try:
	#     floodrisk['percent_sand_dunes_pop_risk'] = round((floodrisk['sand_dunes_pop_risk']/baseline['sand_dunes_pop'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_sand_dunes_pop_risk'] = 0                          

	# floodrisk = response_tree['floodrisk']['area']['lc']
	# baseline = response_tree['baseline']['area']['lc']

	response_tree.path('floodrisk')['area_lc_percent'] = {k:round(div_by_zero_is_zero(v, response_tree['baseline']['area_lc'][k])*100, 0) for k,v in response_tree['floodrisk']['area_lc'].items()}

	# for lctype in LANDCOVER_TYPES:
	#     floodrisk['percent'][lctype] = round(div_by_zero_is_zero(floodrisk[lctype], baseline[lctype])*100, 0)
	# floodrisk.path('floodrisk','area')['lc_percent'] = {\
	#     t:round(div_by_zero_is_zero(response_tree.path('floodrisk','area','lc')[t], response_tree.path('baseline','area','lc')[t])*100, 0) \
	#     for t in LANDCOVER_TYPES\
	# }

	# Area percentage
	# try:
	#     floodrisk['percent_barren_land_area_risk'] = round((floodrisk['barren_land_area_risk']/baseline['barren_land_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_barren_land_area_risk'] = 0
	# try:        
	#     floodrisk['percent_built_up_area_risk'] = round((floodrisk['built_up_area_risk']/baseline['built_up_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_built_up_area_risk'] = 0    
	# try:
	#     floodrisk['percent_fruit_trees_area_risk'] = round((floodrisk['fruit_trees_area_risk']/baseline['fruit_trees_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_fruit_trees_area_risk'] = 0        
	# try:
	#     floodrisk['percent_irrigated_agricultural_land_area_risk'] = round((floodrisk['irrigated_agricultural_land_area_risk']/baseline['irrigated_agricultural_land_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_irrigated_agricultural_land_area_risk'] = 0 
	# try:
	#     floodrisk['percent_permanent_snow_area_risk'] = round((floodrisk['permanent_snow_area_risk']/baseline['permanent_snow_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_permanent_snow_area_risk'] = 0 
	# try:
	#     floodrisk['percent_rainfed_agricultural_land_area_risk'] = round((floodrisk['rainfed_agricultural_land_area_risk']/baseline['rainfed_agricultural_land_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_rainfed_agricultural_land_area_risk'] = 0  
	# try:
	#     floodrisk['percent_rangeland_area_risk'] = round((floodrisk['rangeland_area_risk']/baseline['rangeland_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_rangeland_area_risk'] = 0  
	# try:
	#     floodrisk['percent_sandcover_area_risk'] = round((floodrisk['sandcover_area_risk']/baseline['sandcover_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_sandcover_area_risk'] = 0  
	# try:
	#     floodrisk['percent_vineyards_area_risk'] = round((floodrisk['vineyards_area_risk']/baseline['vineyards_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_vineyards_area_risk'] = 0  
	# try:
	#     floodrisk['percent_water_body_area_risk'] = round((floodrisk['water_body_area_risk']/baseline['water_body_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_water_body_area_risk'] = 0     
	# try:
	#     floodrisk['percent_forest_area_risk'] = round((floodrisk['forest_area_risk']/baseline['forest_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_forest_area_risk'] = 0 
	# try:
	#     floodrisk['percent_sand_dunes_area_risk'] = round((floodrisk['sand_dunes_area_risk']/baseline['sand_dunes_area'])*100,0)
	# except ZeroDivisionError:
	#     floodrisk['percent_sand_dunes_area_risk'] = 0 

	# # Roads 
	# if flag=='drawArea':
	#     countsRoadBase = AfgRdsl.objects.all().\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(road_length=RawSQL_nogroupby('SUM(  \
	#                     case \
	#                         when ST_CoveredBy(wkb_geometry'+','+filterLock+') then road_length \
	#                         else ST_Length(st_intersection(wkb_geometry::geography'+','+filterLock+')) / road_length end \
	#                 )/1000')).\
	#         extra(
	#         where = {
	#             'ST_Intersects(wkb_geometry'+', '+filterLock+')'
	#         }).\
	#         values('type_update','road_length') 

	#     countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(numberhospital=Count('ogc_fid')).\
	#         extra(
	#             where = {
	#                 'ST_Intersects(wkb_geometry'+', '+filterLock+')'
	#             }).\
	#         values('facility_types_description', 'numberhospital')

	# elif flag=='entireAfg':    
	#     # countsRoadBase = AfgRdsl.objects.all().values('type_update').annotate(counter=Count('ogc_fid')).extra(
	#     #         select={
	#     #             'road_length' : 'SUM(road_length)/1000'
	#     #         }).values('type_update', 'road_length')
	#     countsRoadBase = AfgRdsl.objects.all().\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(road_length__sum=Sum('road_length')/1000).\
	#         values('type_update', 'road_length__sum')

	#     # Health Facilities
	#     # countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').values('facility_types_description').annotate(counter=Count('ogc_fid')).extra(
	#     #         select={
	#     #             'numberhospital' : 'count(*)'
	#     #         }).values('facility_types_description', 'numberhospital')
	#     countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(numberhospital=Count('ogc_fid')).\
	#         values('facility_types_description', 'numberhospital')
		
	# elif flag=='currentProvince':
	#     if len(str(code)) > 2:
	#         ff0001 =  "dist_code  = '"+str(code)+"'"
	#     else :
	#         if len(str(code))==1:
	#             ff0001 =  "left(cast(dist_code as text),1)  = '"+str(code)+"'"
	#         else:
	#             ff0001 =  "left(cast(dist_code as text),2)  = '"+str(code)+"'"    
				
	#     countsRoadBase = AfgRdsl.objects.all().\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(road_length__sum=Sum('road_length')/1000).\
	#         extra(
	#             where = {
	#                 ff0001
	#             }).\
	#         values('type_update','road_length__sum') 

	#     countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(numberhospital=Count('ogc_fid')).\
	#         extra(
	#             where = {
	#                 ff0001
	#             }).\
	#         values('facility_types_description', 'numberhospital')

	# elif flag=='currentBasin':
	#     print 'currentBasin'
	# else:
	#     countsRoadBase = AfgRdsl.objects.all().\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(road_length__sum=Sum('road_length')/1000).\
	#         extra(
	#             where = {
	#                 'ST_Within(wkb_geometry'+', '+filterLock+')'
	#             }).\
	#         values('type_update','road_length__sum') 

	#     countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').\
	#         annotate(counter=Count('ogc_fid')).\
	#         annotate(numberhospital=Count('ogc_fid')).\
	#         extra(
	#             where = {
	#                 'ST_Within(wkb_geometry'+', '+filterLock+')'
	#             }).\
	#         values('facility_types_description', 'numberhospital')


	# tempRoadBase = dict([(c['type_update'], c['road_length__sum']) for c in countsRoadBase])
	# tempHLTBase = dict([(c['facility_types_description'], c['numberhospital']) for c in countsHLTBase])

	# response["highway_road_base"]=round(tempRoadBase.get("highway", 0),1)
	# response["primary_road_base"]=round(tempRoadBase.get("primary", 0),1)
	# response["secondary_road_base"]=round(tempRoadBase.get("secondary", 0),1)
	# response["tertiary_road_base"]=round(tempRoadBase.get("tertiary", 0),1)
	# response["residential_road_base"]=round(tempRoadBase.get("residential", 0),1)
	# response["track_road_base"]=round(tempRoadBase.get("track", 0),1)
	# response["path_road_base"]=round(tempRoadBase.get("path", 0),1)
	# response["river_crossing_road_base"]=round(tempRoadBase.get("river crossing", 0),1)
	# response["bridge_road_base"]=round(tempRoadBase.get("bridge", 0),1)
	# response["total_road_base"]=response["highway_road_base"]+response["primary_road_base"]+response["secondary_road_base"]+response["tertiary_road_base"]+response["residential_road_base"]+response["track_road_base"]+response["path_road_base"]+response["river_crossing_road_base"]+response["bridge_road_base"]

	# response["h1_health_base"]=round(tempHLTBase.get("Regional / National Hospital (H1)", 0))
	# response["h2_health_base"]=round(tempHLTBase.get("Provincial Hospital (H2)", 0))    
	# response["h3_health_base"]=round(tempHLTBase.get("District Hospital (H3)", 0))
	# response["sh_health_base"]=round(tempHLTBase.get("Special Hospital (SH)", 0))
	# response["rh_health_base"]=round(tempHLTBase.get("Rehabilitation Center (RH)", 0))               
	# response["mh_health_base"]=round(tempHLTBase.get("Maternity Home (MH)", 0))
	# response["datc_health_base"]=round(tempHLTBase.get("Drug Addicted Treatment Center", 0))
	# response["tbc_health_base"]=round(tempHLTBase.get("TB Control Center (TBC)", 0))
	# response["mntc_health_base"]=round(tempHLTBase.get("Mental Clinic / Hospital", 0))
	# response["chc_health_base"]=round(tempHLTBase.get("Comprehensive Health Center (CHC)", 0))
	# response["bhc_health_base"]=round(tempHLTBase.get("Basic Health Center (BHC)", 0))
	# response["dcf_health_base"]=round(tempHLTBase.get("Day Care Feeding", 0))
	# response["mch_health_base"]=round(tempHLTBase.get("MCH Clinic M1 or M2 (MCH)", 0))
	# response["shc_health_base"]=round(tempHLTBase.get("Sub Health Center (SHC)", 0))
	# response["ec_health_base"]=round(tempHLTBase.get("Eye Clinic / Hospital", 0))
	# response["pyc_health_base"]=round(tempHLTBase.get("Physiotherapy Center", 0))
	# response["pic_health_base"]=round(tempHLTBase.get("Private Clinic", 0))        
	# response["mc_health_base"]=round(tempHLTBase.get("Malaria Center (MC)", 0))
	# response["moph_health_base"]=round(tempHLTBase.get("MoPH National", 0))
	# response["epi_health_base"]=round(tempHLTBase.get("EPI Fixed Center (EPI)", 0))
	# response["sfc_health_base"]=round(tempHLTBase.get("Supplementary Feeding Center (SFC)", 0))
	# response["mht_health_base"]=round(tempHLTBase.get("Mobile Health Team (MHT)", 0))
	# response["other_health_base"]=round(tempHLTBase.get("Other", 0))
	# response["total_health_base"] = response["bhc_health_base"]+response["dcf_health_base"]+response["mch_health_base"]+response["rh_health_base"]+response["h3_health_base"]+response["sh_health_base"]+response["mh_health_base"]+response["datc_health_base"]+response["h1_health_base"]+response["shc_health_base"]+response["ec_health_base"]+response["pyc_health_base"]+response["pic_health_base"]+response["tbc_health_base"]+response["mntc_health_base"]+response["chc_health_base"]+response["other_health_base"]+response["h2_health_base"]+response["mc_health_base"]+response["moph_health_base"]+response["epi_health_base"]+response["sfc_health_base"]+response["mht_health_base"]
	
	# response = response_tree.path('floodforecast','lastupdated','values')

	try:
		row = forecastedLastUpdate.objects.filter(forecasttype='snowwater').latest('datadate')
	except forecastedLastUpdate.DoesNotExist:
		response_tree.path('floodforecast','lastupdated')["snowwater"] = None
	else:
		response_tree.path('floodforecast','lastupdated')["snowwater"] = timeago.format(row.datadate, datetime.datetime.utcnow())   #tempSW.strftime("%d-%m-%Y %H:%M")
		# tempSW = sw.datadate + datetime.timedelta(hours=4.5)
		# response_tree.path('floodforecast','lastupdated')["snowwater"] = timeago.format(tempSW, datetime.datetime.utcnow()+ datetime.timedelta(hours=4.5))   #tempSW.strftime("%d-%m-%Y %H:%M")

	# response = response_tree.path('floodforecast','lastupdated','values')

	try:
		row = forecastedLastUpdate.objects.filter(forecasttype='riverflood').latest('datadate')
	except forecastedLastUpdate.DoesNotExist:
		response_tree.path('floodforecast','lastupdated')["riverflood"] = None
	else:
		response_tree.path('floodforecast','lastupdated')["riverflood"] = timeago.format(row.datadate, datetime.datetime.utcnow())  #tempRF.strftime("%d-%m-%Y %H:%M")
		# tempRF = rf.datadate + datetime.timedelta(hours=4.5)
		# response_tree.path('floodforecast','lastupdated')["riverflood"] = timeago.format(tempRF, datetime.datetime.utcnow()+ datetime.timedelta(hours=4.5))  #tempRF.strftime("%d-%m-%Y %H:%M")

	# print rf.datadate

	now = datetime.datetime.utcnow()
	update = now.replace(hour=3, minute=00, second=00)
	update = update - datetime.timedelta(days=1) if now < update else update

	response_tree.path('floodforecast','lastupdated')["glofas"] = timeago.format(update, now)     #tempSC.strftime("%d-%m-%Y %H:%M")

	# tz = timezone('Asia/Kabul')
	# stdSC = datetime.datetime.utcnow()
	# stdSC = stdSC.replace(hour=3, minute=00, second=00)

	# tempSC = datetime.datetime.utcnow()

	# if stdSC > tempSC:
	#     tempSC = tempSC - datetime.timedelta(days=1)
	
	# tempSC = tempSC.replace(hour=3, minute=00, second=00)
	# tempSC = tempSC + datetime.timedelta(hours=4.5)
	# # tempSC = tempSC.replace(tzinfo=tz) 
	# print tempSC
	# response_tree.path('floodforecast','lastupdated')["glofas"] = timeago.format(tempSC, datetime.datetime.utcnow()+ datetime.timedelta(hours=4.5))     #tempSC.strftime("%d-%m-%Y %H:%M")
	
	return response_tree

def getFloodForecastRisk(filterLock, flag, code, targetRisk, Year, Month, Day, floodtype='flashflood'):
	# flood risk and flashflood forecast matrix
	basequery = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype=floodtype,basinmember__basins__datadate='%s-%s-%s' %(Year, Month, Day))
	fieldGroup = ['basinmember__basins__riskstate','deeperthan']
	kwargs = {
		'alias': {
			'pop': 'pop',
			'area': 'area',
			'building': 'building',
			'settlement': 'settlement',
		}
	}

	return getRiskNumber(basequery, filterLock, fieldGroup, 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, 'afg_fldzonea_100k_risk_landcover_pop', **kwargs)
	
	# px = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype=floodtype,basinmember__basins__datadate='%s-%s-%s' %(Year, Month, Day))

	# annotates = {
	# 	'counter':Count('ogc_fid'),
	# 	'pop':Sum('fldarea_population'),
	# 	'building':Sum('area_buildings'),
	# }

	# if flag=='entireAfg': 
	# 	px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates)
	# elif flag=='currentProvince':
	# 	ff0001 =  "left(cast(dist_code as text),%s) = '%s'"%(len(str(code)), code)
	# 	px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where={ff0001})
	# elif flag=='drawArea':
	# 	sum_tpl = '\
	# 		SUM(  \
	# 			case \
	# 				when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,{filterLock}) then {area_field} \
	# 				else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,{filterLock})) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* {area_field} \
	# 			end \
	# 		)'
	# 	annotates = {
	# 		'counter':Count('ogc_fid'),
	# 		'pop':RawSQL_nogroupby(sum_tpl.format({'filterLock':filterLock,'area_field':'fldarea_population'}),()),
	# 		'building':RawSQL_nogroupby(sum_tpl.format({'filterLock':filterLock,'area_field':'area_buildings'}),()),
	# 	}
	# 	px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where = {'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'})
	# else:
	# 	px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where = {'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'})

	# return px

def getFlashFloodForecastRisk(filterLock, flag, code, targetRisk, Year, Month, Day):
	# deprecated; use getFloodForecastRisk(floodtype='flashflood')
	# flood risk and flashflood forecast matrix
	px = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(Year, Month, Day))

	annotates = {
		'counter':Count('ogc_fid'),
		'pop':Sum('fldarea_population'),
		'building':Sum('area_buildings'),
	}

	if flag=='entireAfg': 
		px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates)
	elif flag=='currentProvince':
		ff0001 =  "left(cast(dist_code as text),%s) = '%s'"%(len(str(code)), code)
		px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where={ff0001})
	elif flag=='drawArea':
		sum_tpl = '\
			SUM(  \
				case \
					when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,{filterLock}) then {area_field} \
					else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,{filterLock})) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* {area_field} \
				end \
			)'
		annotates = {
			'counter':Count('ogc_fid'),
			'pop':RawSQL_nogroupby(sum_tpl.format({'filterLock':filterLock,'area_field':'fldarea_population'}),()),
			'building':RawSQL_nogroupby(sum_tpl.format({'filterLock':filterLock,'area_field':'area_buildings'}),()),
		}
		px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where = {'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'})
	else:
		px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where = {'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'})
	# px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
	#     select={
	#         'pop' : 'SUM(fldarea_population)'
	#     }).values('basinmember__basins__riskstate','deeperthan', 'pop') 
	# if flag=='entireAfg': 
	# 	px = px.\
	# 		annotate(counter=Count('ogc_fid')).\
	# 		annotate(pop=Sum('fldarea_population')).\
	# 		annotate(building=Sum('area_buildings')).\
	# 		values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
	# elif flag=='currentProvince':
	# 	if len(str(code)) > 2:
	# 		ff0001 =  "dist_code  = '"+str(code)+"'"
	# 	else :
	# 		if len(str(code))==1:
	# 			ff0001 =  "left(cast(dist_code as text),1)  = '"+str(code)+"'"
	# 		else:
	# 			ff0001 =  "left(cast(dist_code as text),2)  = '"+str(code)+"'"   
	# 	px = px.\
	# 		annotate(counter=Count('ogc_fid')).\
	# 		annotate(pop=Sum('fldarea_population')).\
	# 		annotate(building=Sum('area_buildings')).\
	# 		extra(
	# 			where={
	# 				ff0001
	# 			}).\
	# 		values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
	# elif flag=='drawArea':
	# 	px = px.\
	# 		annotate(counter=Count('ogc_fid')).\
	# 		annotate(pop=RawSQL_nogroupby('SUM(  \
	# 						case \
	# 							when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then fldarea_population \
	# 							else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* fldarea_population end \
	# 					)',())).\
	# 		annotate(building=RawSQL_nogroupby('SUM(  \
	# 						case \
	# 							when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then area_buildings \
	# 							else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* area_buildings end \
	# 					)',())).\
	# 		extra(
	# 			where = {
	# 				'ST_Intersects(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
	# 			}).\
	# 		values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')  
	# else:
	# 	px = px.\
	# 		annotate(counter=Count('ogc_fid')).\
	# 		annotate(pop=Sum('fldarea_population')).\
	# 		annotate(building=Sum('area_buildings')).\
	# 		extra(
	# 			where = {
	# 				'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
	# 			}).\
	# 		values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')     

	return px

class FloodRiskStatisticResource(ModelResource):

	class Meta:
		# authorization = DjangoAuthorization()
		resource_name = 'statistic_floodrisk'
		allowed_methods = ['post']
		detail_allowed_methods = ['post']
		cache = SimpleCache()
		object_class=None
		# always_return_data = True
 
	def getRisk(self, request):
		# saving the user tracking records

		# o = urlparse(request.META.get('HTTP_REFERER')).path
		# o=o.split('/')
		# if 'v2' in o:
		# 	mapCode = o[3]
		# else:
		# 	mapCode = o[2]
		p = urlparse(request.META.get('HTTP_REFERER')).path.split('/')
		mapCode = p[3] if 'v2' in p else p[2]
		map_obj = _resolve_map(request, mapCode, 'base.view_resourcebase', _PERMISSION_MSG_VIEW)

		queryset = matrix(user=request.user,resourceid=map_obj,action='Interactive Calculation')
		queryset.save()

		boundaryFilter = json.loads(request.body)

		# bring = None
		# temp1 = []
		# for i in boundaryFilter['spatialfilter']:
		# 	temp1.append('ST_GeomFromText(\''+i+'\',4326)')
		# 	bring = i

		# temp2 = 'ARRAY['
		# first=True
		# for i in temp1:
		# 	if first:
		# 		 temp2 = temp2 + i
		# 		 first=False
		# 	else :
		# 		 temp2 = temp2 + ', ' + i  

		# temp2 = temp2+']'
		
		# filterLock = 'ST_Union('+temp2+')'
		# yy = None
		# mm = None
		# dd = None

		wkts = ['ST_GeomFromText(\''+i+'\',4326)' for i in boundaryFilter['spatialfilter']]
		bring = wkts[-1] if len(wkts) else None
		filterLock = 'ST_Union(ARRAY['+', '.join(wkts)+'])'

		# d = datetime.datetime.strptime('2018-09-11','%Y-%m-%d')
		# yy, mm, dd = [d.year, d.month, d.day] if (datetime.datetime.today() - d).days > 0 else [None, None, None]

		# yy = mm = dd = None

		# if 'date' in boundaryFilter:
		# 	tempDate = boundaryFilter['date'].split("-")
		# 	dateSent = datetime.datetime(int(tempDate[0]), int(tempDate[1]), int(tempDate[2]))

		# 	if (datetime.datetime.today() - dateSent).days != 0:
		# 		yy, mm, dd = tempDate[0:3]

		response = getFloodriskStatistic(request, filterLock, boundaryFilter.get('flag'), boundaryFilter.get('code'))

		return response

	def post_list(self, request, **kwargs):
		self.method_check(request, allowed=['post'])
		response = self.getRisk(request)
		return self.create_response(request, response)  

	# def get_list(self, request, **kwargs):
	#     self.method_check(request, allowed=['get'])
	#     response = self.getRisk(request)
	#     return self.create_response(request, response)    

class FloodForecastStatisticResource(ModelResource):

	class Meta:
		# authorization = DjangoAuthorization()
		resource_name = 'statistic_floodforecast'
		allowed_methods = ['post']
		detail_allowed_methods = ['post']
		cache = SimpleCache()
		object_class=None
		# always_return_data = True
 
	def getRisk(self, request):

		p = urlparse(request.META.get('HTTP_REFERER')).path.split('/')
		mapCode = p[3] if 'v2' in p else p[2]
		map_obj = _resolve_map(request, mapCode, 'base.view_resourcebase', _PERMISSION_MSG_VIEW)

		queryset = matrix(user=request.user,resourceid=map_obj,action='Interactive Calculation')
		queryset.save()

		boundaryFilter = json.loads(request.body)

		wkts = ['ST_GeomFromText(\''+i+'\',4326)' for i in boundaryFilter['spatialfilter']]
		bring = wkts[-1] if len(wkts) else None
		filterLock = 'ST_Union(ARRAY['+', '.join(wkts)+'])'

		# d = datetime.datetime.strptime('2018-09-11','%Y-%m-%d')
		# yy, mm, dd = [d.year, d.month, d.day] if (datetime.datetime.today() - d).days > 0 else [None, None, None]

		response = getFloodforecastStatistic(request, filterLock, boundaryFilter.get('flag'), boundaryFilter.get('code'), date=[boundaryFilter.get('date')])
		# response = getFloodForecast(request, filterLock, boundaryFilter.get('flag'), boundaryFilter.get('code'), rf_types=[boundaryFilter.get('rf_type')])
		# response = getFloodriskStatistic(request, filterLock, boundaryFilter.get('flag'), boundaryFilter.get('code'), yy, mm, dd, boundaryFilter.get('rf_type'), bring)

		return response

	def post_list(self, request, **kwargs):
		self.method_check(request, allowed=['post'])
		response = self.getRisk(request)
		return self.create_response(request, response)  

# def getFloodriskStatistic(request,filterLock, flag, code, yy=None, mm=None, dd=None, rf_type=None, bring=None):
# 	response = getFloodRisk(request,filterLock, flag, code)

# 	return response

class FloodStatisticResource(ModelResource):

	class Meta:
		# authorization = DjangoAuthorization()
		resource_name = 'statistic_flood'
		allowed_methods = ['post']
		detail_allowed_methods = ['post']
		cache = SimpleCache()
		object_class=None
		# always_return_data = True
 
	def getRisk(self, request):

		p = urlparse(request.META.get('HTTP_REFERER')).path.split('/')
		mapCode = p[3] if 'v2' in p else p[2]
		map_obj = _resolve_map(request, mapCode, 'base.view_resourcebase', _PERMISSION_MSG_VIEW)

		queryset = matrix(user=request.user,resourceid=map_obj,action='Interactive Calculation')
		queryset.save()

		boundaryFilter = json.loads(request.body)

		wkts = ['ST_GeomFromText(\'%s\',4326)'%(i) for i in boundaryFilter['spatialfilter']]
		bring = wkts[-1] if len(wkts) else None
		filterLock = 'ST_Union(ARRAY[%s])'%(','.join(wkts))

		# d = datetime.datetime.strptime('2018-09-11','%Y-%m-%d')
		# yy, mm, dd = [d.year, d.month, d.day] if (datetime.datetime.today() - d).days > 0 else [None, None, None]

		response = getFloodStatistic(request, filterLock, boundaryFilter.get('flag'), boundaryFilter.get('code'), date=boundaryFilter.get('date'), rf_types=[boundaryFilter.get('rf_types')])

		return response

	def post_list(self, request, **kwargs):
		self.method_check(request, allowed=['post'])
		response = self.getRisk(request)
		return self.create_response(request, response)  

def dashboard_floodrisk(request, filterLock, flag, code, includes=['getCommonUse','baseline','pop_lc','area_lc','building_lc','adm_lc','adm_hlt_road','GeoJson'], excludes=[]):

	response = dict_ext()

	if include_section('getCommonUse', includes, excludes):
		response.update(getCommonUse(request, flag, code))

	response['source'] = getFloodRisk(request, filterLock, flag, code, includes, excludes)
	response['panels'] = panels = dict_ext()
	baseline = response['source']['baseline']
	floodrisk = response['source']['floodrisk']

	for p in ['pop','building','area']:
		panels.path(p+'_depth')['value'] = [floodrisk[p+'_depth'].get(d) or 0 for d in DEPTH_INDEX.values()]
		panels.path(p+'_depth')['total_atrisk'] = total_atrisk = sum(panels.path(p+'_depth')['value'])
		panels.path(p+'_depth')['total'] = total = baseline[p+'_total']
		panels.path(p+'_depth')['value'].append(total-total_atrisk) # value not at risk
		panels.path(p+'_depth')['title'] = [DEPTH_TYPES_SIMPLE[d] for d in DEPTH_INDEX.values()] + ['Not at risk']
		panels.path(p+'_depth')['percent'] = [floodrisk[p+'_depth_percent'].get(d) or 0 for d in DEPTH_INDEX.values()]
		panels.path(p+'_depth')['percent'].append(100-sum(panels.path(p+'_depth')['percent'])) # percent not at risk
		panels.path(p+'_depth')['child'] = [[DEPTH_TYPES_SIMPLE[d], floodrisk[p+'_depth'].get(d)] for d in DEPTH_INDEX.values()]
		panels.path(p+'_depth')['child'].append(['Not at risk',total-total_atrisk]) # percent not at risk

	if include_section('adm_lc', includes, excludes):
		response['adm_lc'] = baseline['adm_lc']
		panels['adm_lcgroup_pop_area'] = {
			# 'title':_('Overview of Population and Area'),
			'parentdata':[
				response['parent_label'],
				baseline['building_total'],
				baseline['settlement_total'],
				baseline['pop_lcgroup']['built_up'],
				baseline['area_lcgroup']['built_up'],
				baseline['pop_lcgroup']['cultivated'],
				baseline['area_lcgroup']['cultivated'],
				baseline['pop_lcgroup']['barren'],
				baseline['area_lcgroup']['barren'],
				baseline['pop_total'],
				baseline['area_total'],
			],
			'child':[{
				'value':[
					v['na_en'],
					v['total_buildings'],
					v['settlements'],
					v['built_up_pop'],
					v['built_up_area'],
					v['cultivated_pop'],
					v['cultivated_area'],
					v['barren_land_pop'],
					v['barren_land_area'],
					v['Population'],
					v['Area'],
				],
				'code':v['code'],
			} for v in baseline['adm_lc']],
		}

	if include_section('GeoJson', includes, excludes):
		response['GeoJson'] = geojsonadd_floodrisk(response)

	return response

def dashboard_floodforecast(request, filterLock, flag, code, includes=[], excludes=[], date='', rf_types=None):

	date = date or request.GET.get('date')
	response = dict_ext(getFloodForecast(request, filterLock, flag, code, rf_types=rf_types, date=date))
	panels = response.path('panels')

	if include_section('getCommonUse', includes, excludes):
		response.update(getCommonUse(request, flag, code))

	# baseline = response['source']['baseline']
	# floodforecast = response['source']['floodforecast']

	LIKELIHOOD_INDEX_EXC_VERYLOW_REVERSED = LIKELIHOOD_INDEX.values()[::-1]
	LIKELIHOOD_INDEX_EXC_VERYLOW_REVERSED.remove('verylow')
	
	panels['flashflood_likelihood_table'] = {
		'title': _('Flash Flood Likelihood'),
		'child': [{
			'title': LIKELIHOOD_TYPES[v],
			'pop': response['pop_flashflood_likelihood'][v],
			'building': response['building_flashflood_likelihood'][v],
			'depth_child': [{
				'title': DEPTH_TYPES_SIMPLE[d],
				'pop': response['pop_flashflood_likelihood_depth'][v][d],
				'building': response['building_flashflood_likelihood_depth'][v][d],
			} for d in DEPTH_INDEX.values()[::-1]],
		} for v in LIKELIHOOD_INDEX_EXC_VERYLOW_REVERSED]
	}

	panels['flashflood_likelihood_chart'] = {
		'title': _('Flash Flood Likelihood'),
		'child': [{
			'title': LIKELIHOOD_TYPES[v],
			'pop': response['pop_flashflood_likelihood'][v],
			'depth_child': [{
				'title': DEPTH_TYPES_SIMPLE[d],
				'pop': response['pop_flashflood_likelihood_depth'][v][d],
			} for d in DEPTH_INDEX.values()],
		} for v in LIKELIHOOD_INDEX_EXC_VERYLOW_REVERSED[::-1]]
	}

	for k,j in response['bysource'].items():

		panels.path('riverflood',k)['key'] = k
		panels.path('riverflood',k)['title'] = k

		panels.path('riverflood',k)['riverflood_likelihood_table'] = {
			'title': _('River Flood Likelihood'),
			'child': [{
				'title': LIKELIHOOD_TYPES[v],
				'pop': j['pop_riverflood_likelihood_subtotal'][v],
				'building': j['building_riverflood_likelihood_subtotal'][v],
				'depth_child': [{
					'title': DEPTH_TYPES_SIMPLE[d],
					'pop': j['pop_riverflood_likelihood_depth'][v][d],
					'building': j['building_riverflood_likelihood_depth'][v][d],
				} for d in DEPTH_INDEX.values()[::-1]],
			} for v in LIKELIHOOD_INDEX_EXC_VERYLOW_REVERSED]
		}

		panels.path('riverflood',k)['riverflood_likelihood_chart'] = {
			'title': _('Flash Flood Likelihood'),
			'child': [{
				'title': LIKELIHOOD_TYPES[v],
				'pop': j['pop_riverflood_likelihood_subtotal'][v],
				'depth_child': [{
					'title': DEPTH_TYPES_SIMPLE[d],
					'pop': j['pop_riverflood_likelihood_depth'][v][d],
				} for d in DEPTH_INDEX.values()],
			} for v in LIKELIHOOD_INDEX_EXC_VERYLOW_REVERSED[::-1]]
		}

		panels.path('riverflood',k)['flood_likelihood_overview_table'] = {
			'title': _('Flood Likelihood Overview'),
			'child': [{
				'code': v['code'],
				'value': [
					v['na_en'],
					v['flashflood_forecast_extreme_pop'],
					v['flashflood_forecast_veryhigh_pop'],
					v['flashflood_forecast_high_pop'],
					v['flashflood_forecast_med_pop'],
					v['flashflood_forecast_low_pop'],
					v['riverflood_forecast_extreme_pop'],
					v['riverflood_forecast_veryhigh_pop'],
					v['riverflood_forecast_high_pop'],
					v['riverflood_forecast_med_pop'],
					v['riverflood_forecast_low_pop'],
			]} for v in response['child_bysource'][k]]
		}

	if include_section('GeoJson', includes, excludes):
		response['GeoJson'] = geojsonadd_floodforecast(response)

	return response

def getFloodForecastBySource(sourceType, targetRisk, filterLock, flag, code, YEAR, MONTH, DAY, **kwargs):
	'''
	kwargs:
		formatted (BOOLEAN): if true return response in multi dictionary format
		init_response (DICT): initial response value
	'''
	# DAY = int(DAY)-1
	if sourceType == None:
		sourceType = 'gfms'

	response = kwargs.get('init_response', dict_ext())
	if sourceType == 'gfms':
		# River Flood Forecasted (GFMS)
		counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='riverflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY)), filterLock, 'basinmember__basins__riskstate', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, 'afg_fldzonea_100k_risk_landcover_pop')

		temp = dict([(c['basinmember__basins__riskstate'], c['count']) for c in counts])
		response['riverflood_forecast_verylow_pop']=round(temp.get(1, 0) or 0,0) 
		response['riverflood_forecast_low_pop']=round(temp.get(2, 0) or 0,0) 
		response['riverflood_forecast_med_pop']=round(temp.get(3, 0) or 0,0) 
		response['riverflood_forecast_high_pop']=round(temp.get(4, 0) or 0,0) 
		response['riverflood_forecast_veryhigh_pop']=round(temp.get(5, 0) or 0,0) 
		response['riverflood_forecast_extreme_pop']=round(temp.get(6, 0) or 0,0) 
		response['total_riverflood_forecast_pop']=response['riverflood_forecast_verylow_pop'] + response['riverflood_forecast_low_pop'] + response['riverflood_forecast_med_pop'] + response['riverflood_forecast_high_pop'] + response['riverflood_forecast_veryhigh_pop'] + response['riverflood_forecast_extreme_pop']

		temp = dict([(c['basinmember__basins__riskstate'], c['areaatrisk']) for c in counts])
		response['riverflood_forecast_verylow_area']=round((temp.get(1, 0) or 0)/1000000,0) 
		response['riverflood_forecast_low_area']=round((temp.get(2, 0) or 0)/1000000,0) 
		response['riverflood_forecast_med_area']=round((temp.get(3, 0) or 0)/1000000,0) 
		response['riverflood_forecast_high_area']=round((temp.get(4, 0) or 0)/1000000,0) 
		response['riverflood_forecast_veryhigh_area']=round((temp.get(5, 0) or 0)/1000000,0) 
		response['riverflood_forecast_extreme_area']=round((temp.get(6, 0) or 0)/1000000,0) 
		response['total_riverflood_forecast_area']=response['riverflood_forecast_verylow_area'] + response['riverflood_forecast_low_area'] + response['riverflood_forecast_med_area'] + response['riverflood_forecast_high_area'] + response['riverflood_forecast_veryhigh_area'] + response['riverflood_forecast_extreme_area']

		# Number of Building on river flood forecast
		temp = dict([(c['basinmember__basins__riskstate'], c['houseatrisk']) for c in counts])
		response['riverflood_forecast_verylow_buildings']=round(temp.get(1, 0) or 0,0) 
		response['riverflood_forecast_low_buildings']=round(temp.get(2, 0) or 0,0) 
		response['riverflood_forecast_med_buildings']=round(temp.get(3, 0) or 0,0) 
		response['riverflood_forecast_high_buildings']=round(temp.get(4, 0) or 0,0) 
		response['riverflood_forecast_veryhigh_buildings']=round(temp.get(5, 0) or 0,0) 
		response['riverflood_forecast_extreme_buildings']=round(temp.get(6, 0) or 0,0) 
		response['total_riverflood_forecast_buildings']=response['riverflood_forecast_verylow_buildings'] + response['riverflood_forecast_low_buildings'] + response['riverflood_forecast_med_buildings'] + response['riverflood_forecast_high_buildings'] + response['riverflood_forecast_veryhigh_buildings'] + response['riverflood_forecast_extreme_buildings']

		# flood risk and riverflood forecast matrix
		px = getFloodForecastRisk(filterLock, flag, code, targetRisk, YEAR, MONTH, DAY, floodtype='riverflood')
		# px = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='riverflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY))

		# annotates = {
		# 	'counter':Count('ogc_fid'),
		# 	'pop':Sum('fldarea_population'),
		# 	'building':Sum('area_buildings'),
		# }

		# if flag=='entireAfg': 
		# 	px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates)
		# 	# px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
		# 	#     select={
		# 	#         'pop' : 'SUM(fldarea_population)',
		# 	#         'building' : 'SUM(area_buildings)'
		# 	#     }).values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		# elif flag=='currentProvince':
		# 	ff0001 =  "left(cast(dist_code as text),%s) = '%s'"%(len(str(code)), code)
		# 	# if len(str(code)) > 2:
		# 	#     ff0001 =  "dist_code  = '"+str(code)+"'"
		# 	# else :
		# 	#     if len(str(code))==1:
		# 	#         ff0001 =  "left(cast(dist_code as text),1)  = '"+str(code)+"'"
		# 	#     else:
		# 	#         ff0001 =  "left(cast(dist_code as text),2)  = '"+str(code)+"'"   
		# 	px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where={ff0001})
		# 	# px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
		# 	#     select={
		# 	#         'pop' : 'SUM(fldarea_population)',
		# 	#         'building' : 'SUM(area_buildings)'
		# 	#     },where={
		# 	#         ff0001
		# 	#     }).values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		# elif flag=='drawArea':
		# 	sum_tpl = '\
		# 		SUM(  \
		# 			case \
		# 				when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,{filterLock}) then {area_field} \
		# 				else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,{filterLock})) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* {area_field} \
		# 			end \
		# 		)'
		# 	annotates = {
		# 		'counter':Count('ogc_fid'),
		# 		'pop':RawSQL_nogroupby(sum_tpl.format({'filterLock':filterLock,'area_field':'fldarea_population'}),()),
		# 		'building':RawSQL_nogroupby(sum_tpl.format({'filterLock':filterLock,'area_field':'area_buildings'}),()),
		# 	}
		# 	px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where = {'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'})
		# 	# px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
		# 	# 	select={
		# 	# 		'pop' : 'SUM(  \
		# 	# 				case \
		# 	# 					when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then fldarea_population \
		# 	# 					else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* fldarea_population end \
		# 	# 			)',
		# 	# 		'building' : 'SUM(  \
		# 	# 				case \
		# 	# 					when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then area_buildings \
		# 	# 					else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* area_buildings end \
		# 	# 			)'
		# 	# 	},
		# 	# 	where = {
		# 	# 		'ST_Intersects(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
		# 	# 	}).values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')  
		# else:
		# 	px = px.values('basinmember__basins__riskstate','deeperthan').annotate(**annotates).extra(where = {'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'})
		# 	# px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
		# 	# 	select={
		# 	# 		'pop' : 'SUM(fldarea_population)',
		# 	# 		'building' : 'SUM(area_buildings)'
		# 	# 	},
		# 	# 	where = {
		# 	# 		'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
		# 	# 	}).values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')      

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 1 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_verylow_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_verylow_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_verylow_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_verylow_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_verylow_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_verylow_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 2 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_low_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_low_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0) 
		response['riverflood_forecast_low_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_low_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_low_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0) 
		response['riverflood_forecast_low_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 3 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_med_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_med_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_med_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0) 
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_med_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_med_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_med_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0) 

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 4 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_high_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_high_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_high_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_high_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_high_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_high_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 5 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_veryhigh_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_veryhigh_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_veryhigh_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_veryhigh_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_veryhigh_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_veryhigh_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 6 ]
		temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		response['riverflood_forecast_extreme_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_extreme_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_extreme_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		response['riverflood_forecast_extreme_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		response['riverflood_forecast_extreme_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		response['riverflood_forecast_extreme_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

	elif sourceType=='glofas':
		if not code:
			code = 'NULL'
		cursor = connections['geodb'].cursor()
		sql = "select \
		coalesce(round(sum(extreme)),0) as riverflood_forecast_extreme_pop, \
		coalesce(round(sum(veryhigh)),0) as riverflood_forecast_veryhigh_pop, \
		coalesce(round(sum(high)),0) as riverflood_forecast_high_pop, \
		coalesce(round(sum(moderate)),0) as riverflood_forecast_med_pop, \
		coalesce(round(sum(low)),0) as riverflood_forecast_low_pop, \
		coalesce(round(sum(verylow)),0) as riverflood_forecast_verylow_pop, \
		coalesce(round(sum(extreme_high)),0) as riverflood_forecast_extreme_risk_high_pop, \
		coalesce(round(sum(extreme_med)),0) as riverflood_forecast_extreme_risk_med_pop, \
		coalesce(round(sum(extreme_low)),0) as riverflood_forecast_extreme_risk_low_pop, \
		coalesce(round(sum(veryhigh_high)),0) as riverflood_forecast_veryhigh_risk_high_pop, \
		coalesce(round(sum(veryhigh_med)),0) as riverflood_forecast_veryhigh_risk_med_pop, \
		coalesce(round(sum(veryhigh_low)),0) as riverflood_forecast_veryhigh_risk_low_pop, \
		coalesce(round(sum(high_high)),0) as riverflood_forecast_high_risk_high_pop, \
		coalesce(round(sum(high_med)),0) as riverflood_forecast_high_risk_med_pop, \
		coalesce(round(sum(high_low)),0) as riverflood_forecast_high_risk_low_pop, \
		coalesce(round(sum(moderate_high)),0) as riverflood_forecast_med_risk_high_pop, \
		coalesce(round(sum(moderate_med)),0) as riverflood_forecast_med_risk_med_pop, \
		coalesce(round(sum(moderate_low)),0) as riverflood_forecast_med_risk_low_pop,\
		coalesce(round(sum(low_high)),0) as riverflood_forecast_low_risk_high_pop, \
		coalesce(round(sum(low_med)),0) as riverflood_forecast_low_risk_med_pop, \
		coalesce(round(sum(low_low)),0) as riverflood_forecast_low_risk_low_pop, \
		coalesce(round(sum(verylow_high)),0) as riverflood_forecast_verylow_risk_high_pop, \
		coalesce(round(sum(verylow_med)),0) as riverflood_forecast_verylow_risk_med_pop, \
		coalesce(round(sum(verylow_low)),0) as riverflood_forecast_verylow_risk_low_pop, \
		coalesce(round(sum(extreme_area)::numeric,1)::double precision,0) as riverflood_forecast_extreme_area, \
		coalesce(round(sum(veryhigh_area)::numeric,1)::double precision,0) as riverflood_forecast_veryhigh_area, \
		coalesce(round(sum(high_area)::numeric,1)::double precision,0) as riverflood_forecast_high_area, \
		coalesce(round(sum(moderate_area)::numeric,1)::double precision,0) as riverflood_forecast_med_area, \
		coalesce(round(sum(low_area)::numeric,1)::double precision,0) as riverflood_forecast_low_area, \
		coalesce(round(sum(verylow_area)::numeric,1)::double precision,0) as riverflood_forecast_verylow_area, \
		coalesce(round(sum(extreme_buildings)),0) as riverflood_forecast_extreme_buildings, \
		coalesce(round(sum(veryhigh_buildings)),0) as riverflood_forecast_veryhigh_buildings, \
		coalesce(round(sum(high_buildings)),0) as riverflood_forecast_high_buildings, \
		coalesce(round(sum(moderate_buildings)),0) as riverflood_forecast_med_buildings, \
		coalesce(round(sum(low_buildings)),0) as riverflood_forecast_low_buildings, \
		coalesce(round(sum(verylow_buildings)),0) as riverflood_forecast_verylow_buildings, \
		coalesce(round(sum(extreme_high_buildings)),0) as riverflood_forecast_extreme_risk_high_buildings, \
		coalesce(round(sum(extreme_med_buildings)),0) as riverflood_forecast_extreme_risk_med_buildings, \
		coalesce(round(sum(extreme_low_buildings)),0) as riverflood_forecast_extreme_risk_low_buildings, \
		coalesce(round(sum(veryhigh_high_buildings)),0) as riverflood_forecast_veryhigh_risk_high_buildings, \
		coalesce(round(sum(veryhigh_med_buildings)),0) as riverflood_forecast_veryhigh_risk_med_buildings, \
		coalesce(round(sum(veryhigh_low_buildings)),0) as riverflood_forecast_veryhigh_risk_low_buildings, \
		coalesce(round(sum(high_high_buildings)),0) as riverflood_forecast_high_risk_high_buildings, \
		coalesce(round(sum(high_med_buildings)),0) as riverflood_forecast_high_risk_med_buildings, \
		coalesce(round(sum(high_low_buildings)),0) as riverflood_forecast_high_risk_low_buildings, \
		coalesce(round(sum(moderate_high_buildings)),0) as riverflood_forecast_med_risk_high_buildings, \
		coalesce(round(sum(moderate_med_buildings)),0) as riverflood_forecast_med_risk_med_buildings, \
		coalesce(round(sum(moderate_low_buildings)),0) as riverflood_forecast_med_risk_low_buildings,\
		coalesce(round(sum(low_high_buildings)),0) as riverflood_forecast_low_risk_high_buildings, \
		coalesce(round(sum(low_med_buildings)),0) as riverflood_forecast_low_risk_med_buildings, \
		coalesce(round(sum(low_low_buildings)),0) as riverflood_forecast_low_risk_low_buildings, \
		coalesce(round(sum(verylow_high_buildings)),0) as riverflood_forecast_verylow_risk_high_buildings, \
		coalesce(round(sum(verylow_med_buildings)),0) as riverflood_forecast_verylow_risk_med_buildings, \
		coalesce(round(sum(verylow_low_buildings)),0) as riverflood_forecast_verylow_risk_low_buildings \
		from get_glofas(date('%s-%s-%s')-1,'%s',%s,'%s')" %(YEAR,MONTH,DAY,flag,code,filterLock)
		row = query_to_dicts(cursor, sql)
		for item in row:
			# response = item
			response.update(item)
		response['total_riverflood_forecast_pop']=response['riverflood_forecast_verylow_pop'] if response['riverflood_forecast_verylow_pop'] else 0 + response['riverflood_forecast_low_pop'] if response['riverflood_forecast_low_pop'] else 0 + response['riverflood_forecast_med_pop'] if response['riverflood_forecast_med_pop'] else 0 + response['riverflood_forecast_high_pop'] if response['riverflood_forecast_high_pop'] else 0 + response['riverflood_forecast_veryhigh_pop'] if response['riverflood_forecast_veryhigh_pop'] else 0 + response['riverflood_forecast_extreme_pop'] if response['riverflood_forecast_extreme_pop'] else 0
		response['total_riverflood_forecast_area']=response['riverflood_forecast_verylow_area'] if response['riverflood_forecast_verylow_area'] else 0 + response['riverflood_forecast_low_area'] if response['riverflood_forecast_low_area'] else 0 + response['riverflood_forecast_med_area'] if response['riverflood_forecast_med_area'] else 0 + response['riverflood_forecast_high_area'] if response['riverflood_forecast_high_area'] else 0 + response['riverflood_forecast_veryhigh_area'] if response['riverflood_forecast_veryhigh_area'] else 0 + response['riverflood_forecast_extreme_area'] if response['riverflood_forecast_extreme_area'] else 0
		response['total_riverflood_forecast_buildings']=response['riverflood_forecast_verylow_buildings'] if response['riverflood_forecast_verylow_buildings'] else 0 + response['riverflood_forecast_low_buildings'] if response['riverflood_forecast_low_buildings'] else 0 + response['riverflood_forecast_med_buildings'] if response['riverflood_forecast_med_buildings'] else 0 + response['riverflood_forecast_high_buildings'] if response['riverflood_forecast_high_buildings'] else 0 + response['riverflood_forecast_veryhigh_buildings'] if response['riverflood_forecast_veryhigh_buildings'] else 0 + response['riverflood_forecast_extreme_buildings'] if response['riverflood_forecast_extreme_buildings'] else 0
		cursor.close()

	elif sourceType=='gfms_glofas':
		if not code:
			code = 'NULL'
		cursor = connections['geodb'].cursor()
		sql = "select \
		coalesce(round(sum(extreme)),0) as riverflood_forecast_extreme_pop, \
		coalesce(round(sum(veryhigh)),0) as riverflood_forecast_veryhigh_pop, \
		coalesce(round(sum(high)),0) as riverflood_forecast_high_pop, \
		coalesce(round(sum(moderate)),0) as riverflood_forecast_med_pop, \
		coalesce(round(sum(low)),0) as riverflood_forecast_low_pop, \
		coalesce(round(sum(verylow)),0) as riverflood_forecast_verylow_pop, \
		coalesce(round(sum(extreme_high)),0) as riverflood_forecast_extreme_risk_high_pop, \
		coalesce(round(sum(extreme_med)),0) as riverflood_forecast_extreme_risk_med_pop, \
		coalesce(round(sum(extreme_low)),0) as riverflood_forecast_extreme_risk_low_pop, \
		coalesce(round(sum(veryhigh_high)),0) as riverflood_forecast_veryhigh_risk_high_pop, \
		coalesce(round(sum(veryhigh_med)),0) as riverflood_forecast_veryhigh_risk_med_pop, \
		coalesce(round(sum(veryhigh_low)),0) as riverflood_forecast_veryhigh_risk_low_pop, \
		coalesce(round(sum(high_high)),0) as riverflood_forecast_high_risk_high_pop, \
		coalesce(round(sum(high_med)),0) as riverflood_forecast_high_risk_med_pop, \
		coalesce(round(sum(high_low)),0) as riverflood_forecast_high_risk_low_pop, \
		coalesce(round(sum(moderate_high)),0) as riverflood_forecast_med_risk_high_pop, \
		coalesce(round(sum(moderate_med)),0) as riverflood_forecast_med_risk_med_pop, \
		coalesce(round(sum(moderate_low)),0) as riverflood_forecast_med_risk_low_pop,\
		coalesce(round(sum(low_high)),0) as riverflood_forecast_low_risk_high_pop, \
		coalesce(round(sum(low_med)),0) as riverflood_forecast_low_risk_med_pop, \
		coalesce(round(sum(low_low)),0) as riverflood_forecast_low_risk_low_pop, \
		coalesce(round(sum(verylow_high)),0) as riverflood_forecast_verylow_risk_high_pop, \
		coalesce(round(sum(verylow_med)),0) as riverflood_forecast_verylow_risk_med_pop, \
		coalesce(round(sum(verylow_low)),0) as riverflood_forecast_verylow_risk_low_pop, \
		coalesce(round(sum(extreme_area)::numeric,1)::double precision,0) as riverflood_forecast_extreme_area, \
		coalesce(round(sum(veryhigh_area)::numeric,1)::double precision,0) as riverflood_forecast_veryhigh_area, \
		coalesce(round(sum(high_area)::numeric,1)::double precision,0) as riverflood_forecast_high_area, \
		coalesce(round(sum(moderate_area)::numeric,1)::double precision,0) as riverflood_forecast_med_area, \
		coalesce(round(sum(low_area)::numeric,1)::double precision,0) as riverflood_forecast_low_area, \
		coalesce(round(sum(verylow_area)::numeric,1)::double precision,0) as riverflood_forecast_verylow_area, \
		coalesce(round(sum(extreme_buildings)),0) as riverflood_forecast_extreme_buildings, \
		coalesce(round(sum(veryhigh_buildings)),0) as riverflood_forecast_veryhigh_buildings, \
		coalesce(round(sum(high_buildings)),0) as riverflood_forecast_high_buildings, \
		coalesce(round(sum(moderate_buildings)),0) as riverflood_forecast_med_buildings, \
		coalesce(round(sum(low_buildings)),0) as riverflood_forecast_low_buildings, \
		coalesce(round(sum(verylow_buildings)),0) as riverflood_forecast_verylow_buildings, \
		coalesce(round(sum(extreme_high_buildings)),0) as riverflood_forecast_extreme_risk_high_buildings, \
		coalesce(round(sum(extreme_med_buildings)),0) as riverflood_forecast_extreme_risk_med_buildings, \
		coalesce(round(sum(extreme_low_buildings)),0) as riverflood_forecast_extreme_risk_low_buildings, \
		coalesce(round(sum(veryhigh_high_buildings)),0) as riverflood_forecast_veryhigh_risk_high_buildings, \
		coalesce(round(sum(veryhigh_med_buildings)),0) as riverflood_forecast_veryhigh_risk_med_buildings, \
		coalesce(round(sum(veryhigh_low_buildings)),0) as riverflood_forecast_veryhigh_risk_low_buildings, \
		coalesce(round(sum(high_high_buildings)),0) as riverflood_forecast_high_risk_high_buildings, \
		coalesce(round(sum(high_med_buildings)),0) as riverflood_forecast_high_risk_med_buildings, \
		coalesce(round(sum(high_low_buildings)),0) as riverflood_forecast_high_risk_low_buildings, \
		coalesce(round(sum(moderate_high_buildings)),0) as riverflood_forecast_med_risk_high_buildings, \
		coalesce(round(sum(moderate_med_buildings)),0) as riverflood_forecast_med_risk_med_buildings, \
		coalesce(round(sum(moderate_low_buildings)),0) as riverflood_forecast_med_risk_low_buildings,\
		coalesce(round(sum(low_high_buildings)),0) as riverflood_forecast_low_risk_high_buildings, \
		coalesce(round(sum(low_med_buildings)),0) as riverflood_forecast_low_risk_med_buildings, \
		coalesce(round(sum(low_low_buildings)),0) as riverflood_forecast_low_risk_low_buildings, \
		coalesce(round(sum(verylow_high_buildings)),0) as riverflood_forecast_verylow_risk_high_buildings, \
		coalesce(round(sum(verylow_med_buildings)),0) as riverflood_forecast_verylow_risk_med_buildings, \
		coalesce(round(sum(verylow_low_buildings)),0) as riverflood_forecast_verylow_risk_low_buildings \
		from get_merge_glofas_gfms(date('%s-%s-%s'),'%s',%s,'%s')" %(YEAR,MONTH,DAY,flag,code,filterLock)
		print sql
		row = query_to_dicts(cursor, sql)
		for item in row:
			# response = item
			response.update(item)
		response['total_riverflood_forecast_pop']=response['riverflood_forecast_verylow_pop'] if response['riverflood_forecast_verylow_pop'] else 0 + response['riverflood_forecast_low_pop'] if response['riverflood_forecast_low_pop'] else 0 + response['riverflood_forecast_med_pop'] if response['riverflood_forecast_med_pop'] else 0 + response['riverflood_forecast_high_pop'] if response['riverflood_forecast_high_pop'] else 0 + response['riverflood_forecast_veryhigh_pop'] if response['riverflood_forecast_veryhigh_pop'] else 0 + response['riverflood_forecast_extreme_pop'] if response['riverflood_forecast_extreme_pop'] else 0
		response['total_riverflood_forecast_area']=response['riverflood_forecast_verylow_area'] if response['riverflood_forecast_verylow_area'] else 0 + response['riverflood_forecast_low_area'] if response['riverflood_forecast_low_area'] else 0 + response['riverflood_forecast_med_area'] if response['riverflood_forecast_med_area'] else 0 + response['riverflood_forecast_high_area'] if response['riverflood_forecast_high_area'] else 0 + response['riverflood_forecast_veryhigh_area'] if response['riverflood_forecast_veryhigh_area'] else 0 + response['riverflood_forecast_extreme_area'] if response['riverflood_forecast_extreme_area'] else 0
		cursor.close()

	# convert response to multi dictionary format
	if kwargs.get('formatted'):

		response_tree = dict_ext()
		MAINDATA_TYPES = {'pop':'pop','area':'area','buildings':'building'}

		# make base dict with default value zero
		response_tree.update({m+'_riverflood_likelihood_depth':{l:{d:0 for d in DEPTH_TYPES} for l in LIKELIHOOD_INDEX_INVERSE} for m in MAINDATA_TYPES.values()})

		for key, val in response.items():
			keys = list_ext(key.split('_'))
			if key.startswith('total_riverflood_forecast') and (keys.get(3) in MAINDATA_TYPES):
				response_tree['%s_riverflood_likelihood_total'%(MAINDATA_TYPES[keys[3]])] = val
			elif key.startswith('riverflood_forecast') and (keys.get(2) in LIKELIHOOD_INDEX_INVERSE) and (keys.get(3) in MAINDATA_TYPES):
				maindata, likelihood = MAINDATA_TYPES[keys[3]], keys[2]
				response_tree.path('%s_riverflood_likelihood_subtotal'%(maindata))[likelihood] = val
			elif key.startswith('riverflood_forecast') and (keys.get(2) in LIKELIHOOD_INDEX_INVERSE) and (keys.get(3) == 'risk') and (keys.get(4) in DEPTH_TYPES) and (keys.get(5) in MAINDATA_TYPES):
				maindata, likelihood, depth = MAINDATA_TYPES[keys[5]], keys[2], keys[4]
				response_tree.path('%s_riverflood_likelihood_depth'%(maindata),likelihood)[depth] = val
			else:
				response_tree.path('floodforecast')[key] = val

		response = response_tree

	return response

def geojsonadd_floodrisk(response):

	floodrisk = response['source']['floodrisk']
	baseline = response['source']['baseline']
	boundary = response['source']['baseline']['GeoJson']

	for feature in boundary['features']:

		# Checking if it's in a district
		if response['areatype'] == 'district':
			response['set_jenk_divider'] = 1
			feature['properties']['na_en']=response['parent_label']
			feature['properties']['total_risk_population']=floodrisk['pop_likelihood_total']
			feature['properties']['total_risk_buildings']=floodrisk['building_likelihood_total']
			feature['properties']['settlements_at_risk']=floodrisk['settlement_likelihood_total']
			feature['properties']['total_risk_area']=floodrisk['area_likelihood_total']

			feature['properties']['low_risk_population']=floodrisk['pop_depth']['low']
			feature['properties']['med_risk_population']=floodrisk['pop_depth']['med']
			feature['properties']['high_risk_population']=floodrisk['pop_depth']['high']

			feature['properties']['low_risk_area']=floodrisk['area_depth']['low']
			feature['properties']['med_risk_area']=floodrisk['area_depth']['med']
			feature['properties']['high_risk_area']=floodrisk['area_depth']['high']

		else:
			response['set_jenk_divider'] = 7
			for data in baseline.get('adm_lc',[]):
				if (feature['properties']['code']==data['code']):
					feature['properties']['na_en']=data['na_en']
					feature['properties']['total_risk_population']=data['total_risk_population']
					feature['properties']['total_risk_buildings']=data['total_risk_buildings']
					feature['properties']['settlements_at_risk']=data['settlements_at_risk']
					feature['properties']['total_risk_area']=data['total_risk_area']

					feature['properties']['low_risk_population']=data['low_risk_population']
					feature['properties']['med_risk_population']=data['med_risk_population']
					feature['properties']['high_risk_population']=data['high_risk_population']

					feature['properties']['low_risk_area']=data['low_risk_area']
					feature['properties']['med_risk_area']=data['med_risk_area']
					feature['properties']['high_risk_area']=data['high_risk_area']

	return boundary

def geojsonadd_floodforecast(response):

	boundary = response['GeoJson']
	response['child_bysource_dict'] = {k:{data['code']:data for data in v} for k,v in response.get('child_bysource',{}).items()}

	LIKELIHOOD_INDEX_EXC_VERYLOW = LIKELIHOOD_INDEX.values()[::-1]
	LIKELIHOOD_INDEX_EXC_VERYLOW.remove('verylow')

	for k,v in enumerate(boundary['features']):
		boundary['features'][k]['properties'] = properties = dict_ext(boundary['features'][k]['properties'])
		if response['areatype'] == 'district':
			response['set_jenk_divider'] = 1
			properties['na_en'] = response['parent_label']
			properties['flashflood_forecast_pop'] = {k:response['pop_flashflood_likelihood'][k] for k in LIKELIHOOD_INDEX_EXC_VERYLOW}
			properties['value'] = 0
			for k,v in response['bysource'].items():
				k2 = '' if k == 'gfms' else k+'_'
				properties.update({'%sriverflood_forecast_%s_pop'%(k2,i):j for i,j in v['pop_riverflood_likelihood_subtotal'].items() if i is not 'verylow'})

		else:
			response['set_jenk_divider'] = 7
			for k,v in response.get('child_bysource_dict',{}).items():
				if (properties['code'] in v):
					data = v[properties['code']]
					k2 = '' if k == 'gfms' else k+'_'
					properties.update({'%sriverflood_forecast_%s_pop'%(k2,i):data['riverflood_forecast_%s_pop'%(i)] for i in LIKELIHOOD_INDEX_EXC_VERYLOW})
					if k == 'gfms':
						properties['na_en'] = data['na_en']
						properties['value'] = 0
						properties.update({'flashflood_forecast_%s_pop'%(i):data['flashflood_forecast_%s_pop'%(i)] for i in LIKELIHOOD_INDEX_EXC_VERYLOW})

				# for data in v:
				# 	if (properties['code'] == data['code']):
				# 		properties.path('bysource',k)['riverflood_forecast_pop'] = {k:data['riverflood_forecast_%s_pop'%(k)] for k in LIKELIHOOD_INDEX_EXC_VERYLOW}
				# 		if k == 'gfms':
				# 			properties['na_en'] = data['na_en']
				# 			properties['value'] = 0
				# 			properties['flashflood_forecast_pop'] = {k:data['flashflood_forecast_%s_pop'%(k)] for k in LIKELIHOOD_INDEX_EXC_VERYLOW}

			# for data in response.get('child_bysource',{}).get('gfms',[]):
			# 	if (feature['properties']['code']==data['code']):
			# 		feature['properties']['na_en']=data['na_en']
			# 		feature['properties']['value']=0
			# 		feature.path('properties')['flashflood_forecast_pop'] = {k:data['flashflood_forecast_%s_pop'%(k)] for k in LIKELIHOOD_INDEX_EXC_VERYLOW}
			# 		feature.path('properties','bysource','gfms')['riverflood_forecast_pop'] = {k:data['riverflood_forecast_%s_pop'%(k)] for k in LIKELIHOOD_INDEX_EXC_VERYLOW}

			# for data in response.get('child_bysource',{}).get('glofas',[]):
			# 	if (feature['properties']['code']==data['code']):
			# 		feature.path('properties','bysource','glofas')['riverflood_forecast_pop'] = {k:data['riverflood_forecast_%s_pop'%(k)] for k in LIKELIHOOD_INDEX_EXC_VERYLOW}

			# for data in response.get('child_bysource',{}).get('gfms_glofas',[]):
			# 	if (feature['properties']['code']==data['code']):
			# 		feature.path('properties','bysource','gfms_glofas')['riverflood_forecast_pop'] = {k:data['riverflood_forecast_%s_pop'%(k)] for k in LIKELIHOOD_INDEX_EXC_VERYLOW}

	return boundary

def getFloodriskStatistic(request,filterLock, flag, code):

	response_dashboard = dashboard_floodrisk(request, filterLock, flag, code)
	response = dict_ext()
	response['source'] = response_dashboard['source']

	PANEL_TITLES = {'pop_depth':'Population Graph','area_depth':'Area Graph','building_depth':'Building Graph','adm_lcgroup_pop_area':'Overview of Population and Area'}
	chart_order = ['pop_depth','building_depth','area_depth']
	response.path('panels_list')['charts'] = []
	for k in chart_order:
		p = {}
		p['child'] = [{'value':response_dashboard['panels'][k]['value'][i], 'percent':response_dashboard['panels'][k]['percent'][i], 'title':t} for i,t in enumerate(response_dashboard['panels'][k]['title'])]
		p['title'] = PANEL_TITLES.get(k)
		p['total'] = response_dashboard['panels'][k]['total']
		p['total_atrisk'] = response_dashboard['panels'][k]['total_atrisk']
		response['panels_list']['charts'].append(p)
	response.path('panels_list')['tables'] = [{
		'title':PANEL_TITLES.get(k),
		'child':[response_dashboard['panels'][k]['parentdata']]+[j['value'] for j in response_dashboard['panels'][k]['child']]
	} for k in ['adm_lcgroup_pop_area']]

	return response

def getFloodforecastStatistic(request,filterLock, flag, code, date=None, rf_types=[], bring=None):

	response = {'panels':dashboard_floodforecast(request, filterLock, flag, code, date=date, rf_types=rf_types)['panels']}
	return response

def getFloodStatistic(request,filterLock, flag, code, date=None, rf_types=[]):

	response = {
		'floodrisk': getFloodriskStatistic(request,filterLock, flag, code),
		'floodforecast': getFloodforecastStatistic(request,filterLock, flag, code, date=date, rf_types=rf_types),
	}

	return response
