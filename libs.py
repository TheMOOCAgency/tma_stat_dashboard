
from django.contrib.auth.decorators import login_required
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore
from course_api.blocks.api import get_blocks



def require_level(level):
    """
    Decorator with argument that requires an access level of the requesting
    user. If the requirement is not satisfied, returns an
    HttpResponseForbidden (403).
    Assumes that request is in args[0].
    Assumes that course_id is in kwargs['course_id'].
    `level` is in ['instructor', 'staff']
    if `level` is 'staff', instructors will also be allowed, even
        if they are not in the staff group.
    """
    if level not in ['instructor', 'staff']:
        raise ValueError("unrecognized level '{}'".format(level))

    def decorator(func):  # pylint: disable=missing-docstring
        def wrapped(*args, **kwargs):  # pylint: disable=missing-docstring
            request = args[0]
            course = get_course_by_id(CourseKey.from_string(kwargs['course_id']))

            if has_access(request.user, level, course):
                return func(*args, **kwargs)
            else:
                return HttpResponseForbidden()
        return wrapped
    return decorator

#return real values of select fields' input
def return_select_value(key,value,kwarg):
    for indice in kwarg:
        if key == indice.get('name'):
            if indice.get('type') == 'select':
                if indice.get("options") is not None:
                    if len(indice.get("options")) > 0:
                        for _row in indice.get("options"):
                            if str(value) == str(_row.get('value')):
                                value = _row.get('name')
    return value
