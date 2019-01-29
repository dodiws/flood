from django.conf.urls import include, patterns, url
from tastypie.api import Api
from .views import (
    FloodRiskStatisticResource,
    FloodForecastStatisticResource,
    FloodStatisticResource,
    FLoodInfoVillages 
)

api = Api(api_name='geoapi')

api.register(FloodRiskStatisticResource())
api.register(FloodForecastStatisticResource())
api.register(FloodStatisticResource())

GETOVERVIEWMAPS_APIOBJ = [
    FLoodInfoVillages(),
]

urlpatterns = [
    url(r'', include(api.urls)),
    url(r'^getOverviewMaps/', include(patterns(
        'flood.views',
        url(r'^floodinfo$', 'getFloodInfoVillages', name='getFloodInfoVillages'),
        url(r'^getGlofasChart$', 'getGlofasChart', name='getGlofasChart'),
        url(r'^getGlofasPointsJSON$', 'getGlofasPointsJSON', name='getGlofasPointsJSON'),    
    ))),
]
