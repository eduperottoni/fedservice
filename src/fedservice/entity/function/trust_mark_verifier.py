import logging
from typing import Callable
from typing import Optional

from cryptojwt import KeyBundle
from cryptojwt.jws.jws import factory
from cryptojwt.jwt import utc_time_sans_frac

from fedservice import message
from fedservice.entity.function import collect_trust_chains
from fedservice.entity.function import Function
from fedservice.entity.function import get_payload
from fedservice.entity.function import verify_trust_chains
from fedservice.entity_statement.statement import TrustChain

logger = logging.getLogger(__name__)


class TrustMarkVerifier(Function):
    def __init__(self, superior_get: Callable):
        Function.__init__(self, superior_get)

    def __call__(self, trust_mark: str, check_status: Optional[bool] = False, entity_id:
                Optional[str] = ''):
        """
        Verifies that a trust mark is issued by someone in the federation and that
        the signing key is a federation key.

        :param trust_mark: A signed JWT representing a trust mark
        :returns: TrustClaim message instance if OK otherwise None
        """

        payload = get_payload(trust_mark)
        _trust_mark = message.TrustMark(**payload)
        # Verify that everything that should be there is there
        _trust_mark.verify()

        # Has it expired ?
        _expires_at = payload.get("exp")
        if _expires_at:
            if _expires_at < utc_time_sans_frac():
                return None

        # Get trust chain
        _federation_entity = self.superior_get("node").superior_get('node')
        _chains, _ = collect_trust_chains(_federation_entity, _trust_mark['iss'])
        _trust_chains = verify_trust_chains(_federation_entity, _chains)

        # Now try to verify the signature on the trust_mark
        # should have the necessary keys
        _jwt = factory(trust_mark)
        keyjar = _federation_entity.superior_get("attribute", "keyjar")
        try:
            _mark = _jwt.verify_compact(trust_mark, keys=keyjar.get_jwt_verify_keys(_jwt.jwt))
        except Exception as err:
            return None
        else:
            return _mark