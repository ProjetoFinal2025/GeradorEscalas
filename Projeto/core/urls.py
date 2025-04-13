from django.urls import path
from django.views.generic import RedirectView
from django.contrib.auth.views import LogoutView
from .views import login_view, home_view, mapa_dispensas_view

urlpatterns = [
    path('', RedirectView.as_view(url='login/', permanent=False)),
    path('login/', login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('home/', home_view, name='home'),
    path('mapa-dispensas/', mapa_dispensas_view, name='mapa_dispensas'),
]
