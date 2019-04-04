#!/usr/bin/env python

import os
import importlib
import sys
reload(sys)
sys.setdefaultencoding('utf8')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lms.envs.aws")
os.environ.setdefault("lms.envs.aws,SERVICE_VARIANT", "lms")
os.environ.setdefault("PATH", "/edx/app/edxapp/venvs/edxapp/bin:/edx/app/edxapp/edx-platform/bin:/edx/app/edxapp/.rbenv/bin:/edx/app/edxapp/.rbenv/shims:/edx/app/edxapp/.gem/bin:/edx/app/edxapp/edx-platform/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")

os.environ.setdefault("SERVICE_VARIANT", "lms")
os.chdir("/edx/app/edxapp/edx-platform")

startup = importlib.import_module("lms.startup")
startup.run()

from django.core.management import execute_from_command_line
import django

#Script imports
from courseware.courses import get_course_by_id
import json
from microsite_configuration.models import Microsite
from opaque_keys.edx.keys import CourseKey
from tma_stat_dashboard.grade_reports import grade_reports


receivers_args = sys.argv[1]
course_id = sys.argv[2]
fields_args = sys.argv[3]
try :
    cohortes_list = sys.argv[4]
except:
    cohortes_list=''


try:
    course_key=CourseKey.from_string(course_id)
    course_org=get_course_by_id(course_key).org
    microsite_information = Microsite.objects.get(key=course_org)
except:
    sys.exit('Course id is not valid!')

#Treated arguments
receivers = receivers_args.split(';')
fields = fields_args.split(';')
if cohortes_list :
    cohortes_list=cohortes_list.split(';')
    cohortes_list=['cohort_selection_'+cohorte for cohorte in cohortes_list]
    fields.extend(cohortes_list)
try:
    microsite_register_form = microsite_information.values['FORM_EXTRA']
except:
    microsite_register_form=''
try :
    microsite_certificate_form = microsite_information.values['CERTIFICATE_FORM_EXTRA']
except:
    microsite_certificate_form=''

task_input = {
    "microsite":course_org,
    "form":fields,
    "register_form":microsite_register_form,
    "certificate_form":microsite_certificate_form,
    "send_to":receivers,
}
print(task_input)
grade_reports(task_input,course_id=course_id).task_generate_xls()
