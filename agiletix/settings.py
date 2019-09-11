
from django.conf import settings

AGILE_SETTINGS = getattr(settings, 'AGILE_SETTINGS', {})

required_settings = [
    'AGILE_BASE_URL',
    'AGILE_APP_KEY',
    'AGILE_USER_KEY',
    'AGILE_CORP_ORG_ID',
    'AGILE_BUYER_TYPE_STANDARD_ID',
    'AGILE_USE_MEMBERSHIP_ID',
]

for key in required_settings:
    if not key in AGILE_SETTINGS.keys():
        raise ImproperlyConfigured('{0} is required in AGILE_SETTINGS'.format())

AGILE_SETTINGS.setdefault('AGILE_RESPONSE_FORMAT', 'json')
AGILE_SETTINGS.setdefault('AGILE_DATE_FORMAT', '%Y-%m-%dT%H:%M:%S')

