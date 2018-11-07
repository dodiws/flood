from django.conf.urls import include, patterns, url
from tastypie.api import Api
from .views import FloodRiskStatisticResource

api = Api(api_name='geoapi')

api.register(FloodRiskStatisticResource())

urlpatterns_getoverviewmaps = patterns(
    'flood.views',
    url(r'^floodinfo$', 'getFloodInfoVillages', name='getFloodInfoVillages'),
    url(r'^getGlofasChart$', 'getGlofasChart', name='getGlofasChart'),
    url(r'^getGlofasPointsJSON$', 'getGlofasPointsJSON', name='getGlofasPointsJSON'),    
)
urlpatterns = [
    # api
    url(r'', include(api.urls)),

    url(r'^getOverviewMaps/', include(urlpatterns_getoverviewmaps)),
]
