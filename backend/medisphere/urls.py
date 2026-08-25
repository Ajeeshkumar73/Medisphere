from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('add_review/', views.add_review, name='add_review'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password Reset URLs
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='password_reset_form.html',
        email_template_name='password_reset_email.html',
        subject_template_name='password_reset_subject.txt',
        success_url='/password_reset/done/'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='password_reset_confirm.html',
        success_url='/reset/done/'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='password_reset_complete.html'
    ), name='password_reset_complete'),

    path('profile/', views.user_profile_view, name='user_profile'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('medical-records/', views.medical_reports_view, name='medical_reports'),
    path('medical-records/upload/', views.upload_document_view, name='upload_document'),
    path('medical-records/delete/<int:doc_id>/', views.delete_document_view, name='delete_document'),

    # User-facing pharmacy views
    path('pharmacy/', views.user_pharmacy_view, name='user_pharmacy'),
    path('pharmacy/order/', views.place_order_view, name='place_order'),
    path('pharmacy/prescription/', views.upload_prescription_order_view, name='upload_prescription_order'),

    # Pharmacy-facing dashboard views
    path('pharmacy/dashboard/', views.pharmacy_dashboard_view, name='pharmacy_dashboard'),
    path('pharmacy/medicine/add/', views.add_medicine_view, name='add_medicine'),
    path('pharmacy/medicine/delete/<int:med_id>/', views.delete_medicine_view, name='delete_medicine'),
    path('pharmacy/order/update/<int:order_id>/', views.update_order_status_view, name='update_order_status'),
    path('pharmacy/prescription/update/<int:pres_id>/', views.update_prescription_status_view, name='update_prescription_status'),
    path('pharmacy/medicine/import/', views.bulk_upload_medicines_view, name='bulk_upload_medicines'),

    # Lab-facing dashboard views
    path('lab/dashboard/', views.lab_dashboard_view, name='lab_dashboard'),
    path('lab/test/add/', views.add_lab_test_view, name='add_lab_test'),
    path('lab/test/delete/<int:test_id>/', views.delete_lab_test_view, name='delete_lab_test'),
    path('lab/appointment/update/<int:appt_id>/', views.update_appointment_status_view, name='update_appointment_status'),

    # Patient-facing lab views
    path('lab/', views.user_lab_view, name='user_lab'),
    path('lab/appointment/book/', views.book_appointment_view, name='book_appointment'),
    path('appointments/', views.user_appointments_view, name='user_appointments'),
    path('appointments/cancel/<int:appt_id>/', views.cancel_appointment_view, name='cancel_appointment'),
    path('appointments/medicine/cancel/<int:order_id>/', views.cancel_medicine_order_view, name='cancel_medicine_order'),

    # Notifications
    path('notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),

    # Global dashboard search
    path('search/', views.dashboard_search_view, name='dashboard_search'),

    # Expense Tracker
    path('expenses/', views.expenses_view, name='expenses'),
    # AI Analyser & Member Health Summary URLs
    path('AI_analyser/', views.ai_analyser, name='ai_analyser'),
    path('AI_analyser/qr_code/<str:member_type>/<int:member_id>/', views.ai_summary_qr_code, name='ai_summary_qr_code'),
    path('AI_analyser/qr/<str:member_type>/<int:member_id>/', views.ai_summary_qr_view, name='ai_summary_qr_view'),
    path('AI_analyser/download/<str:member_type>/<int:member_id>/', views.download_ai_summary, name='download_ai_summary'),
]