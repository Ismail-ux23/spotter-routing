from django.urls import path
from routing.views import routes, health

urlpatterns = [path("api/routes", routes), path("api/health", health)]
