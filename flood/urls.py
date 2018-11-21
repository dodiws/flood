from django.conf.urls import include, patterns, url
from tastypie.api import Api
from .views import FloodRiskStatisticResource, FloodForecastStatisticResource, FloodStatisticResource

api = Api(api_name='geoapi')

api.register(FloodRiskStatisticResource())
api.register(FloodForecastStatisticResource())
api.register(FloodStatisticResource())

urlpatterns_getoverviewmaps = patterns(
    'flood.views',
    url(r'^floodinfo$', 'getFloodInfoVillages', name='getFloodInfoVillages'),
    url(r'^getGlofasChart$', 'getGlofasChart', name='getGlofasChart'),
    url(r'^getGlofasPointsJSON$', 'getGlofasPointsJSON', name='getGlofasPointsJSON'),    
)
urlpatterns = [
    url(r'', include(api.urls)),
    url(r'^getOverviewMaps/', include(urlpatterns_getoverviewmaps)),
]
