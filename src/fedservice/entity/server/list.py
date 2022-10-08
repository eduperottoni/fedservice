import logging
from typing import Optional
from typing import Union

from idpyoidc.message import oidc
from idpyoidc.message import Message
from idpyoidc.server.endpoint import Endpoint
from idpyoidc.server.endpoint_context import init_service

logger = logging.getLogger(__name__)


class List(Endpoint):
    request_cls = oidc.Message
    # response_cls = EntityIDList
    response_format = 'json'
    name = "list"

    def __init__(self, server_get, **kwargs):
        Endpoint.__init__(self, server_get, **kwargs)

    def process_request(self, request=None, **kwargs):
        _db = self.server_get("node").subordinate
        return {'response': list(_db.keys())}

    def response_info(
            self,
            response_args: Optional[dict] = None,
            request: Optional[Union[Message, dict]] = None,
            **kwargs
    ) -> dict:
        return response_args
