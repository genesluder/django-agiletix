
import re

from django.contrib import messages
from django.contrib.auth import get_user_model

from agiletixapi import AgileError, AgileSalesAPI
from agiletixapi.models import AgileCustomer

from agiletix.settings import AGILE_SETTINGS as SETTINGS


EMAIL_REGEX = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
User = get_user_model()


class AgileBackend(object):

    def authenticate(self, request,  username=None, password=None):

        api = AgileSalesAPI(
            base_url=SETTINGS['AGILE_BASE_URL'],
            app_key=SETTINGS['AGILE_APP_KEY'],
            user_key=SETTINGS['AGILE_USER_KEY'],
            corp_org_id=SETTINGS['AGILE_CORP_ORG_ID']
        )

        username_type = 'username'

        if username.isdigit():
            # A member number was specified
            username_type = 'member number'
            response = api.authenticate_member(43, username, password)
        else:
            # Detemine if an email was specified
            if re.search(EMAIL_REGEX, username):
                username_type = 'email'
                response = api.authenticate_email(username, password)
            else:
                response = api.authenticate_customer(username, password)

        if response.success:

            agile_customer = AgileCustomer(response.data)

            member = None
            user = None

            if len(agile_customer.members) > 0:
                # For now, we only support a single membership program type
                # but allow use of particular membership type
                member = None
                for m in agile_customer.members:
                    if m.membership_id == SETTINGS['AGILE_USE_MEMBERSHIP_ID']:
                        member = m
                if not member:
                    member = agile_customer.members[0]
            
            try:
                user = User.objects.get(customer_id=agile_customer.customer_id)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(username=agile_customer.customer_id)
                except User.DoesNotExist:
                    user = User.objects.create_agile_user(
                        agile_customer.customer_id, 
                        customer_name=agile_customer.customer_name, 
                    )
            finally:
                if user:
                    user.customer_id = agile_customer.customer_id 
                    user.customer_name = agile_customer.customer_name 
                    if member:
                        user.member_number = member.member_number
                        user.membership_id = member.membership_id
                        user.member_id = member.member_id  
                    user.save()

            return user

        else:
            if response.error.code == AgileError.OnlineAccountRequired:
                messages.add_message(request, messages.ERROR, 'An online account is required for this membership.')
            elif response.error.code == AgileError.MemberNotValid: 
                messages.add_message(request, messages.ERROR, 'This membership is no longer valid.')
            elif response.error.code == AgileError.MemberRenewalRequired: 
                messages.add_message(request, messages.ERROR, 'This membership needs to be renewed. Please visit "My Account" to renew.')
            elif response.error.code == AgileError.MemberExpired: 
                messages.add_message(request, messages.ERROR, 'This membership has expired. Please visit "My Account" to renew.')
            else:
                messages.add_message(request, messages.ERROR, 'The {0} or password you entered is not correct.'.format(username_type))

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

