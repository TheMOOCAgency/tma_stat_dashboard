"""
STATdashboard API endpoint urls.
"""
from django.conf.urls import patterns, url
from django.conf import settings

urlpatterns = patterns (
    url(
        r'^courses/{}/stat_dashboard$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        'lms.djangoapps.tma_stat_dashboard.views.stat_dashboard',
        name='stat_dashboard',
    ),
    # return the score per users
    url(
        r'^courses/{}/stat_dashboard/get_grade/(?P<username>[^/]*)/$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        'lms.djangoapps.tma_stat_dashboard.views.stat_dashboard_username',
        name='stat_dashboard_username',
    ),
    # return average grades of differents blocks
    url(
        r'^courses/{}/stat_dashboard/get_course_blocks_grade/$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        'lms.djangoapps.tma_stat_dashboard.views.get_course_blocks_grade',
        name='get_course_blocks_grade',
    ),
    # return list of username for search input of stat_dashboard page
    url(
        r'^courses/{}/stat_dashboard/get_user/(?P<username>[^/]*)/$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        'lms.djangoapps.tma_stat_dashboard.views.get_dashboard_username',
        name='stat_dashboard_username_search',
    ),
    # grades
    url(
        r'^courses/{}/stat_dashboard/grade_reports/$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        'lms.djangoapps.tma_stat_dashboard.views.stat_grade_reports',
        name='stat_dashboard_username_search',
    ),
    # stat_dashboard_average_test
    url(
        r'^stat_dashboard/csv/(?P<filename>[^"]*)/$',
        'lms.djangoapps.tma_stat_dashboard.views.download_xls',
        name='stat_dashboard_dl_xls',
    ),
    url(
        r'^courses/{}/stat_dashboard/xls_grade_reports/$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        'lms.djangoapps.tma_stat_dashboard.views.calculate_grades_xls',
        name='calculate_grades_xls',
    )
 )
