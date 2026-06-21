from django.urls import path
from . import views
from .models import Event, Registration


urlpatterns = [
    path('', views.auth_view, name='auth'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('volunteer/', views.volunteer_view, name='volunteer'),
    path('save-profile/', views.save_profile_view, name='save_profile'), 
    path('logout/', views.logout_view, name='logout'),

    path(
        'join-event/<int:event_id>/',
        views.join_event,
        name='join_event'
    ),

    path(
        'cancel-registration/<int:registration_id>/',
        views.cancel_registration,
        name='cancel_registration'
    ),

    path(
        'certificate/<int:registration_id>/',
        views.certificate_view,
        name='certificate'
    ),

    path(
        'organization/',
        views.organization_view,
        name='organization'
    ),

    path(
        'terms/',
        views.terms_view,
        name='terms'
    ),

    path(
        'privacy/',
        views.privacy_view,
        name='privacy'
    ),

    path(
        'create-event/',
        views.create_event_view,
        name='create_event'
    ),

    path(
        'edit-event/<int:event_id>/',
        views.edit_event_view,
        name='edit_event'
    ),

    path(
        'delete-event/<int:event_id>/',
        views.delete_event_view,
        name='delete_event'
    ),

    path(
        'qr-image/<int:event_id>/',
        views.generate_qr_view,
        name='qr_image'
    ),

    path(
        'qr-info/<int:event_id>/',
        views.get_event_qr_info,
        name='qr_info'
    ),

    path(
        'complete-event/<int:event_id>/',
        views.complete_event_view,
        name='complete_event'
    ),

    path(
        'org-certificate/<int:registration_id>/',
        views.organization_certificate_view,
        name='org_certificate'
    ),

    path(
        'save-org-profile/',
        views.save_organization_profile_view,
        name='save_org_profile'
    ),

    path(
        'add-employee/',
        views.add_employee_view,
        name='add_employee'
    ),
    path(
        'delete-employee/<int:employee_id>/',
        views.delete_employee_view,
        name='delete_employee'
    ),
    path(
        'get-employees/',
        views.get_employees_view,
        name='get_employees'
    ),

    path(
        'event-employees/<int:event_id>/',
        views.event_employees_view,
        name='event_employees'
    ),

    path('checkin-qr/', views.checkin_qr_view, name='checkin_qr'),
    path('checkin-manual/', views.checkin_manual_view, name='checkin_manual'),
    path('event-employees-volunteer/<int:event_id>/', views.event_employees_for_volunteer, name='event_employees_volunteer'),

    path('change-password/', views.change_password_view, name='change_password'),
    
]


