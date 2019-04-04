# -*- coding: utf-8 -*-
from django.utils.translation import ugettext as _
from celery import task
from django.conf import settings
from djcelery.models import (PeriodicTask, PeriodicTasks,CrontabSchedule, IntervalSchedule)
from util.json_request import JsonResponse
import logging
import random
import string
import json
from celery import task
from tma_task.tasks_helper import (
    BaseInstructorTask,
)
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
import os
import json
from xlwt import *
import time
import logging

from django.utils.translation import ugettext as _

from django.conf import settings

from django.http import Http404, HttpResponseServerError, HttpResponse
from util.json_request import JsonResponse
from student.models import User,CourseEnrollment,UserProfile
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from lms.djangoapps.tma_grade_tracking.models import dashboardStats
from tma_ensure_form.utils import ensure_form_factory
from .libs import return_select_value
from lms.djangoapps.grades.new.course_grade import CourseGradeFactory
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from opaque_keys.edx.keys import CourseKey
from courseware.courses import get_course_by_id
from openedx.core.djangoapps.course_groups.models import CohortMembership, CourseUserGroup

from io import BytesIO

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEBase import MIMEBase
from email import encoders

from django.core.mail import EmailMessage
from celery import Celery


log = logging.getLogger(__name__)

class scheduled_grade_report() :
    def __init__(self,course_id,course_key,request):
    	self.course_id = str(course_id)
    	self.user = request.user
    	self.request = request
    	self.course_key = course_key

    def manage_scheduled_report(self):
        status=200
        response={}

        action=self.request.POST.get('action')
        minute=self.request.POST.get('minutes')
        hour=self.request.POST.get('hour')
        day=self.request.POST.get('day')
        day_month=self.request.POST.get('day_month')
        month_year=self.request.POST.get('month_year')
        receivers=self.request.POST.get('receivers')
        report_fields=self.request.POST.get('report_fields')


        log.info(' action {}'.format(action))
        log.info(' requestttttttttttttttttttttttttttt {}'.format(self.request.POST))

        if action =="add_scheduled_report":
            #Prepare tasks arguments
            microsite = configuration_helpers.get_value('domain_prefix')
            register_form = configuration_helpers.get_value('FORM_EXTRA')
            if register_form is None:
                register_form = []
            certificate_form = configuration_helpers.get_value('CERTIFICATE_FORM_EXTRA')
            if certificate_form is None:
                certificate_form = []
            if microsite is None:
                microsite = '_';

            kwargs={
                "microsite":microsite,
                "course_id":self.course_id,
                "register_form":register_form,
                "certificate_form":certificate_form,
                "report_fields":report_fields,
                "receivers":receivers,
            }

            #Check if cron exists
            if all(parameter is not None for parameter in [minute, hour, day, day_month, month_year]):
                cron_params={
                    "minute":minute,
                    "hour":hour,
                    "day_of_week":day,
                    "day_of_month":day_month,
                    "month_of_year":month_year
                }

                if CrontabSchedule.objects.filter(**cron_params).exists() :
                    cron_tab=CrontabSchedule.objects.get(**cron_params)
                else :
                    cron_tab, _ = CrontabSchedule.objects.get_or_create(**cron_params)

                name=self.course_id+'_'.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(4))
                task="tma_stat_dashboard.scheduled_grade_report.launch_gr_generation"
                PeriodicTask.objects.create(name=name,crontab=cron_tab,task=task,kwargs=json.dumps(kwargs))


            else :
                status = 400
                response['error']=[minutes, hour, day, day_month, month_year,kwargs]


        elif action=="remove_scheduled_report":
            pass

        else :
            status = 400
            response['error']=_('Wrong action request')
        return JsonResponse(response, status=status)


@task(base=BaseInstructorTask, routing_key=settings.GRADES_DOWNLOAD_ROUTING_KEY)
def launch_gr_generation(microsite,course_id, register_form, certificate_form, report_fields, receivers):
    send_grade_report(microsite,course_id, register_form, certificate_form, report_fields, receivers)



def send_grade_report(microsite,course_id, register_form, certificate_form, report_fields, receivers):
    #Get report info
    course_key=CourseKey.from_string(course_id)
    course=get_course_by_id(course_key)

    #Dict of labels
    form_labels={}
    for field in register_form :
        form_labels[field.get('name')]=field.get('label')
    for field in certificate_form :
        form_labels[field.get('name')]=field.get('label')
    form_labels['last_connexion']="Dernière connexion"
    form_labels['inscription_date']="Date d'inscription"
    form_labels['user_id']='Id Utilisateur'
    form_labels['email']='Email'
    form_labels['grade_final']='Note finale'
    form_labels['cohorte_names']="Nom de la cohorte"

    #Form Factory
    form_factory = ensure_form_factory()
    form_factory_db = 'ensure_form'
    form_factory_collection = 'certificate_form'
    form_factory.connect(db=form_factory_db,collection=form_factory_collection)

    #get workbook
    wb = Workbook(encoding='utf-8')
    filename = '/home/edxtma/csv/{}_{}.xls'.format(time.strftime("%Y_%m_%d"),course.display_name_with_default)
    sheet = wb.add_sheet('Stats')

    #Prepare header
    log.info('report_fields {}'.format(report_fields))
    cell=0
    for field in report_fields :
        if field=="grade_detailed":
            grade_detail_labels=[]
            for evaluation in course._grading_policy['RAW_GRADER'] :
                grade_detail_labels.append(evaluation['type'])
                sheet.write(0, cell, evaluation['type'])
                cell+=1
        else :
            sheet.write(0, cell, form_labels.get(field))
            cell+=1

    if "cohorte_names" in report_fields :
        cohortes = CourseUserGroup.objects.filter(course_id=course_key)
        cohortes_names={}
        for cohorte in cohortes :
            cohortes_names[cohorte.id]=cohorte.name

    #Get user report info
    course_enrollments=CourseEnrollment.objects.filter(course_id=course_key)

    line=1
    for enrollment in course_enrollments :
        cell=0
        user= enrollment.user
        user_grade = CourseGradeFactory().create(user, course)
        grade_summary={}
        for section_grade in user_grade.grade_value['section_breakdown']:
            grade_summary[section_grade['category']]=section_grade['percent']
        try:
            custom_field = json.loads(UserProfile.objects.get(user=user).custom_field)
        except:
            custom_field = {}

        user_certificate_info = {}
        form_factory.microsite = microsite
        form_factory.user_id = user.id

        try:
            user_certificate_info = form_factory.getForm(user_id=True,microsite=True).get('form')
        except:
            pass

        for field in report_fields :
            if field=="last_connexion":
                try :
                    last_login=user.last_login.strftime('%d-%m-%y')
                except:
                    last_login=''
                sheet.write(line, cell, last_login)
                cell+=1
            elif field=="inscription_date":
                try :
                    date_joined=user.date_joined.strftime('%d-%m-%y')
                except:
                    date_joined=''
                sheet.write(line, cell, date_joined)
                cell+=1
            elif field=="user_id":
                sheet.write(line, cell, user.id)
                cell+=1
            elif field=="email":
                sheet.write(line, cell, user.email)
                cell+=1
            elif field=="cohorte_names":
                cohortes_list=''
                if CohortMembership.objects.filter(course_id=course_key, user_id=user.id).exists():
                    user_cohortes = CohortMembership.objects.filter(course_id=course_key, user_id=user.id)
                    log.info('user cohorteeeeeeeeeeessssssss{}'.format(user_cohortes))
                    for cohorte in user_cohortes :
                        cohortes_list+=cohortes_names[cohorte.course_user_group_id]+" "
                sheet.write(line, cell, cohortes_list)
                cell+=1
            elif field=="grade_detailed":
                for section in grade_detail_labels :
                    section_grade = str(int(round(grade_summary[section] * 100)))+'%'
                    sheet.write(line, cell, section_grade)
                    cell+=1

            elif field=="grade_final":
                percent = str(int(round(user_grade.percent * 100)))+'%'
                sheet.write(line, cell, percent)
                cell+=1
            elif field in user_certificate_info.keys():
                certificate_value = user_certificate_info.get(field)
                sheet.write(line, cell, certificate_value)
                cell+=1
            else :
                try :
                    user_data=custom_field[field]
                except:
                    user_data=""
                sheet.write(line, cell, user_data)
                cell+=1


        line+=1
        log.warning("file ok")


    #Save the file
	output = BytesIO()
	wb.save(output)
	_files_values = output.getvalue()
    log.warning("file saved")


    html = "<html><head></head><body><p>Bonjour,<br/><br/>Vous trouverez en PJ le rapport de donnees du MOOC {}<br/><br/>Bonne reception<br>The MOOC Agency<br></p></body></html>".format(course.display_name)
    part2 = MIMEText(html.encode('utf-8'), 'html', 'utf-8')

    for receiver in receivers :
        fromaddr = "ne-pas-repondre@themoocagency.com"
        toaddr = str(receiver)
        msg = MIMEMultipart()
        msg['From'] = fromaddr
        msg['To'] = toaddr
        msg['Subject'] = "Rapport des reussites"
        attachment = _files_values
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', "attachment; filename= %s" % os.path.basename(filename))
        msg.attach(part)
        server = smtplib.SMTP('mail3.themoocagency.com', 25)
        server.starttls()
        server.login('contact', 'waSwv6Eqer89')
        msg.attach(part2)
        text = msg.as_string()
        server.sendmail(fromaddr, toaddr, text)
        server.quit()
        log.warning("file sent to {}".format(receiver))

    response = {
        'path':filename,
        'send_to':receivers
    }

    return response
