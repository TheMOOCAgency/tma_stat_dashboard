# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf8')

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
from openedx.core.djangoapps.course_groups.cohorts import get_cohort, is_course_cohorted
from tma_apps.models import TmaCourseEnrollment
import time
from collections import OrderedDict
from lms.djangoapps.grades.context import grading_context_for_course

from io import BytesIO

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEBase import MIMEBase
from email import encoders

from django.core.mail import EmailMessage

log = logging.getLogger(__name__)

#OLD VERSION GRADES REPORT
class grade_reports():
    def __init__(self,request,course_id=None,microsite=None,filename=None,filepath=None):
        self.request = request
        self.course_id = course_id
        self.microsite = microsite
        self.filename = filename
        self.filepath = filepath

    def prepare_workbook(self):
        timesfr = time.strftime("%d_%m_%Y_%H_%M_%S")
        timestr = str(timesfr)
        wb = Workbook(encoding='utf-8')
        self.filename = '{}_{}_grades.xls'.format(self.microsite,timestr)
        self.filepath = '/edx/var/edxapp/grades/{}'.format(self.filename)
        sheet_count = wb.add_sheet('reports')

        return wb

    def generate_xls(self):
        log.warning(_("tma_grade_reports : start generate_xls"))
        log.warning(_("tma_grade_reports : course_id : "+self.course_id))

        #get request body

        body = json.loads(self.request.body).get('fields')

        log.warning(_("tma_grade_reports : microsite : "+self.microsite))
        log.warning(_("tma_grade_reports : body : "+str(body)))
        #get mongodb course's grades
        mongo_persist = dashboardStats()
        find_mongo_persist_course = mongo_persist.get_course(self.course_id)

        #prepare workbook
        _wb = self.prepare_workbook()
        sheet_count = _wb.get_sheet('reports')

        #form factory connection
        form_factory = ensure_form_factory()
        form_factory_db = 'ensure_form'
        form_factory_collection = 'certificate_form'
        form_factory.connect(db=form_factory_db,collection=form_factory_collection)

        #get register & certificate fields info
        register_form_ = configuration_helpers.get_value('FORM_EXTRA')
        certificates_form_ = configuration_helpers.get_value('CERTIFICATE_FORM_EXTRA')

        #prepare workbook header
        k=0
        for u in body:
            if not ('final-grades' and 'summary') in u:
                sheet_count.write(0, k, u)
                k = k + 1
            elif "summary" in u:
                grade_breakdown = find_mongo_persist_course[0].get('users_info').get('summary').get('grade_breakdown')
                for key,value in grade_breakdown.items():
                    sheet_count.write(0, k, value.get('category'))
                    k = k + 1
            elif "final-grades" in u:
                sheet_count.write(0, k, 'final grade')
                k = k + 1
                sheet_count.write(0, k, 'Eligible attestation')
                k = k + 1

        #sheets row
        j = 1

        #write differents workbook_rows
        for _row in find_mongo_persist_course:
            # get row user_id
            user_id = _row['user_id']

            #ensure user exist if False pass to next row
            ensure_user_exist = True
            try:
                #get current row users mysql auth_user & aut_userprofile info
                _user = User.objects.raw("SELECT a.id,a.email,a.username,a.date_joined,b.custom_field FROM auth_user a,auth_userprofile b WHERE a.id = b.user_id and a.id = %s", [user_id])

                #prepare dict of auth_user info
                user = {}

                #prepare dict of aut_userprofile info
                user_profile = {}

                #prepare dict of certificate form info
                user_certif_profile = {}

                #ensure only first occurance of _user is use
                det = 0

                #get current user certificates forms values
                if certificates_form_ is not None:
                    form_factory.microsite = self.microsite
                    form_factory.user_id = user_id
                    try:
                        user_certif_profile = form_factory.getForm(user_id=True,microsite=True).get('form')
			log.ingo("user_certif_profile")
			log.warning(user_certif_profile)
                    except:
                        pass

                #hydrate user & user_profile dicts
                for extract in _user:
                    if det < 1:
                        #hydrate user dict
                        user['id'] = extract.id
                        user['email'] = extract.email
                        user['username'] = extract.username
                        user['date_joined'] = extract.date_joined

                        #row from auth_userprofile mysql table
                        _user_profile = extract.custom_field

                        #bloc for with det == 1
                        det = 1

                        #hydrate user_profile dict
                        try:
                            user_profile = json.loads(_user_profile)
                        except:
                            pass

            except:
                ensure_user_exist = False

            #write user xls line if exist
            if ensure_user_exist:
                k=0
                for n in body:

                    #insert user mysql value to xls
                    if n in user.keys():
                        if n == 'date_joined':
                            sheet_count.write(j, k, str(user.get(n).strftime('%d-%m-%Y')))
                        else:
                            sheet_count.write(j, k, user.get(n))
                        k = k + 1

                    #insert register_form mysql value to xls
                    elif n in user_profile.keys():
                        _insert_value = return_select_value(n,user_profile.get(n),register_form_)
                        sheet_count.write(j, k, _insert_value)
                        k = k + 1

                    #insert certificate_form mongodb value to xls
                    elif n in user_certif_profile.keys():
                        _insert_value = return_select_value(n,user_certif_profile.get(n),certificates_form_)
                        sheet_count.write(j, k, _insert_value)
                        k = k + 1

                    #insert summary grades mongodb value to xls
                    elif "summary" in n:
                        grade_breakdown = _row.get('users_info').get('summary').get('grade_breakdown')
                        for key,value in grade_breakdown.items():
                            #insert grade value to xls
                            details = value['detail']
                            details = details.replace(value['category'],"").replace(" = ","").replace("of a possible ","").replace("%","")
                            split = details.split(" ")
                            avg = str(int(float(split[0])/float(split[1]) * 100))+"%"
                            sheet_count.write(j, k, avg)
                            k = k + 1

                    #insert final grades mongodb value to xls
                    elif "final-grades" in n:
                        sheet_count.write(j, k, str(_row.get('users_info').get('percent') * 100)+"%")
                        k = k + 1
                        sheet_count.write(j, k, str(_row.get('users_info').get('passed')))
                        k = k + 1
                    else:
                        sheet_count.write(j, k, '')
                        k = k + 1
                j = j + 1
            else:
                pass
        log.warning(_("tma_grade_reports : save file generate_xls"))
        _wb.save(self.filepath)
        _file = open(self.filepath,'r')
        _content = _file.read()
        _file.close()

        response = {
            'path':self.filename
        }

        return JsonResponse(response)




    def tma_graded_scorable_blocks_to_header(self, course_key):
        """
        Returns an OrderedDict that maps a scorable block's id to its
        headers in the final report.
        """
        scorable_blocks_map = OrderedDict()
        grading_context = grading_context_for_course(course_key)
        for assignment_type_name, subsection_infos in grading_context['all_graded_subsections_by_type'].iteritems():
            for subsection_index, subsection_info in enumerate(subsection_infos, start=1):
                for scorable_block in subsection_info['scored_descendants']:
                    header_name = (
                        u"{assignment_type} {subsection_index}: "
                        u"{subsection_name} - {scorable_block_name}"
                    ).format(
                        scorable_block_name=scorable_block.display_name,
                        assignment_type=assignment_type_name,
                        subsection_index=subsection_index,
                        subsection_name=subsection_info['subsection_block'].display_name,
                    )
                    scorable_blocks_map[scorable_block.location] = header_name
        return scorable_blocks_map

    def get_time_tracking(self,enrollment):
        tma_enrollment,is_exist=TmaCourseEnrollment.objects.get_or_create(course_enrollment_edx=enrollment)
        seconds = tma_enrollment.global_time_tracking
        hour = seconds // 3600
        seconds %= 3600
        minute = seconds // 60
        global_time = str(hour)+"h"+str(minute)+"min"
        return global_time




    #ACTUAL VERSION GRADES REPORT
    def task_generate_xls(self):
        log.info('Start task generate XLS')
        #Get report infos
        self.microsite = self.request.get('microsite')
        report_fields = self.request.get('form')
        register_fields = self.request.get('register_form')
        certificate_fields = self.request.get('certificate_form')
        course_key=CourseKey.from_string(self.course_id)
        course=get_course_by_id(course_key)

        form_factory = ensure_form_factory()
        form_factory.connect(db='ensure_form',collection='certificate_form')

        #Dict of labels
        form_labels={
            "last_connexion":_("Last login"),
            "inscription_date":_("Register date"),
            "user_id":_("User id"),
            "email":_("Email"),
            "grade_final":_("Final Grade"),
            "cohorte_names":_("Cohorte name"),
            "time_tracking":_("Time spent"),
            "certified":_("Attestation"),
            "username":_("Username"),
        }
        for field in register_fields :
            form_labels[field.get('name')]=field.get('label')
        for field in certificate_fields :
            form_labels[field.get('name')]=field.get('label')

        #Identify multiple cells fields
        multiple_cell_fields=["exercises_grade","grade_detailed"]

        #Is report cohort specific?
        course_cohorted=is_course_cohorted(course_key)
        if course_cohorted :
            cohortes_targeted=[field.replace('cohort_selection_','') for field in report_fields if field.find('cohort_selection_')>-1]
            for field in report_fields :
                log.info(field)
                log.info(field.find('cohort_selection_'))
            log.info(cohortes_targeted)
            log.info('cohortes_targeted')
            if cohortes_targeted and not 'cohorte_names' in report_fields:
                report_fields.append('cohorte_names')
        else :
            if 'cohorte_names' in report_fields:
                report_fields.remove('cohorte_names')

        #Get Graded block for exercises_grade details
        graded_scorable_blocks = self.tma_graded_scorable_blocks_to_header(course_key)

        #Create Workbook
        wb = Workbook(encoding='utf-8')
        filename = '/home/edxtma/csv/{}_{}.xls'.format(time.strftime("%Y_%m_%d"),course.display_name_with_default)
        sheet = wb.add_sheet('Grade Report')

        #Write information
        line=1
        course_enrollments=CourseEnrollment.objects.filter(course_id=course_key, is_active=1)
        for enrollment in course_enrollments :
            #do not include in reports if not active
            if not enrollment.is_active:
                continue
            #Gather user information
            user= enrollment.user
            user_grade = CourseGradeFactory().create(user, course)
            grade_summary={}

            if course_cohorted :
                user_cohorte=get_cohort(user, course_key).name
                #if cohort specific report avoid student that are not part of cohortes_targeted provided
                if cohortes_targeted and not user_cohorte in cohortes_targeted :
                    continue

            for section_grade in user_grade.grade_value['section_breakdown']:
                grade_summary[section_grade['category']]=section_grade['percent']
            try:
                custom_field = json.loads(UserProfile.objects.get(user=user).custom_field)
            except:
                custom_field = {}

            user_certificate_info = {}
            try:
                form_factory.microsite = self.microsite
                form_factory.user_id = user.id
                user_certificate_info = form_factory.getForm(user_id=True,microsite=True).get('form')
            except:
                pass

            cell=0
            for field in report_fields :
                if field in multiple_cell_fields:
                    if field=="grade_detailed":
                        for section in grade_summary :
                            section_grade = str(int(round(grade_summary[section] * 100)))+'%'
                            sheet.write(line, cell, section_grade)
                            #Write header
                            if line ==1 :
                                sheet.write(0, cell, "Travail - "+section)
                            cell+=1
                    elif field=="exercises_grade":
                        for block_location in graded_scorable_blocks.items():
                            try:
                                problem_score = user_grade.locations_to_scores[block_location[0]]
                                if problem_score.attempted:
                                    value=round(float(problem_score.earned)/problem_score.possible, 2)
                                else:
                                    value=_('n.a.')
                            except:
                                value=_('inv.')
                            sheet.write(line, cell, value)
                            if line==1 :
                                sheet.write(0, cell, block_location[1])
                            cell+=1
                else :
                    value=''
                    if field=="user_id":
                        value=user.id
                    elif field=="email":
                        value=user.email
                    elif field=="first_name":
                        try :
                            if user.first_name:
                                value=user.first_name
                            elif custom_field :
                                value=custom_field.get('first_name', 'unkowna')
                            else :
                                value='unknown'
                        except :
                            value='unknown'
                    elif field=="last_name":
                        try :
                            if user.last_name:
                                value=user.last_name
                            elif custom_field:
                                value=custom_field.get('last_name', 'unkowna')
                        except :
                            value='unknown'
                    elif field=="last_connexion":
                        try :
                            value=user.last_login.strftime('%d-%m-%y')
                        except:
                            value=''
                    elif field=="inscription_date":
                        try :
                            value=user.date_joined.strftime('%d-%m-%y')
                        except:
                            value=''
                    elif field=="cohorte_names":
                        try:
                            value=user_cohorte
                        except:
                            value=''
                    elif field=="time_tracking":
                        value=self.get_time_tracking(enrollment)
                    elif field=="certified":
                        if user_grade.passed :
                            value = _("Yes")
                        else :
                            value = _("No")
                    elif field=="grade_final":
                        value = str(int(round(user_grade.percent * 100)))+'%'
                    elif field=="username":
                        value=user.username
                    elif field in user_certificate_info.keys():
                        value=user_certificate_info.get(field)
                    else :
                        value=custom_field.get(field,'')
                    #Write header and write value
                    log.info('field')
                    log.info(field)
                    log.info('value')
                    log.info(value)
                    log.info(form_labels)
                    if field in form_labels.keys():
                        sheet.write(line, cell, value)
                        if line==1:
                            sheet.write(0, cell, form_labels.get(field))
                        cell+=1
            line+=1
            log.warning("file ok")


        #Save the file
        output = BytesIO()
        wb.save(output)
        _files_values = output.getvalue()
        log.warning("file saved")

        #Send the email to receivers
        receivers = self.request.get('send_to')

        html = "<html><head></head><body><p>Bonjour,<br/><br/>Vous trouverez en PJ le rapport de donnees du MOOC {}<br/><br/>Bonne reception<br>The MOOC Agency<br></p></body></html>".format(course.display_name)
        part2 = MIMEText(html.encode('utf-8'), 'html', 'utf-8')

        for receiver in receivers :
            fromaddr = "ne-pas-repondre@themoocagency.com"
            toaddr = str(receiver)
            msg = MIMEMultipart()
            msg['From'] = fromaddr
            msg['To'] = toaddr
            msg['Subject'] = "Rapport de donnees"
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
            'path':self.filename,
            'send_to':receivers
        }

        return response




    def download_xls(self):
        self.filepath = '/edx/var/edxapp/grades/{}'.format(self.filename)
        _file = open(self.filepath,'r')
        _content = _file.read()
        response = HttpResponse(_content, content_type="application/vnd.ms-excel")
        response['Content-Disposition'] = "attachment; filename="+self.filename
        return response
