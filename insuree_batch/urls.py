from django.urls import path
from . import views

urlpatterns = [
    path('exportInsurees/', views.export_insurees, name='export_insurees'),
    path('batch_qr/', views.batch_qr, name='batch_qr'),
]
