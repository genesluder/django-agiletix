


import json

from django.utils import timezone

from agiletixapi import AgileError, AgileSalesAPI
from agiletixapi.exceptions import AgileException, InvalidPromoException
from agiletixapi.models import Order
from agiletixapi.utils import datestring_to_ms_datestring
from agiletix.logging import get_logger
logger = get_logger('lib')
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


def get_or_create_cart_for_request(request, force_non_member=False):
    """
    Try to retrieve cart from the current session. If none found, create one

    """
    cart = None
    try:
        cart = get_cart_for_request(request)
        if not cart or (force_non_member and cart and cart.is_member):
            cart = Cart(request)
            cart.start_order(force_non_member=force_non_member)
    except AgileException as e:
        # TODO: Yeha
        #logger.warning(__name__, "AgileException -> {}".format(e))
        if e.code == 1024:
            cart = get_or_create_cart_for_request(request, force_non_member=True)
        #cart_error = e.code

    return cart


    def get_cart(self, request):
        cart_error = None
        cart = None

        if not cart:
            logger.warning(__name__, "Couldn't load cart")
            cart_error = -1
        return cart, cart_error




class Cart(object):

    def __init__(self, request, order=None):
        self._order = None
        self.request = request

        self.is_member = False

        if request.user.is_authenticated:
            customer = request.user
            if customer.member_id:
                self.is_member = True

        if order:
            self.order = order

    def start_order(self, force_non_member=False):
        customer = None
        response = None    

        if self.request.user.is_authenticated:
            customer = self.request.user

        if customer:
            if customer.member_id and not force_non_member:
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
            logger.debug("Order started", response=response.data)
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
            logger.debug("Order loaded", order_json=json_object)
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
        if self.request.user.is_authenticated:
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
        quantities = ",".join([str(tickets[t]) for t in tickets.keys()])
        self.add_ticket(
            agile_event_org_id=agile_event_org_id, 
            agile_event_id=agile_event_id, 
            tier_id=tier_id, 
            ticket_types=ticket_types, 
            quantities=quantities, 
            promo_codes=promo_codes
        )

    def add_ticket(self, agile_event_org_id, agile_event_id, tier_id, ticket_types, quantities, promo_codes=None):
        order = self.order

        if promo_codes:
            promo_codes = ",".join(promo_codes)

        logger.debug("Adding ticket payload to cart",            
            order_id=order.order_id, 
            transaction_id=order.transaction_id, 
            agile_event_org_id=agile_event_org_id, 
            agile_event_id=agile_event_id, 
            tier_id=tier_id,
            ticket_types=ticket_types, 
            quantities=quantities,
            promo_codes=promo_codes
        )

        response = api.tickets_add(
            order.order_id, 
            order.transaction_id, 
            agile_event_org_id, 
            agile_event_id, 
            tier_id,
            ticket_types, 
            quantities,
            promo_codes=promo_codes
        )
        logger.debug("Adding ticket response", response=response.data) 
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

