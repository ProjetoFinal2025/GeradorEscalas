from django.urls import path
from django.views.generic import RedirectView
from .views import login_view, home_view

urlpatterns = [
    path('', RedirectView.as_view(url='login/', permanent=False)),
    path('login/', login_view, name='login'),
    path('home/', home_view, name='home'),
]
