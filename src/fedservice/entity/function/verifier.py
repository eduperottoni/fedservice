import logging
from typing import Callable

from cryptojwt import KeyBundle
from cryptojwt.jws.jws import factory

from fedservice.entity.function import Function
from fedservice.entity_statement.statement import TrustChain

logger = logging.getLogger(__name__)


class TrustChainVerifier(Function):
    def __init__(self, superior_get: Callable):
        Function.__init__(self, superior_get)

    def trusted_anchor(self, entity_statement):
        _jwt = factory(entity_statement)
        payload = _jwt.jwt.payload()
        _keyjar = self.superior_get("attribute", "keyjar")
        if payload['iss'] not in _keyjar:
            logger.warning(
                f"Trust chain ending in a trust anchor I do not know: {payload['iss']}", )
            return False

        return True

    def verify_trust_chain(self, entity_statement_list):
        """

        :param entity_statement_list: List of entity statements. The entity's self-signed statement last.
        :return: A sequence of verified entity statements
        """
        ves = []

        if not self.trusted_anchor(entity_statement_list[0]):
            # Trust chain ending in a trust anchor I don't know.
            return ves

        n = len(entity_statement_list) - 1
        _keyjar = self.superior_get("attribute", "keyjar")
        for entity_statement in entity_statement_list:
            _jwt = factory(entity_statement)
            if _jwt:
                logger.debug("JWS header: %s", _jwt.headers())
                keys = _keyjar.get_jwt_verify_keys(_jwt.jwt)
                _key_spec = ['{}:{}:{}'.format(k.kty, k.use, k.kid) for k in keys]
                logger.debug("Possible verification keys: %s", _key_spec)
                res = _jwt.verify_compact(keys=keys)
                logger.debug("Verified entity statement: %s", res)
                try:
                    _jwks = res['jwks']
                except KeyError:
                    if len(ves) != n:
                        raise ValueError('Missing signing JWKS')
                else:
                    _kb = KeyBundle(keys=_jwks['keys'])
                    try:
                        old = _keyjar.get_issuer_keys(res['sub'])
                    except KeyError:
                        _keyjar.add_kb(res['sub'], _kb)
                    else:
                        new = [k for k in _kb if k not in old]
                        if new:
                            _key_spec = ['{}:{}:{}'.format(k.kty, k.use, k.kid) for k in new]
                            logger.debug(
                                "New keys added to the federation key jar for '{}': {}".format(
                                    res['sub'], _key_spec)
                            )
                            # Only add keys to the KeyJar if they are not already there.
                            _kb.set(new)
                            _keyjar.add_kb(res['sub'], _kb)

                ves.append(res)

        return ves

    def trust_chain_expires_at(self, trust_chain):
        exp = -1
        for entity_statement in trust_chain:
            if exp >= 0:
                if entity_statement['exp'] < exp:
                    exp = entity_statement['exp']
            else:
                exp = entity_statement['exp']
        return exp

    def __call__(self, trust_chain: list):
        """

        :param trust_chain: A chain of entity statements
        :param entity_type: Which type of metadata you want returned
        :param apply_policies: Apply policies to the metadata or not
        :returns: A TrustChain instances
        """
        logger.debug("Evaluate trust chain")
        verified_trust_chain = self.verify_trust_chain(trust_chain)

        if not verified_trust_chain:
            return None

        _expires_at = self.trust_chain_expires_at(verified_trust_chain)

        statement = TrustChain(exp=_expires_at, verified_chain=verified_trust_chain)

        iss_path = [x['iss'] for x in verified_trust_chain]
        statement.anchor = iss_path[0]
        iss_path.reverse()
        statement.iss_path = iss_path

        return statement
