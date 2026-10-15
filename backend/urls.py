from django.urls import path
from routing.views import routes, health, cities

urlpatterns = [
    path("api/routes", routes),
    path("api/health", health),
    path("api/cities", cities),
]
