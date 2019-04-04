# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf8')

from course_api.blocks.views import BlocksInCourseView,BlocksView
from courseware.models import StudentModule
from course_api.blocks.api import get_blocks
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from courseware.courses import get_course_by_id, get_studio_url
from lms.djangoapps.grades.new.course_grade import CourseGradeFactory
from student.models import User,CourseEnrollment,UserProfile,LoginFailures
from xmodule.modulestore.django import modulestore
import json
from lms.djangoapps.tma_grade_tracking.models import dashboardStats
from django.http import JsonResponse
from opaque_keys.edx.keys import CourseKey
from django.conf import settings
from courseware.courses import get_course_by_id
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from courseware.courses import get_courses
from time import strftime
from tma_apps.tma_support_functions import is_course_opened,is_enrollment_opened
from django.utils.translation import ugettext as _



class stat_dashboard_api():

    def __init__(self,request,course_id,username=None,course_key=None):
        self.request = request
        self.course_id = course_id
        self.course_key = course_key
        self.username = username

    #return course overall grades info
    def overall_grades_infos(self):

        mongo_persist = dashboardStats()
        find_mongo_persist_course = mongo_persist.return_grades_values(self.course_id)

        context = {
         "all_user":find_mongo_persist_course['num_users'],
         "user_finished":find_mongo_persist_course['passed'],
         'course_average_grade':round(find_mongo_persist_course['average_grades'],1),
         'passed_average_grades':round(find_mongo_persist_course['passed_average_grades'],1)
        }

        return context

    #return course structure
    def get_course_structure(self):
        blocks_overviews = []
        course_usage_key = modulestore().make_course_usage_key(self.course_key)
        blocks = get_blocks(self.request,course_usage_key,depth='all',requested_fields=['display_name','children'])
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
                blocks_overviews.append(q)
        except:
            children = ''

        return blocks_overviews

    #return unit average grades
    def _course_blocks_grade(self):

        data = json.loads(self.request.body)
        data_id = data.get('data_id')
        course_block = StudentModule.objects.raw("SELECT id,AVG(grade) AS moyenne,count(id) AS total,MAX(max_grade) AS max_grade,course_id,module_id FROM courseware_studentmodule WHERE course_id = %s AND max_grade IS NOT NULL AND grade <= max_grade GROUP BY module_id", [self.course_id])
        course_grade = {}
        for n in course_block:
            usage_key = n.module_state_key
            block_view = BlocksView()
            try:
                block_name = get_blocks(self.request,usage_key,depth='all',requested_fields=['display_name'])
                root = block_name['root']
                for z in data_id:
                    if root in z.get('id'):
                        if not root in course_grade:
                            course_grade[root] = {}
                            course_grade[root]['moyenne'] = n.moyenne
                            course_grade[root]['total'] = n.total
                            course_grade[root]['max_grade'] = n.max_grade
                            course_grade[root]['course_id'] = str(n.course_id)
                            course_grade[root]['module_id'] = str(n.module_state_key)
                            course_grade[root]['display_name'] = block_name['blocks'][root]['display_name']
                            course_grade[root]['vertical_name'] = z.get('title')

            except:
                pass
        return course_grade

    #return username from string
    def _get_dashboard_username(self):
        course_key = SlashSeparatedCourseKey.from_deprecated_string(self.course_id)
        row = User.objects.raw('SELECT a.id,a.username FROM auth_user a,student_courseenrollment b WHERE a.id=b.user_id AND b.course_id=%s' ,[self.course_id])
        usernames = []
        username = str(self.username).lower()
        for n in row:
            low = str(n.username).lower()
            if username in low:
                usernames.append(n.username)
        context = {
                "usernames":usernames
            }

        return context

    #Return data of user registered
    def tma_users_registered(self):
        context={}
        enrolled_to_current_course=False
        user_email = self.request.POST['user_email']

        if User.objects.filter(email=user_email).exists():
            user=User.objects.get(email=user_email)
            #Get preprofile info
            userprofile = UserProfile.objects.get(user=user)
            try :
                custom_field=json.loads(user.profile.custom_field)
                first_name=custom_field['first_name']
                last_name=custom_field['last_name']
            except :
                custom_field = {}
                last_name='Undefined'
                first_name='Undefined'

            #Get courses enrollments
            microsite_courses=get_courses(user=user, org=configuration_helpers.get_value('course_org_filter'))

            user_ms_course_list={}
            for course in microsite_courses :
                if CourseEnrollment.objects.filter(user=user, course_id=course.id).exists():
                    user_ms_course_list[str(course.id)]={
                        'course_name':course.display_name_with_default,
                        'course_grades':'/courses/'+str(course.id)+'/progress/'+str(user.id),
                        'opened_enrollments':is_enrollment_opened(course),
                        'opened_course':is_course_opened(course),
                        'on_invitation':course.invitation_only,
                    }


            #Get user grade for this course
            course_key = SlashSeparatedCourseKey.from_deprecated_string(self.course_id)
            current_course=get_course_by_id(course_key)
            grade = CourseGradeFactory().create(user, current_course)

            #User dates
            if user.last_login is not None:
                last_login=user.date_joined.strftime("%d-%b-%Y %H:%M:%S")
            else :
                last_login=_('User has not logged in yet')


            context={
                'email':str(user_email),
                'id':str(user.id),
                'inscription':str(user.date_joined.strftime("%d-%b-%Y %H:%M:%S")),
                'last_login':last_login,
                'first_name':first_name,
                'last_name':last_name,
                'user_ms_course_list': user_ms_course_list,
                'custom_field':custom_field,
                'grade':grade.grade_value['percent'],
                'passed':grade.grade_value['grade'],
                'active':user.is_active,
                'login_failure':LoginFailures.is_user_locked_out(user) ,
            }


            #Check if user is registered to this course
            course_key=SlashSeparatedCourseKey.from_deprecated_string(self.course_id)
            if CourseEnrollment.objects.filter(user=user,course_id=course_key, is_active=1).exists():
                current_course_grades='/courses/'+str(self.course_id)+'/progress/'+str(user.id)
                context['enrolled_to_current_course']=True
                context['current_course_grades']=current_course_grades
            else :
                context['enrolled_to_current_course']=False


        else :
            context={'error':'Le participant n\'a pas de compte sur nos plateformes.'}


        return context

    #return user stats
    def _dashboard_username(self):

        context = {
            "course_id":self.course_id,
            "username":self.username,
            "user_id": '',
            "course_grade": [],
            "user_info": '',
        }

        try:
            # get users info
            users = User.objects.get(username=self.username)
            # get user id
            user_id= users.id
            # get course_key from url's param
            course_key = SlashSeparatedCourseKey.from_deprecated_string(self.course_id)
            # get course from course_key
            course = get_course_by_id(course_key)
            # get all courses block of the site
            course_block = StudentModule.objects.all().filter(student_id=user_id,course_id=course_key,max_grade__isnull=False)
            # var of grades / course_structure
            course_grade = []
            # get course_users_info
            course_user_info = CourseGradeFactory().create(users, course)
            # user info responses
            user_info = [
                {'Grade':str(course_user_info.percent * 100)+'%'},
                {'First_name':users.first_name},
                {'Last_name':users.last_name},
                {'Email':users.email}
            ]

            for n in course_block:
                q = {}
                usage_key = n.module_state_key
                block_view = BlocksView()
                block_name = get_blocks(self.request,usage_key,depth='all',requested_fields=['display_name'])
                root = block_name['root']
                display_name = block_name['blocks'][root]['display_name']
                q['earned'] = n.grade
                q['possible'] = n.max_grade
                q['display_name'] = display_name
                q['root'] = root
                course_grade.append(q)

            context["user_id"] = user_id
            context["course_grade"] = course_grade
            context["user_info"] = user_info

        except:
            pass

        return context
