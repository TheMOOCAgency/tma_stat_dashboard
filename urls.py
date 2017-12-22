"""
TMA DASHBOARD API endpoint urls.
"""

from django.conf.urls import url

from lms.djangoapps.instructor.views import api, gradebook_api
from django.conf import settings
from tma_stat_dashboard.views import tma_dashboard_views,tma_overall_users_views,tma_per_question_views,tma_create_user_from_csv,tma_ensure_email_username,task_user_grade_list,tma_cut_off_update

urlpatterns = (
    url(r'^dashboard$', tma_dashboard_views, name="tma_dashboard"),
    url(r'^overall_users_stats$', tma_overall_users_views, name="tma_overall_users_stats"),
    url(r'^per_question$', tma_per_question_views, name="tma_specific_users_stats"),
    url(r'^tma_dashboard_upload_csv$', tma_create_user_from_csv, name="tma_create_user_from_csv"),
    url(r'^ensure_user_exist$', tma_ensure_email_username, name="tma_ensure_email_username"),
    url(r'^task_user_grade_list$', task_user_grade_list, name="task_user_grade_list"),
    url(r'^tma_cut_off_update$', tma_cut_off_update, name="tma_cut_off_update"),
 )
