import json
import datetime
import time
from student.models import *
from xmodule.modulestore.django import modulestore

import logging
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from courseware.courses import get_course_by_id
from courseware.models import StudentModule

log = logging.getLogger(__name__)


class course_cut_off():


	def __init__(self,course,user):

		"""
		course is defined by the def get_course_by_id(course_key)
		course_key is defined by SlashSeparatedCourseKey.from_deprecated_string(course_id)
		user is defined from the User Class

		All timers are in seconds & timestamps
		"""

		self.course_id = str(course.id)
		self.course = course
		self.user = user


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
		log.warning("course_cut_off.get_course_enroll user {}, _current : {}".format(self.user.id,len(_current)))
		if len(_current) > 0:
			log.warning("course_cut_off.get_course_enroll user {}, created : {}".format(self.user.id,_current[0].created))
			_time = time.mktime(_current[0].created.timetuple())
		log.warning("course_cut_off.get_course_enroll user {}, value : {}".format(self.user.id,_time))
		return _time

	def check_user_allowed(self):
		context = True
		_course = self.get_course_status()
		_is_cut_off = _course.get('_is')
		log.warning("course_cut_off.check_user_allowed user {}, _is_cut_off : {}".format(self.user.id,_is_cut_off))
		if _is_cut_off is not None:
			if _is_cut_off:
				_time = self.get_course_enroll()
				now = datetime.now()
				timestamp = time.mktime(now.timetuple())
				log.warning("course_cut_off.check_user_allowed user {}, total time : {}".format(self.user.id,(_time + _course.get('timer'))))
				log.warning("course_cut_off.check_user_allowed user {}, timestamp : {}".format(self.user.id,timestamp))
				if (_time + _course.get('timer')) < timestamp:
					context = False
		log.warning("course_cut_off.check_user_allowed user {}, value : {}".format(self.user.id,context))
		return context
