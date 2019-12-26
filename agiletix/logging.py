import inspect
import json
import logging
import random
import types

from typing import cast


def get_logger(name, include_caller=True):
    return Logger(name, include_caller=include_caller)


class Logger(object):
    """
    Wrapper for the standard Python logger

    Outputs logs in the format:
    `LOGLEVEL method=METHOD_NAME: MESSAGE JSON_CONTEXT_KWARGS`

    For example:

    def find_key_to_time(self):
        logger.info(
            "Successfully found a key to time", 
            companions=["Romana", "K9"],
            form="Jethrik", 
            location="Ribos",
        )

    find_key_to_time()

    `INFO method=find_key_to_time: Successfully found a key to time 
    {"companions": ["Romana", "K9"], "form": "Jethrik", "location": "Ribos"}`
    
    """

    def __init__(self, name, include_caller=True):
        self.include_caller = include_caller
        self.logger = logging.getLogger(name)

    def __getattr__(self, name):
        def method(message, sample=100, **kwargs):
            if sample < 100:
                if random.random() > sample/100:
                    return 
            level = name.upper()
            payload = level
            if self.include_caller:
                # Ref: https://stackoverflow.com/a/57712700/
                caller_name = cast(types.FrameType, inspect.currentframe()).f_back.f_code.co_name
                payload = '{} method={}'.format(payload, caller_name)
            context = json.dumps(kwargs)
            payload = '{}: {} {}'.format(payload, message, context)
            if self.logger.isEnabledFor(getattr(logging, level)):                                        
                getattr(self.logger, name)(payload)
        return method
