import json
from json import JSONDecodeError
import logging
from typing import Callable
from typing import List
from typing import Optional
from typing import Union

from cryptojwt.key_jar import KeyJar
from idpyoidc.client.client_auth import client_auth_setup
from idpyoidc.client.configure import Configuration
from idpyoidc.client.defaults import SUCCESSFUL
from idpyoidc.client.exception import OidcServiceError
from idpyoidc.client.exception import ParseError
from idpyoidc.client.service import init_services
from idpyoidc.client.service import REQUEST_INFO
from idpyoidc.client.service import Service
from idpyoidc.client.util import get_deserialization_method
from idpyoidc.exception import FormatError
from idpyoidc.message import Message

from fedservice.defaults import DEFAULT_OIDC_FED_SERVICES
from fedservice.entity import FederationContext
from fedservice.node import ClientNode

logger = logging.getLogger(__name__)


class FederationServiceContext(FederationContext):
    def __init__(self,
                 config: Optional[Union[dict, Configuration]] = None,
                 entity_id: str = "",
                 superior_get: Callable = None,
                 keyjar: Optional[KeyJar] = None,
                 priority: Optional[List[str]] = None,
                 trust_marks: Optional[List[str]] = None,
                 trusted_roots: Optional[dict] = None,
                 ):

        if config is None:
            config = {}

        FederationContext.__init__(self,
                                   config=config,
                                   entity_id=entity_id,
                                   superior_get=superior_get,
                                   keyjar=keyjar)

        self.trust_mark_issuer = None
        self.signed_trust_marks = []
        self.trust_marks = trust_marks

        if trusted_roots:
            _trusted_roots = trusted_roots
        else:
            _trusted_roots = config.get("trusted_roots")

        if _trusted_roots is None:
            # Must be trust anchor then
            self.trusted_roots = {}
        elif isinstance(_trusted_roots, str):
            self.trusted_roots = json.loads(open(_trusted_roots).read())
        else:
            self.trusted_roots = _trusted_roots

        _key_jar = self.superior_get("attribute", "keyjar")
        for iss, jwks in self.trusted_roots.items():
            _key_jar.import_jwks(jwks, iss)

        if priority:
            self.tr_priority = priority
        elif 'priority' in config:
            self.tr_priority = config["priority"]
        else:
            self.tr_priority = sorted(set(self.trusted_roots.keys()))


class FederationEntityClient(ClientNode):
    def __init__(
            self,
            superior_get: Callable = None,
            keyjar: Optional[KeyJar] = None,
            config: Optional[Union[dict, Configuration]] = None,
            httpc: Optional[object] = None,
            httpc_params: Optional[dict] = None,
            services: Optional[dict] = None,
            jwks_uri: Optional[str] = "",
    ):
        """

        :param keyjar: A py:class:`idpyoidc.key_jar.KeyJar` instance
        :param config: Configuration information passed on to the
            :py:class:`idpyoidc.client.service_context.ServiceContext`
            initialization
        :param httpc: A HTTP client to use
        :param services: A list of service definitions
        :param jwks_uri: A jwks_uri
        :param httpc_params: HTTP request arguments
        :return: Client instance
        """

        ClientNode.__init__(self, superior_get=superior_get, httpc=httpc,
                            keyjar=keyjar, httpc_params=httpc_params,
                            config=config, jwks_uri=jwks_uri)

        self._service_context = FederationServiceContext(config=config, superior_get=self.node_get)

        _srvs = services or DEFAULT_OIDC_FED_SERVICES

        self._service = init_services(service_definitions=_srvs, superior_get=self.node_get)

        self.setup_client_authn_methods(config)

    def get_attribute(self, attr, *args):
        val = getattr(self, attr)
        if val:
            return val
        else:
            return self.superior_get('attribute', attr)

    def get_service(self, service_name, *arg):
        try:
            return self._service[service_name]
        except KeyError:
            return None

    def get_context(self, *args):
        return self._service_context

    def setup_client_authn_methods(self, config):
        if config and "client_authn_methods" in config:
            self._service_context.client_authn_method = client_auth_setup(
                config.get("client_authn_methods")
            )
        else:
            self._service_context.client_authn_method = {}

    def do_request(
            self,
            request_type: str,
            response_body_type: Optional[str] = "",
            request_args: Optional[dict] = None,
            behaviour_args: Optional[dict] = None,
            **kwargs
    ):
        _srv = self._service[request_type]

        _info = _srv.get_request_parameters(request_args=request_args, **kwargs)

        if not response_body_type:
            response_body_type = _srv.response_body_type

        logger.debug("do_request info: {}".format(_info))

        try:
            _state = kwargs["state"]
        except:
            _state = ""
        return self.service_request(
            _srv, response_body_type=response_body_type, state=_state, **_info
        )

    def set_client_id(self, client_id):
        self._service_context.set("client_id", client_id)

    def get_response(
            self,
            service: Service,
            url: str,
            method: Optional[str] = "GET",
            body: Optional[dict] = None,
            response_body_type: Optional[str] = "",
            headers: Optional[dict] = None,
            **kwargs
    ):
        """

        :param url:
        :param method:
        :param body:
        :param response_body_type:
        :param headers:
        :param kwargs:
        :return:
        """
        try:
            resp = self.http(url, method, data=body, headers=headers)
        except Exception as err:
            logger.error("Exception on request: {}".format(err))
            raise

        if 300 <= resp.status_code < 400:
            return {"http_response": resp}

        if resp.status_code < 300:
            if "keyjar" not in kwargs:
                kwargs["keyjar"] = service.superior_get("context").keyjar
            if not response_body_type:
                response_body_type = service.response_body_type

            if response_body_type == "html":
                return resp.text

            if body:
                kwargs["request_body"] = body

        return self.parse_request_response(service, resp, response_body_type, **kwargs)

    def service_request(
            self,
            service: Service,
            url: str,
            method: Optional[str] = "GET",
            body: Optional[dict] = None,
            response_body_type: Optional[str] = "",
            headers: Optional[dict] = None,
            **kwargs
    ) -> Message:
        """
        The method that sends the request and handles the response returned.
        This assumes that the response arrives in the HTTP response.

        :param service: The Service instance
        :param url: The URL to which the request should be sent
        :param method: Which HTTP method to use
        :param body: A message body if any
        :param response_body_type: The expected format of the body of the
            return message
        :param httpc_params: Arguments for the HTTP client
        :return: A cls or ResponseMessage instance or the HTTP response
            instance if no response body was expected.
        """

        if headers is None:
            headers = {}

        logger.debug(REQUEST_INFO.format(url, method, body, headers))

        try:
            response = service.get_response_ext(
                url, method, body, response_body_type, headers, **kwargs
            )
        except AttributeError:
            response = self.get_response(
                service, url, method, body, response_body_type, headers, **kwargs
            )

        if "error" in response:
            pass
        else:
            try:
                kwargs["key"] = kwargs["state"]
            except KeyError:
                pass

            service.update_service_context(response, **kwargs)
        return response

    def parse_request_response(self, service, reqresp, response_body_type="", state="",
                               **kwargs):
        """
        Deal with a self.http response. The response are expected to
        follow a special pattern, having the attributes:

            - headers (list of tuples with headers attributes and their values)
            - status_code (integer)
            - text (The text version of the response)
            - url (The calling URL)

        :param service: A :py:class:`idpyoidc.client.service.Service` instance
        :param reqresp: The HTTP request response
        :param response_body_type: If response in body one of 'json', 'jwt' or
            'urlencoded'
        :param state: Session identifier
        :param kwargs: Extra keyword arguments
        :return:
        """

        # if not response_body_type:
        #     response_body_type = self.response_body_type

        if reqresp.status_code in SUCCESSFUL:
            logger.debug('response_body_type: "{}"'.format(response_body_type))
            _deser_method = get_deserialization_method(reqresp)

            if _deser_method != response_body_type:
                logger.warning(
                    "Not the body type I expected: {} != {}".format(
                        _deser_method, response_body_type
                    )
                )
            if _deser_method in ["json", "jwt", "urlencoded"]:
                value_type = _deser_method
            else:
                value_type = response_body_type

            logger.debug("Successful response: {}".format(reqresp.text))

            try:
                return service.parse_response(reqresp.text, value_type, state, **kwargs)
            except Exception as err:
                logger.error(err)
                raise
        elif reqresp.status_code in [302, 303]:  # redirect
            return reqresp
        elif reqresp.status_code == 500:
            logger.error("(%d) %s" % (reqresp.status_code, reqresp.text))
            raise ParseError("ERROR: Something went wrong: %s" % reqresp.text)
        elif 400 <= reqresp.status_code < 500:
            logger.error(
                "Error response ({}): {}".format(reqresp.status_code, reqresp.text))
            # expecting an error response
            _deser_method = get_deserialization_method(reqresp)
            if not _deser_method:
                _deser_method = "json"

            try:
                err_resp = service.parse_response(reqresp.text, _deser_method)
            except (FormatError, ValueError):
                if _deser_method != response_body_type:
                    try:
                        err_resp = service.parse_response(reqresp.text, response_body_type)
                    except (OidcServiceError, FormatError, ValueError):
                        raise OidcServiceError(
                            "HTTP ERROR: %s [%s] on %s"
                            % (reqresp.text, reqresp.status_code, reqresp.url)
                        )
                else:
                    raise OidcServiceError(
                        "HTTP ERROR: %s [%s] on %s"
                        % (reqresp.text, reqresp.status_code, reqresp.url)
                    )
            except JSONDecodeError:  # So it's not JSON assume text then
                err_resp = {"error": reqresp.text}

            err_resp["status_code"] = reqresp.status_code
            return err_resp
        else:
            logger.error(
                "Error response ({}): {}".format(reqresp.status_code, reqresp.text))
            raise OidcServiceError(
                "HTTP ERROR: %s [%s] on %s" % (
                    reqresp.text, reqresp.status_code, reqresp.url)
            )
