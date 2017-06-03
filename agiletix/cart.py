
import logging
logger = logging.getLogger('agile')

import json

from django.utils import timezone

from agiletixapi import AgileError, AgileSalesAPI
from agiletixapi.exceptions import AgileException, InvalidPromoException
from agiletixapi.models import Order
from agiletixapi.utils import datestring_to_ms_datestring

from agiletix.settings import AGILE_SETTINGS as SETTINGS


SESSION_CART_DATA = "SESSION_CART_DATA"
SESSION_EVENT_PRICE_CACHE_KEY = "SESSION_EVENT_PRICE_CACHE_KEY"

api = AgileSalesAPI(
    base_url=SETTINGS['AGILE_BASE_URL'],
    app_key=SETTINGS['AGILE_APP_KEY'],
    user_key=SETTINGS['AGILE_USER_KEY'],
    corp_org_id=SETTINGS['AGILE_CORP_ORG_ID']
)


def get_cart_for_request(request):
    """
    Try to retrieve cart from the current session.

    """
    if hasattr(request, 'cart'):
        cart = request.cart
    else:
        cart = Cart(request)
    if cart:
        if cart.is_valid:
            request.cart = cart # Store cart on the request for the next call
            return cart
        else:
            request.session[SESSION_CART_DATA] = None

    return None


def get_or_create_cart_for_request(request):
    """
    Try to retrieve cart from the current session. If none found, create one

    """
    cart = get_cart_for_request(request)
    if not cart:
        cart = Cart(request)
        cart.start_order()
    return cart


class Cart(object):

    def __init__(self, request, order=None):
        self._order = None
        self.request = request
        if order:
            self.order = order

    def start_order(self):
        customer = None
        response = None    

        if self.request.user.is_authenticated():
            customer = self.request.user

        if customer:
            if customer.member_id:
                response = api.order_start(buyer_type_id=SETTINGS['AGILE_BUYER_TYPE_STANDARD_ID'] , customer_id=customer.customer_id, member_id=customer.member_id)
            else:
                response = api.order_start(buyer_type_id=SETTINGS['AGILE_BUYER_TYPE_STANDARD_ID'] , customer_id=customer.customer_id)

            if not response.success:
                if response.error.code == AgileError.MemberRenewalRequired:
                    raise AgileException(code=response.error.code, message=response.error.message)
                # TODO: Handle others

        if not customer or (response and not response.success):
            response = api.order_start(buyer_type_id=SETTINGS['AGILE_BUYER_TYPE_STANDARD_ID'])
        
        if response and response.success:
            order = Order(response.data)
        else:
            order = None

        self.order = order

    def load_order(self, request):
        order = None
        json_object = None
        order_json = request.session.get(SESSION_CART_DATA)
        if order_json:
            try:
                json_object = json.loads(order_json)
            except:
                pass # TODO: Better handling here
                
        if json_object:
            # Need to convert datetimes back to MS Json.NET before passing to Order object
            # CloseDateTime, ExpirationDateTime, OpenDateTime
            agile_json_object = {}
            for key, value in json_object.items():
                if "DateTime" in key:
                    agile_json_object[key] = datestring_to_ms_datestring(value)
                else:
                    agile_json_object[key] = value

            order = Order(agile_json_object)
        return order 

    @property
    def order(self):
        if not self._order:
            self._order = self.load_order(self.request)
        return self._order

    @order.setter
    def order(self, value):
        self._order = None
        self.request.session[SESSION_CART_DATA] = json.dumps(value.to_json())

    @property
    def is_valid(self):
        if not hasattr(self, '_is_valid'):
            self._is_valid = (self.order is not None and not self.is_expired and self.is_in_process and self.cart_customer_matches_current)
        return self._is_valid

    @property
    def is_in_process(self):
        in_process = False
        response = api.order_status(self.order.order_id, self.order.transaction_id)
        if response and response.success:
            try:
                order = Order(response.data)
                in_process = order.in_process
            except:
                # TODO: Better handling
                pass
        return in_process

    @property
    def is_expired(self):
        expired = (self.order.expiration_datetime < timezone.now()) or self.order.expired
        return expired

    @property
    def cart_customer_matches_current(self):
        customer = None
        if self.request.user.is_authenticated():
            customer = self.request.user
        if customer and customer.customer_id and self.order.customer_id and (int(self.order.customer_id) != int(customer.customer_id)):
            return False
        return True

    def add_tickets(self, agile_event_org_id, agile_event_id, tier_id, tickets, promo_codes=None):
        """
        Tickets is a dictionary in the format:
            { TICKET_TYPE: QUANTITY }

        """
        ticket_types = ",".join(tickets.keys()) 
        quantities = ",".join([repr(tickets[t]) for t in tickets.keys()])
        self.add_ticket(agile_event_org_id, agile_event_id, tier_id, ticket_types, quantities, promo_codes)

    def add_ticket(self, agile_event_org_id, agile_event_id, tier_id, ticket_types, quantities, promo_codes=None):

        order = self.order

        promo_code_string = None
        if promo_codes:
            promo_code_string = ",".join(promo_codes)

        response = api.tickets_add(
            order.order_id, 
            order.transaction_id, 
            agile_event_org_id, 
            agile_event_id, 
            tier_id,
            ticket_types, 
            quantities,
            promo_codes=promo_code_string
        )

        if not response.success:
            if response.error.code == 1034:
                raise InvalidPromoException
            else:
                raise AgileException(code=response.error.code, message=response.error.message)

    def get_transfer_url(self):
        response = api.order_transfer(self.order.order_id, self.order.transaction_id)
        url = None
        if response.success:
            url = response.data
            url = url.replace('http://', 'https://')
        return url

