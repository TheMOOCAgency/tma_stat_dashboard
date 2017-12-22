import json
import datetime

from student.models import *
from xmodule.modulestore.django import modulestore
#from cms.djangoapps.contentstore.views.course import get_course_and_check_access
import logging

log = logging.getLogger(__name__)


class course_cut_off():


	def __init__(self,course_id=None,course=None,user=None,course_key=None):

		"""
		course is defined by the def get_course_by_id(course_key)
		course_key is defined by SlashSeparatedCourseKey.from_deprecated_string(course_id)		
		user is defined from the User Class

		All timers are in seconds & timestamps
		"""

		self.course_id = course_id
		self.course_key = course_key
		self.course = course
		self.user = user


	#get current user course_cut_off status from custom_field mysql column
	def get_user_status(self):
		
		context = {
			"status": True,
			"data": None
		}

		try:
			_custom_field = UserProfile.objects.get(user=self.user).custom_field

			if _custom_field is not None:

				_custom_field = json.loads(_custom_field)
				_current_cut_off = _custom_field.get('is_cut_off')

				if _current_cut_off is not None:

					_status = False
					for _cut in _current_cut_off:

						if _cut.get('course_id') == self.course_id:
							context['data'] = _cut
							_status = True

					context['status'] = _status
		except:
			pass

		return context

	#get course status
	def get_course_status(self):

		_current = self.course.course_extra

		return json.loads(_current).get('is_cut_off')

	#set course_status
	def set_course_status(self,request):
		"""
		request params needs :
		{
			"status":(True or False),
			"duration":(None or value in seconds /!\ 3600s in 1hour,86400s in 1day,604800s in 1week,2592000s in 30 days)
		}
		"""
		context = {
			"status":None,
			"change_to":None
		}

		_data = json.loads(request.body)
		_status = _data.get("status")
		_duration = _data.get('duration')
		_view_string = _data.get('view_string')
		_current = self.course.course_extra
		log.info(u'_current %s', str(_current))
		try:
			_current = json.loads(_current)
		except:
			_current = {}

		if _status and _duration:

			_current['is_cut_off'] = {
				"status":_status,
				"timer":_duration,
				"view_string":_view_string
			}

			context = {
				"status":True,
				"change_to":_status
			}

		course_module = get_course_and_check_access(self.course_key, request.user)
		course_module['is_cut_off'] = _current['is_cut_off']
		modulestore().update_item(course_module, request.user.id)

		return context

	#check if current user is times out
	def time_out(self):

		context = {
			"status":None
		}

		_now = int(datetime.datetime.now().strftime('%s'))
		_current_course = self.get_course_status()
		_current_user = self.get_user_status()

		#if course as status _is from is_cut_off
		if _current_course.get('_is'):

			if _current_user.get('status'):

				if int(_current_user.get('data').get('end_date')) > now:
					context['status'] = True

				else:
					context['status'] = False

			else:

				_user_profile = UserProfile.objects.get(user=user)

				q = {
					"course_id": self.course_id,
					"start_date": now,
					"end_date": now + int(_current_course.get('timer'))
				}

				if _user_profile.custom_field is not None:

					_custom_field = _user_profile.custom_field

					if _custom_field.get('is_cut_off') is not None:
					   _custom_field['is_cut_off'].append(q)

					else:
						_custom_field['is_cut_off'] = [q]

				else:
					_custom_field = {
						"is_cut_off":[q]
					}

				_user_profile.cutsom_field = json.dumps(_custom_field)
				_user_profile.save()

				context['status'] = True

			return context






