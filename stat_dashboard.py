# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf8')

from opaque_keys.edx.locations import SlashSeparatedCourseKey
from xmodule.modulestore.django import modulestore
from courseware.courses import get_course_by_id
from student.models import User,CourseEnrollment,UserProfile
from course_api.blocks.api import get_blocks
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from lms.djangoapps.tma_grade_tracking.models import dashboardStats
from edxmako.shortcuts import render_to_response

class stat_dashboard_factory(dashboardStats):

    def __init__(self,course_id,course_key,request=None):
        #init parent class attributes
        dashboardStats.__init__(self)
        self.request = request
        self.course_id = course_id
        self.course_key = course_key
        self.course = get_course_by_id(course_key)
        self.course_usage_key = modulestore().make_course_usage_key(course_key)
        self.course_module = modulestore().get_course(course_key, depth=0)
        self.course_enrollment = CourseEnrollment.objects.all().filter(course_id=course_key)
        self.blocks_overviews = []
        self.register_form = configuration_helpers.get_value('FORM_EXTRA')
        self.certificate_form = configuration_helpers.get_value('CERTIFICATE_FORM_EXTRA')

    def _form_fields_name(self):
        #register field
        register_form_fields = []
        if self.register_form is not None:
            for n in self.register_form:
                register_form_fields.append(n.get('name'))
        #certificate field
        certificates_form_fields = []
        if self.certificate_form is not None:
            for n in self.certificate_form:
                certificates_form_fields.append(n.get('name'))

        context = {
            "certificates_form_fields":certificates_form_fields,
            "register_form_field":register_form_fields
        }

        return context

    def get_course_structure(self):

        blocks = get_blocks(self.request,self.course_usage_key,depth='all',requested_fields=['display_name','children'])
        root = blocks['root']
        try:
            children = blocks['blocks'][root]['children']
            for z in children:
                q = {}
                child = blocks['blocks'][z]
                q['display_name'] = child['display_name']
                q['id'] = child['id']
                try:
                    sub_section = child['children']
                    q['children'] = []
                    for s in sub_section:
                        sub_ = blocks['blocks'][s]
                        a = {}
                        a['id'] = sub_['id']
                        a['display_name'] = sub_['display_name']
                        vertical = sub_['children']
                        try:
                            a['children'] = []
                            for v in vertical:
                                unit = blocks['blocks'][v]
                                w = {}
                                w['id'] = unit['id']
                                w['display_name'] = unit['display_name']
                                try:
                                    w['children'] = unit['children']
                                except:
                                    w['children'] = []
                                a['children'].append(w)
                        except:
                            a['children'] = []
                        q['children'].append(a)
                except:
                    q['children'] = []
                self.blocks_overviews.append(q)
        except:
            children = ''

    def as_views(self):
        #defaults user fields from auth_user table
        grade_fields = [
            'id',
            'email',
            'username',
            'date_joined'
        ]
        #get grades persisted values in mongo stat_dashboard db
        find_mongo_persist_course = self.return_grades_values(self.course_id)
        self.get_course_structure()
        context = {

             "course_id":self.course_id,
             "course":self.course,
             "row":self.course_enrollment,
             'course_module':self.course_module,
             "all_user":find_mongo_persist_course['num_users'],
             "num_passed":find_mongo_persist_course['passed'],
             'course_average_grade':round(find_mongo_persist_course['average_grades'],1),
             'passed_average_grades':round(find_mongo_persist_course['passed_average_grades'],1),
             'user_finished':find_mongo_persist_course['passed'],
             'course_structure':self.blocks_overviews,
             'grade_fields':grade_fields,
             "extra_form_field":self._form_fields_name().get('register_form_field'),
             "certificates_form_fields":self._form_fields_name().get('certificates_form_fields')
        }

        return render_to_response('courseware/stat.html', context)
