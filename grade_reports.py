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

from opaque_keys.edx.locations import SlashSeparatedCourseKey
from opaque_keys.edx.keys import CourseKey
from courseware.courses import get_course_by_id

from django.core.mail import EmailMessage

log = logging.getLogger(__name__)

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

        body = json.loads(self.request.body).get('array')

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

    def task_generate_xls(self):
        log.warning(_("tma_grade_reports_task : start generate_xls"))
        log.warning(_("tma_grade_reports_task : course_id : "+self.course_id))

        #get request body
        body = self.request.get('form')
        self.microsite = self.request.get('microsite')

        #get register & certificate fields info
        register_form_ = self.request.get('register_form')
        certificates_form_ = self.request.get('CERTIFICATE_FORM_EXTRA')

        log.warning(_("tma_grade_reports_task : microsite : "+self.microsite))

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

        #sending grades reports by mail
        #user requested
        sended_email = self.request.get('send_to')

        course_key = CourseKey.from_string(self.course_id)
        course = get_course_by_id(course_key)

        log.warning("send grade reports course_id : "+str(self.course_id))
        log.warning("email : "+str(sended_email)) 

        subject = "{} grades report".format(course.display_name_with_default_escaped)
        text_content = "Attached, {} grades reports in xls.".format(course.display_name_with_default_escaped)
        from_email=configuration_helpers.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
        to = sended_email
        mimetype='application/vnd.ms-excel'
        fail_silently=False

        _email = EmailMessage(subject, text_content, from_email, [to])
        _email.attach(self.filename, _content, mimetype=mimetype)
        _email.send(fail_silently=fail_silently)
        log.warning("end send grade reports course_id : "+str(self.course_id))

        response = {
            'path':self.filename,
            'send_to':sended_email
        }

        return response

    def download_xls(self):
        self.filepath = '/edx/var/edxapp/grades/{}'.format(self.filename)
        _file = open(self.filepath,'r')
        _content = _file.read()
        response = HttpResponse(_content, content_type="application/vnd.ms-excel")
        response['Content-Disposition'] = "attachment; filename="+self.filename
        os.remove(self.filepath)
        return response
