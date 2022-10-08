import json
import os

from idpyoidc.server.util import execute
import pytest

from fedservice.combo import FederationCombo
from fedservice.entity import FederationEntity
from fedservice.entity.client import FederationEntityClient
from fedservice.entity.client.entity_configuration import \
    EntityConfiguration as c_EntityConfiguration
from fedservice.entity.client.entity_statement import EntityStatement
from fedservice.entity.function.trust_chain_collector import TrustChainCollector
from fedservice.entity.server import FederationEntityServer
from fedservice.entity.server.entity_configuration import \
    EntityConfiguration as s_EntityConfiguration
from fedservice.entity.server.fetch import Fetch
from fedservice.trust_mark_issuer import TrustMarkIssuer
from fedservice.trust_mark_issuer.status import Status

KEYDEFS = [
    {"type": "RSA", "key": "", "use": ["sig"]},
    {"type": "EC", "crv": "P-256", "use": ["sig"]},
]

BASE_PATH = os.path.abspath(os.path.dirname(__file__))

jwks = open(os.path.join(BASE_PATH, 'base_data', 'feide.no', 'feide.no', 'jwks.json')).read()
ANCHOR = {'https://feide.no': json.loads(jwks)}

OPPONENT_ID = "https://example.org"
TENNANT_ID = "https://example.org/tennant1"
ENTITY_ID = "https://entity.example.org"
ISSUER = "https://example.org/adm1"


class TestFederationEntity(object):
    @pytest.fixture(autouse=True)
    def server_setup(self):
        config = {
            'class': FederationEntity,
            "kwargs": {
                "metadata": {
                    "organization_name": "The example cooperation",
                    "homepage_uri": "https://www.example.com",
                    "contacts": "operations@example.com"
                },
                "function": {
                    "class": TrustChainCollector,
                    "kwargs": {
                        "trust_anchors": ANCHOR,
                        "allowed_delta": 600
                    }
                },
                "entity_id": ENTITY_ID,
                "client": {
                    'class': FederationEntityClient,
                    'kwargs': {
                        "services": {
                            "entity_configuration": {
                                "class": c_EntityConfiguration,
                                "kwargs": {}
                            },
                            "entity_statement": {
                                "class": EntityStatement,
                                "kwargs": {}
                            }
                        }
                    }
                },
                "server": {
                    'class': FederationEntityServer,
                    'kwargs': {
                        "metadata": {
                            "authority_hints": ['https://ntnu.no'],
                        },
                        "endpoint": {
                            "entity_configuration": {
                                "path": ".well-known/openid-federation",
                                "class": s_EntityConfiguration,
                                "kwargs": {}
                            },
                            "fetch": {
                                "path": "fetch",
                                "class": Fetch,
                                "kwargs": {}
                            }
                        }
                    }
                }
            }
        }

        self.entity = execute(config)

    def test_metadata(self):
        metadata = self.entity.get_metadata()
        assert list(metadata.keys()) == ['federation_entity']
        assert set(metadata['federation_entity'].keys()) == {'organization_name',
                                                             'contacts',
                                                             'homepage_uri',
                                                             'federation_fetch_endpoint'}

    def test_create_entity_configuration(self):
        _endpoint = self.entity.server.get_endpoint('entity_configuration')
        _req = _endpoint.parse_request({})
        _resp_args = _endpoint.process_request(_req)
        assert _resp_args


TM_ID = "https://refeds.org/wp-content/uploads/2016/01/Sirtfi-1.0.pdf"


class TestTrustIssuer(object):
    @pytest.fixture(autouse=True)
    def server_setup(self):
        config = {
            "entity_id": ENTITY_ID,
            "endpoint": {
                "trust_mark_status": {
                    'path': 'status',
                    'class': Status,
                    'kwargs': {}
                }
            },
            'trust_marks': {
                TM_ID: {"ref": "https://refeds.org/sirtfi"}
            }
        }

        self.entity = TrustMarkIssuer(**config)

    def test_metadata(self):
        metadata = self.entity.get_metadata()
        assert list(metadata.keys()) == ['trust_mark_issuer']
        assert set(metadata['trust_mark_issuer'].keys()) == {'federation_status_endpoint'}


class TestCombo(object):
    @pytest.fixture(autouse=True)
    def setup(self):
        config = {
            "entity_id": ENTITY_ID,
            "key_conf": {"key_defs": KEYDEFS},
            "federation_entity": {
                'class': FederationEntity,
                "kwargs": {
                    "metadata": {
                        "organization_name": "The example cooperation",
                        "homepage_uri": "https://www.example.com",
                        "contacts": "operations@example.com"
                    },
                    "function": {
                        "class": TrustChainCollector,
                        "kwargs": {
                            "trust_anchors": ANCHOR,
                            "allowed_delta": 600
                        }
                    },
                    "client": {
                        'class': FederationEntityClient,
                        'kwargs': {
                            "services": {
                                "entity_configuration": {
                                    "class": c_EntityConfiguration,
                                    "kwargs": {}
                                },
                                "entity_statement": {
                                    "class": EntityStatement,
                                    "kwargs": {}
                                }
                            }
                        }
                    },
                    "server": {
                        'class': FederationEntityServer,
                        'kwargs': {
                            "metadata": {
                                "authority_hints": ['https://ntnu.no'],
                                "organization_name": "The example cooperation",
                                "homepage_uri": "https://www.example.com",
                                "contacts": "operations@example.com"
                            },
                            "endpoint": {
                                "entity_configuration": {
                                    "path": ".well-known/openid-federation",
                                    "class": s_EntityConfiguration,
                                    "kwargs": {}
                                },
                                "fetch": {
                                    "path": "fetch",
                                    "class": Fetch,
                                    "kwargs": {}
                                }
                            }
                        }
                    }
                }
            },
            "trust_mark_issuer": {
                'class': TrustMarkIssuer,
                'kwargs': {
                    "endpoint": {
                        "trust_mark_status": {
                            'path': 'status',
                            'class': Status,
                            'kwargs': {}
                        }
                    },
                    'trust_marks': {
                        TM_ID: {"ref": "https://refeds.org/sirtfi"}
                    }
                }
            }
        }

        self.entity = FederationCombo(config)

    def test_metadata(self):
        res = self.entity.get_metadata()
        assert set(res.keys()) == {"federation_entity", "trust_mark_issuer"}
