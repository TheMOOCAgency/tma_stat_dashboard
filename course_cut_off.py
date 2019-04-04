import json
import datetime
from datetime import timedelta, date
import time
from student.models import *
from xmodule.modulestore.django import modulestore

import logging
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from courseware.courses import get_course_by_id
from courseware.models import StudentModule
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from util.json_request import JsonResponse
from openedx.core.djangoapps.course_groups.models import CohortMembership, CourseUserGroup
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from openedx.core.djangoapps.course_groups.cohorts import get_cohort
from django.utils.translation import ugettext as _

log = logging.getLogger(__name__)


class course_cut_off():


	def __init__(self,course, request, course_key):

		"""
		course is defined by the def get_course_by_id(course_key)
		course_key is defined by SlashSeparatedCourseKey.from_deprecated_string(course_id)
		user is defined from the User Class

		All timers are in seconds & timestamps
		"""
		self.course = course
		self.course_id = str(course.id)
		self.user = request.user
		self.request = request
		self.course_key = course_key


	#get course status
	def get_course_status(self):
		_return = {}
		_current = self.course.course_extra
		log.warning("course_cut_off.get_course_status user {}, value : {}".format(self.user.id,_current))
		if _current is not None:
			_value = _current.get('is_cut_off')
			if _value is not None:
				_return = _value
		return _return

	def get_course_enroll(self):

		_current = list(StudentModule.objects.raw("SELECT id,created FROM courseware_studentmodule WHERE course_id = %s AND student_id = %s ORDER BY created ASC LIMIT 1",[self.course_id,self.user.id]))
		_time = 0
		if len(_current) > 0:
			_time = time.mktime(_current[0].created.timetuple())
		return _time

	def check_user_allowed(self):
		context = True
		_course = self.get_course_status()
		_is_cut_off = _course.get('_is')
		if _is_cut_off is not None:
			if _is_cut_off:
				_time = self.get_course_enroll()
				now = datetime.now()
				timestamp = time.mktime(now.timetuple())
				if (_time + _course.get('timer')) < timestamp :
					context = False
		return context



	def get_remaining_global_time(self, user_register_date):
		remaining_time=''
		course_overview = CourseOverview.objects.get(id=self.course_key)
		course_extra = json.loads(course_overview.course_extra)['is_cut_off']
		if course_extra['_is'] :
			timer = timedelta(seconds=int(course_extra['timer']))
			remaining_time = (user_register_date.replace(tzinfo=None) + timer - datetime.now().replace(tzinfo=None)).total_seconds()
		return remaining_time


	#Enable or Disable timer on a course
	def tma_timer_activation(self):
		course_overview = CourseOverview.objects.get(id=self.course_key)
		course_extra = json.loads(course_overview.course_extra)
		action = self.request.POST.get('action')
		response={}

		if action is not None :
			if action == "disable_timer":
				course_extra['is_cut_off']['_is']=False
				response['success']=_("Timer disabled")

			elif action =="enable_timer":
				course_extra['is_cut_off']['_is']=True
				response['success']=_("Timer enabled")

			else :
				status = 400
				response['error']=_('Invalid Action')

			course_overview.course_extra = json.dumps(course_extra)
			course_overview.save()
			status=200

		else :
			status = 400
			response['error']='Missing Parameters'

		return  JsonResponse(response, status=status)


	def set_course_timer(self):
		status=''
		context={}
		action = self.request.POST.get('action')

		if action :
			course_overview = CourseOverview.objects.get(id=self.course_key)
			course_extra = json.loads(course_overview.course_extra)
			if action =='delete_course_timer':
				course_extra['is_cut_off']['timer_type']='no_timer'
				course_overview.course_extra = json.dumps(course_extra)
				course_overview.save()
				context['success']=_('Cours timer deleted')

			elif action =='add_course_timer':
				try:
					timer_type=self.request.POST.get('timer_type')
					timer_value=self.request.POST.get('timer_value')
					course_extra['is_cut_off']['timer_type']=timer_type
				except :
					timer_type=''
					timer_value=''

				if timer_type=="date_timer":
					course_extra['is_cut_off']['timer_date_value']=timer_value
					course_extra['is_cut_off']['timer_days_value']=''
					course_overview.course_extra = json.dumps(course_extra)
					course_overview.save()
					context['success']=_('Course date timer created')

				elif timer_type=="days_timer":
					course_extra['is_cut_off']['timer_days_value']=int(timer_value)
					course_extra['is_cut_off']['timer_date_value']=''
					course_overview.course_extra = json.dumps(course_extra)
					course_overview.save()
					context['success']=_('Course days timer created')

				else :
					status = 400
					context['error']=_('Invalid parameters sent')
			else :
				status = 400
				context['error']=_('Invalid action requested')
		else  :
			status = 400
			context['error']=_('No action requested')

		return JsonResponse(context, status=status)


	def set_cohort_timer(self):
		response={}
		status=200
		action=self.request.POST.get('action')

		cohort_id=self.request.POST.get('cohort_id')
		cohort=CourseUserGroup.objects.get(id=cohort_id)

		if action == 'add_cohort_timer' and cohort_id is not None:
			try :
				timer=self.request.POST.get('timer_cohort')
			except :
				timer=None

			if timer is not None :
				new_timer=datetime.strptime(timer, '%d-%m-%Y').replace(hour=11, minute=59)
				cohort.tma_timer=new_timer
				cohort.save()
				response['success']=_('cohort timer created')
			else :
				status = 400
				response['error']=_('Wrong parameters')

		elif action =='delete_cohort_timer' and cohort_id is not None:
			cohort.tma_timer=None
			cohort.save()
			response['success']=_('Cohort timer deleted')

		else :
			status = 400
			response['error']=_('Wrong parameters')

		return JsonResponse(response, status=status)


def has_valid_timer(user, course_id):
	#check if course has global timer
	course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
	course_overview = CourseOverview.objects.get(id=course_key)
	course_extra = json.loads(course_overview.course_extra)['is_cut_off']

	#Check use cohort CohortMembership
	if get_cohort(user, course_key):
		user_cohort_timer=get_cohort(user, course_key).tma_timer
	else :
		user_cohort_timer=None

	#check user course enrollement
	if CourseEnrollment.is_enrolled(user, course_key):
		user_register_date =CourseEnrollment.get_enrollment(user, course_key).created
		if user_register_date > course_overview.start :
			user_enter_date=user_register_date
		else :
			user_enter_date = course_overview.start
	else :
		user_enter_date=None

	user_access=True
	#Timer is activated
	user_timer_date=None
	if course_extra['_is']:
		#Check for cohort timer
		if user_cohort_timer is not None :
			user_timer_date=user_cohort_timer
		#If no cohort_timer check for course timer
		else :
			if 'timer_type' in course_extra and course_extra['timer_type']=='days_timer' and user_enter_date is not None :
				user_timer_date = user_enter_date +timedelta(days = course_extra['timer_days_value'])

			elif 'timer_type' in course_extra and course_extra['timer_type']=='date_timer' and user_enter_date is not None:
				user_timer_date = datetime.strptime(course_extra['timer_date_value'], '%d-%m-%Y').replace(hour=11, minute=59)

	if user_timer_date is not None and datetime.now() > user_timer_date.replace(tzinfo=None) :
		user_access=False


	return user_access


#fonctionnalite timer user en stand by
"""
	def set_user_timer(self):
		response={}
		status=200
		if self.request.method=="GET":
			if self.request.GET.get('user_email') is not None :
				mail = self.request.GET.get('user_email')
				if User.objects.filter(email=mail).exists():
					user = User.objects.get(email=mail)
					profile = UserProfile.objects.get(user=user)
					custom_fields = json.loads(user.profile.custom_field)

					if CourseEnrollment.objects.filter(course_id=self.course_key, user=user).exists():
						response['user_enrolled'] = True
						enrollment_object = CourseEnrollment.objects.get(user=user, course_id=self.course_key)
						try :
							response['user_timer']= enrollment_object.tma_timer
						except :
							response['user_timer']=None
						try :
							response['date_enrolled']= enrollment_object.created.strftime("%d-%m-%Y")
						except :
							response['date_enrolled']=None
					else :
						response['user_enrolled'] = False

					response['user_email'] = mail
					response['first_name'] = custom_fields.get('first_name')
					response['last_name'] = custom_fields.get('last_name')
					response['id'] = user.id
					#Get remaining time for current user according to course global time
					response['remaining_time']=str(self.get_remaining_global_time(enrollment_object.created));

				else :
					response['error'] = "User does not exists."
			else :
				status = 400
				response['error']='Invalid parameters sent'

		elif self.request.method=="POST":
			parameters = self.request.POST
			if parameters.get('action') is not None and parameters.get('user_id') is not None:
				user = User.objects.get(id=parameters['user_id'])
				Enrollment=CourseEnrollment.objects.get(user=user, course_id=self.course_key)
				if parameters['action']=="delete_individual_timer":
					Enrollment.tma_timer = None
					Enrollment.save()
					status=200
					response['success']="Timer erased"

				elif parameters['action']=="add_individual_timer":
					Enrollment.tma_timer = datetime.strptime(parameters['timer_value'], '%m/%d/%Y').replace(hour=11, minute=59)
					Enrollment.save()
					status=200
					response['timer_saved']=str(datetime.strptime(parameters['timer_value'], '%m/%d/%Y'))
			else :
				status = 400
				response['error']='Invalid parameters sent'

		else :
			status = 400
			response['error']='Method not allowed'

		return JsonResponse(response, status=status)

"""
