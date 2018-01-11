from opaque_keys.edx.locations import SlashSeparatedCourseKey
from xmodule.modulestore.django import modulestore
from courseware.courses import get_course_by_id
from student.models import User,CourseEnrollment,UserProfile
from course_api.blocks.api import get_blocks
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from lms.djangoapps.tma_grade_tracking.models import dashboardStats
from edxmako.shortcuts import render_to_response
from .api import stat_dashboard_api

from django.core.validators import validate_email

import logging
import json

from instructor.views.api import generate_random_string,create_manual_course_enrollment

from django.conf import settings

#enroll
from django.utils.translation import ugettext as _
from django.db import IntegrityError, transaction
from instructor.views.api import generate_random_string,create_manual_course_enrollment
from django.core.exceptions import ValidationError, PermissionDenied

from django.contrib.auth.models import User

from shoppingcart.models import (
    Coupon,
    CourseRegistrationCode,
    RegistrationCodeRedemption,
    Invoice,
    CourseMode,
    CourseRegistrationCodeInvoiceItem,
)
from student.models import (
    CourseEnrollment, unique_id_for_user, anonymous_id_for_user,
    UserProfile, Registration, EntranceExamConfiguration,
    ManualEnrollmentAudit, UNENROLLED_TO_ALLOWEDTOENROLL, ALLOWEDTOENROLL_TO_ENROLLED,
    ENROLLED_TO_ENROLLED, ENROLLED_TO_UNENROLLED, UNENROLLED_TO_ENROLLED,
    UNENROLLED_TO_UNENROLLED, ALLOWEDTOENROLL_TO_UNENROLLED, DEFAULT_TRANSITION_STATE
)
from lms.djangoapps.instructor.enrollment import (
    get_user_email_language,
    enroll_email,
    send_mail_to_student,
    get_email_params,
    send_beta_role_email,
    unenroll_email,
)

from instructor.enrollment import render_message_to_string
from django.core.mail import send_mail

#taskmodel

from tma_task.models import tmaTask

log = logging.getLogger(__name__)


class tma_dashboard():

    def __init__(self,course_id=None,course_key=None,request=None):

        self.request = request
        self.site_name = None
        self.course_key = course_key
        self.course_id = course_id
        self.course = get_course_by_id(course_key)
        self.course_module = modulestore().get_course(course_key, depth=0)

    def required_register_fields(self):

        register_fields = [
            {
                "name":"email",
                "required":True
            },
            {
                "name":"username",
                "required":True
            }
        ]

        _microsite_register_fields = configuration_helpers.get_value("FORM_EXTRA")

        if _microsite_register_fields is not None:
            for row in _microsite_register_fields:

                name = row.get('name')
                required = row.get('required')

                register_fields.append(
                        {
                            "name":name,
                            "required":required
                        }
                    )

        return register_fields

    def required_certificates_fields(self):

        certificates_fields = [

        ]

        _microsite_certificates_fields = configuration_helpers.get_value("CERTIFICATE_FORM_EXTRA")

        if _microsite_certificates_fields is not None:
            for row in _microsite_certificates_fields:

                name = row.get('name')
                required = row.get('required')

                certificates_fields.append(
                        {
                            "name":name,
                            "required":required
                        }
                    )

        return certificates_fields


    #password generator

    def create_user_and_user_profile(self,email, username, password, custom_field):
        """
        Create a new user, add a new Registration instance for letting user verify its identity and create a user profile.
        :param email: user's email address
        :param username: user's username
        :param name: user's name
        :param country: user's country
        :param password: user's password
        :return: User instance of the new user.
        """
        user = User.objects.create_user(username, email, password)
        reg = Registration()
        reg.register(user)

        profile = UserProfile(user=user)
        profile.custom_field = json.dumps(custom_field)
        profile.save()

        return user

    def create_and_enroll_user(self,email, username, custom_field, password, course_id, course_mode, enrolled_by, email_params):
        """
        Create a new user and enroll him/her to the given course, return list of errors in the following format
            Error format:
                each error is key-value pait dict with following key-value pairs.
                1. username: username of the user to enroll
                1. email: email of the user to enroll
                1. response: readable error message
        :param email: user's email address
        :param username: user's username
        :param name: user's name
        :param country: user's country
        :param password: user's password
        :param course_id: course identifier of the course in which to enroll the user.
        :param course_mode: mode for user enrollment, e.g. 'honor', 'audit' etc.
        :param enrolled_by: User who made the manual enrollment entry (usually instructor or support)
        :param email_params: information to send to the user via email
        :return: list of errors
        """
        errors = list()
        user = ''
        try:
            with transaction.atomic():
                # Create a new user
                user = self.create_user_and_user_profile(email, username, password, custom_field)
                # Enroll user to the course and add manual enrollment audit trail
                create_manual_course_enrollment(
                    user=user,
                    course_id=self.course_key,
                    mode=course_mode,
                    enrolled_by=enrolled_by,
                    reason='Enrolling via csv upload',
                    state_transition=UNENROLLED_TO_ENROLLED,
                )

                #add custom_field
        except IntegrityError:
            errors.append({
                'username': username, 'email': email, 'response': _('Username {user} already exists.').format(user=username)
            })
        except Exception as ex:  # pylint: disable=broad-except
            log.exception(type(ex).__name__)
            errors.append({
                'username': username, 'email': email, 'response': type(ex).__name__,
            })
        else:
            try:
                # It's a new user, an email will be sent to each newly created user.
                email_params.update({
                    'message': 'account_creation_and_enrollment',
                    'email_address': email,
                    'password': password,
                    'platform_name': self.site_name,
                })
                #update sitename params
                email_params['site_name'] = self.site_name
                send_mail_to_student(email, email_params)
            except Exception as ex:  # pylint: disable=broad-except
                log.exception(
                    "Exception '{exception}' raised while sending email to new user.".format(exception=type(ex).__name__)
                )
                errors.append({
                    'username': username,
                    'email': email,
                    'response':
                        _("Error '{error}' while sending email to new user (user email={email}). "
                          "Without the email student would not be able to login. "
                          "Please contact support for further information.").format(error=type(ex).__name__, email=email),
                })
            else:
                log.info(u'email sent to new created user at %s', email)

        return user

    #enroll
    def send_mail_to_student(self,student, param_dict, language=None):
        """
        Construct the email using templates and then send it.
        `student` is the student's email address (a `str`),
        `param_dict` is a `dict` with keys
        [
            `site_name`: name given to edX instance (a `str`)
            `registration_url`: url for registration (a `str`)
            `display_name` : display name of a course (a `str`)
            `course_id`: id of course (a `str`)
            `auto_enroll`: user input option (a `str`)
            `course_url`: url of course (a `str`)
            `email_address`: email of student (a `str`)
            `full_name`: student full name (a `str`)
            `message`: type of email to send and template to use (a `str`)
            `is_shib_course`: (a `boolean`)
        ]
        `language` is the language used to render the email. If None the language
        of the currently-logged in user (that is, the user sending the email) will
        be used.
        Returns a boolean indicating whether the email was sent successfully.
        """

        # add some helpers and microconfig subsitutions

        if 'display_name' in param_dict:
            param_dict['course_name'] = param_dict['display_name']

        """
        param_dict['site_name'] = configuration_helpers.get_value(
            'SITE_NAME',
            param_dict['site_name']
        )
        """
        subject = None
        message = None

        # see if there is an activation email template definition available as configuration,
        # if so, then render that
        message_type = param_dict['message']

        email_template_dict = {
            'allowed_enroll': (
                'emails/enroll_email_allowedsubject.txt',
                'emails/enroll_email_allowedmessage.txt'
            ),
            'enrolled_enroll': (
                'emails/enroll_email_enrolledsubject.txt',
                'emails/enroll_email_enrolledmessage.txt'
            ),
            'allowed_unenroll': (
                'emails/unenroll_email_subject.txt',
                'emails/unenroll_email_allowedmessage.txt'
            ),
            'enrolled_unenroll': (
                'emails/unenroll_email_subject.txt',
                'emails/unenroll_email_enrolledmessage.txt'
            ),
            'add_beta_tester': (
                'emails/add_beta_tester_email_subject.txt',
                'emails/add_beta_tester_email_message.txt'
            ),
            'remove_beta_tester': (
                'emails/remove_beta_tester_email_subject.txt',
                'emails/remove_beta_tester_email_message.txt'
            ),
            'account_creation_and_enrollment': (
                'emails/enroll_email_enrolledsubject.txt',
                'emails/account_creation_and_enroll_emailMessage.txt'
            ),
        }

        subject_template, message_template = email_template_dict.get(message_type, (None, None))
        if subject_template is not None and message_template is not None:
            subject, message = render_message_to_string(
                subject_template, message_template, param_dict, language=language
            )

        if subject and message:
            # Remove leading and trailing whitespace from body
            message = message.strip()

            # Email subject *must not* contain newlines
            subject = ''.join(subject.splitlines())
            from_address = configuration_helpers.get_value(
                'email_from_address',
                settings.DEFAULT_FROM_EMAIL
            )

            send_mail(subject, message, from_address, [student], fail_silently=False)

    def generate_unique_password(self,generated_passwords, password_length=12):
        """
        generate a unique password for each student.
        """

        password = generate_random_string(password_length)
        while password in generated_passwords:
            password = generate_random_string(password_length)

        generated_passwords.append(password)

        return password

    def task_generate_user(self):
        #ici self. request correspond a task_input du systeme de task
        task_input = self.request
        #row valide issues du csv
        valid_rows = task_input.get("valid_rows")
        #microsite prefix
        microsite = task_input.get("microsite")
        log.warning(u'tma_dashboard.task_generate_user inscription users pour le microsite : '+microsite)
        #info du register_form associe au microsite
        register_form = task_input.get("register_form")
        #requester id
        requester_id = task_input.get("requester_id")
        #requester user
        _requester_user = User.objects.get(pk=requester_id)
        #site_name hydrate
        self.site_name = task_input.get('site_name')+' '

        log.warning(u'tma_dashboard.task_generate_user inscription users par le username '+_requester_user.username+' email : '+_requester_user.email)
        #generated passwords
        generated_passwords = []
        #tableau de retour confirmant les utilisateurs cree compose du dict {"id":int,"email":"example@example.com"}
        _generates = []
        #tableau de retour donannt les utilisateurs dont le compte n'a pas ete cree dans un dict tel que {"email":"example@example.com","response":"la raison du fail"}
        _failed = []
        #warning field
        warnings = []
        #preparer la list contenant les keys du register form induit
        register_keys = []
        for _key in register_form:
            register_keys.append(_key.get('name'))
        # for white labels we use 'shopping cart' which uses CourseMode.DEFAULT_SHOPPINGCART_MODE_SLUG as
        # course mode for creating course enrollments.
        if CourseMode.is_white_label(self.course_key):
            course_mode = CourseMode.DEFAULT_SHOPPINGCART_MODE_SLUG
        else:
            course_mode = None
        #action sur chacunes des rows
        for _user in valid_rows:
            #get current users values
            email = _user.get('email')
            username = _user.get('username')

            #check is validate email
            email_params = get_email_params(self.course, True, secure=True)
            try:
                validate_email(email)  # Raises ValidationError if invalid
            except ValidationError:
                _failed.append({
                    'email': email, 'response': _('Invalid email {email_address}.').format(email_address=email)})
            else:
                #check if email exist
                log.info(
                    u"user '%s' and '%s'",
                    username,
                    email
                )
                User.objects.filter(email=email)
                if User.objects.filter(email=email).exists():
                    # Email address already exists. assume it is the correct user
                    # and just register the user in the course and send an enrollment email.
                    user = User.objects.get(email=email)

                    # see if it is an exact match with email and username
                    # if it's not an exact match then just display a warning message, but continue onwards
                    if not User.objects.filter(email=email, username=username).exists():
                        warning_message = _(
                            'An account with email {email} exists but the provided username {username} '
                            'is different. Enrolling anyway with {email}.'
                        ).format(email=email, username=username)

                        warnings.append({
                            'username': username, 'email': email, 'response': warning_message
                        })
                        log.warning(u'email %s already exist', email)
                    else:
                        log.info(
                            u"user already exists with username '%s' and email '%s'",
                            username,
                            email
                        )
                    # enroll a user if it is not already enrolled.
                    if not CourseEnrollment.is_enrolled(user, self.course_key):
                        # Enroll user to the course and add manual enrollment audit trail
                        create_manual_course_enrollment(
                            user=user,
                            course_id=self.course_key,
                            mode=course_mode,
                            enrolled_by=_requester_user,
                            reason='Enrolling via csv upload',
                            state_transition=UNENROLLED_TO_ENROLLED,
                        )
                        enroll_email(course_id=self.course_key, student_email=email, auto_enroll=True, email_students=True, email_params=email_params)
                else:
                    # This email does not yet exist, so we need to create a new account
                    # If username already exists in the database, then create_and_enroll_user
                    # will raise an IntegrityError exception.
                    #generate password
                    password = self.generate_unique_password(generated_passwords)
                    #generate custom_field
                    custom_field = {}
                    #ajout user dans les donnees depuis les key
                    for key,value in _user.items():
                        #assurer que la key est presente dans la liste des key et non presente dans les custom_fields actuels
                        if (key in register_keys) and (not key in custom_field.keys()):
                            custom_field[key] = value

                    created_user = self.create_and_enroll_user(
                        email, username, custom_field, password, self.course_id, course_mode, _requester_user, email_params
                    )
                    #maj de l'info
                    if created_user != '':
                        _generates.append(
                            {"id":created_user.id,"email":created_user.email})
                    else:
                        _failed.append(
                            {"email":email,"reponse":"creation failed"})
        log.warning(u'tma_dashboard.task_generate_user fin inscription users pour le microsite : '+microsite)
        log.warning(u'tma_dashboard.task_generate_user fin inscription users par le username '+_requester_user.username+' email : '+_requester_user.email)

        retour = {
            "requester": _requester_user.email,
            "_generates": _generates,
            "_failed": _failed,
            "warning": warnings
        }

        return retour

    def as_views(self):

        _stat_dashboard_api = _stat_dashboard_api = stat_dashboard_api(self.request,self.course_id,course_key=self.course_key)
        course_structure = _stat_dashboard_api.get_course_structure()

        #ensure user is @themoocagency.com
        _email = self.request.user.email
        if "@themoocagency.com" in _email:
            csv_limits = False
        else:
            csv_limits = True

        context = {
            "course_id":self.course_id,
            "course":self.course,
            "course_module":self.course_module,
            "course_structure":course_structure,
            "register_fields":self.required_register_fields(),
            "certificates_fields":self.required_certificates_fields(),
            "csv_limits":csv_limits
        }

        return render_to_response('tma_dashboard.html', context)

    def ensure_user_exists(self):

        list_users = json.loads(self.request.body)

        _username = []
        _email = []

        for u in list_users:
            _id = u.get('id')
            email = u.get('email')
            username = u.get('username')
            try:
                user = User.objects.get(email=email)
                q = {
                    "id":_id,
                    "email":email
                }
                _email.append(q)
            except:
                pass
            try:
                user = User.objects.get(username=username)
                q = {
                    "id":_id,
                    "username":username
                }
                _username.append(q)   
            except:
                pass    

        context = {
            "username":_username,
            "email":_email
        } 

        return context

    def user_grade_task_list(self):
        task_type = "user_generation"
        course_key = self.course_key
        task_list = tmaTask.objects.all().filter(course_id=course_key,task_type=task_type)
        return_list = []
        for task in task_list:

            requester = User.objects.get(pk=task.requester_id)

            q = {}
            
            q['id'] = task.id

            q['requester'] = {
                "id":requester.id,
                "email":requester.email,
                "username":requester.username,
            }
	    try:
                q['output'] = json.loads(task.task_output)
            except:
                q['output'] = {}
            q['date'] = task.created
            q['progress'] = task.task_state

            return_list.append(q);

        return return_list



