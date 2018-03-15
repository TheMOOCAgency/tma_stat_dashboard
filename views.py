# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf8')

"""
Instructor Dashboard Views
"""

import logging
import json

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST,require_GET,require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from .stat_dashboard import stat_dashboard_factory
from .api import stat_dashboard_api
from .grade_reports import grade_reports
from django.conf import settings
from util.json_request import JsonResponse
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from courseware.courses import get_course_by_id

#TASK
from django.views.decorators.cache import cache_control
from django.db import IntegrityError, transaction
from lms.djangoapps.instructor_task.api_helper import AlreadyRunningError
from django.utils.translation import ugettext as _
log = logging.getLogger(__name__)
from lms.djangoapps.tma_task.api import submit_calculate_grades_xls,submit_generate_users

#TMA DASHBOARD
from edxmako.shortcuts import render_to_response
from tma_dashboard import tma_dashboard

#course_cut_off class
from course_cut_off import course_cut_off

@login_required
@require_GET
def stat_dashboard(request, course_id):

    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    _stat_dashboard = stat_dashboard_factory(course_id,course_key,request=request)

    return _stat_dashboard.as_views()


@ensure_csrf_cookie
@login_required
def get_dashboard_username(request,course_id,username):

    context = stat_dashboard_api(request,course_id,username)._get_dashboard_username()

    return JsonResponse(context)


@ensure_csrf_cookie
@login_required
@require_GET
def stat_dashboard_username(request, course_id, username):

    context = stat_dashboard_api(request,course_id,username)._dashboard_username()

    return JsonResponse(context)


@ensure_csrf_cookie
@login_required
@require_POST
def get_course_blocks_grade(request,course_id):

    course_grade = stat_dashboard_api(request,course_id)._course_blocks_grade()

    return JsonResponse({'course_grade':course_grade})


@ensure_csrf_cookie
@login_required
@require_POST
def stat_grade_reports(request,course_id):

    microsite = configuration_helpers.get_value('domain_prefix')
    if microsite is None:
        microsite = '_';

    return grade_reports(request,course_id=course_id,microsite=microsite).generate_xls()

@login_required
@require_GET
def download_xls(request,filename):

    return grade_reports(request,filename=filename).download_xls()

#TMA dashboard views
@login_required
@require_GET
def tma_dashboard_views(request,course_id):

    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    _tma_dashboard = tma_dashboard(course_id=course_id,course_key=course_key,request=request)

    return _tma_dashboard.as_views()

@login_required
@require_GET
@ensure_csrf_cookie
def tma_overall_users_views(request,course_id):
    _stat_dashboard_api = stat_dashboard_api(request,course_id)
    return JsonResponse(_stat_dashboard_api.overall_grades_infos())


@login_required
@require_GET
@ensure_csrf_cookie
def tma_per_question_views(request,course_id):
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    _stat_dashboard_api = stat_dashboard_api(request,course_id,course_key=course_key)
    return JsonResponse(_stat_dashboard_api.get_course_structure())


@login_required
@require_POST
@ensure_csrf_cookie
def tma_ensure_email_username(request,course_id):

    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)

    return JsonResponse(tma_dashboard(course_id=course_id,course_key=course_key,request=request).ensure_user_exists())

@login_required
@require_POST
@ensure_csrf_cookie
def tma_cut_off_update(request,course_id):

    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    course = get_course_by_id(course_key)
    return JsonResponse(course_cut_off(course_id=course_id,course_key=course_key,course=course).set_course_status(request))

@transaction.non_atomic_requests
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@login_required
@require_GET
@ensure_csrf_cookie
def task_user_grade_list(request,course_id):

    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)

    return JsonResponse(tma_dashboard(course_id=course_id,course_key=course_key,request=request).user_grade_task_list())

#TASK EXEMPLE
@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
#@require_level('staff')
def calculate_grades_xls(request,course_id):

    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    try:
        submit_calculate_grades_xls(request, course_key)
        success_status = _("The grade report is being created."
                           " To view the status of the report, see Pending Tasks below.")
        return JsonResponse({"status": success_status,"user_email":request.user.email})
    except AlreadyRunningError:
        already_running_status = _("The grade report is currently being created."
                                   " To view the status of the report, see Pending Tasks below."
                                   " You will be able to download the report when it is complete.")
        return JsonResponse({"status": already_running_status})

@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
#@require_level('staff')
def tma_create_user_from_csv(request,course_id):
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    try:
        submit_generate_users(request, course_key)
        success_status = _("La generations du rapport de notes a ete lance.")
        return JsonResponse({"status": success_status})
    except AlreadyRunningError:
        already_running_status = _("Une generation de rapport de notes, veuillez attendre quelle se finisse")
        return JsonResponse({"status": already_running_status})
