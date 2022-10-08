from typing import Callable
from typing import Optional
from typing import Union
from urllib.parse import urlencode

from idpyoidc.client.configure import Configuration
from idpyoidc.client.service import Service
from idpyoidc.message import oauth2
from idpyoidc.message.oauth2 import ResponseMessage

from fedservice import message


def construct_entity_configuration_query(api_endpoint, issuer="", subject=""):
    if issuer:
        if subject:
            query = urlencode({"iss": issuer, "sub": subject})
        else:
            query = urlencode({"iss": issuer})

        return f"{api_endpoint}?{query}"
    else:
        return f"{api_endpoint}"


class EntityStatement(Service):
    """The service that talks to the OIDC federation Fetch endpoint."""

    msg_type = oauth2.Message
    response_cls = message.EntityStatement
    error_msg = ResponseMessage
    synchronous = True
    service_name = "entity_statement"
    http_method = "GET"

    def __init__(self,
                 superior_get: Callable,
                 conf:Optional[Union[dict, Configuration]] = None):
        Service.__init__(self, superior_get, conf=conf)

    def get_request_parameters(
            self,
            request_args: Optional[dict] = None,
            method: Optional[str] = "",
            request_body_type: Optional[str] = "",
            authn_method: Optional[str] = "",
            fetch_endpoint: Optional[str] = "",
            issuer: Optional[str] = "",
            subject: Optional[str] = "",
            **kwargs
    ) -> dict:
        """
        Builds the request message and constructs the HTTP headers.

        :param method: HTTP method used.
        :param authn_method: Client authentication method
        :param request_args: Message arguments
        :param request_body_type:
        :param fetch_endpoint:
        :param issuer:
        :param subject:
        :param kwargs: extra keyword arguments
        :return: Dictionary with the necessary information for the HTTP request
        """
        if not method:
            method = self.http_method

        if not fetch_endpoint:
            raise AttributeError("Missing endpoint")

        if issuer:
            _q_args = {'iss': issuer}
            if subject:
                _q_args['sub'] = subject

            query = urlencode(_q_args)
            _url = f"{fetch_endpoint}?{query}"
        else:
            _url = f"{fetch_endpoint}"

        return {"url": _url, 'method': method}
