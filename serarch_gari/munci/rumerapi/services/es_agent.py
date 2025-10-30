from __future__ import annotations
from typing import Any, Dict, Optional, Union, List
from elasticsearch import Elasticsearch
from munci.rumerapi.core.config import settings
import logging

logger = logging.getLogger(__name__)

class ESAgent:
    def __init__(
        self,
        hosts: Optional[Union[str, List[str]]] = None,
        index: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_certs: Optional[bool] = None,
        ca_cert: Optional[str] = None,
    ):
        self.index = index or settings.es_index
        hosts = hosts or settings.es_hosts
        if isinstance(hosts, str) and "," in hosts:
            hosts = [h.strip() for h in hosts.split(",") if h.strip()]
        basic_auth = None
        u = username or settings.es_username
        p = password or settings.es_password
        if u and p:
            basic_auth = (u, p)
        verify = settings.es_verify_certs if verify_certs is None else verify_certs
        kwargs: Dict[str, Any] = {"request_timeout": 60, "verify_certs": verify}
        if basic_auth:
            kwargs["basic_auth"] = basic_auth
        if verify and (ca := (ca_cert or settings.es_ca_cert)):
            kwargs["ca_certs"] = ca
        self.es = Elasticsearch(hosts, **kwargs)

    def search(self, dsl: Dict[str, Any], index: Optional[str] = None) -> Dict[str, Any]:
        ix = index or self.index
        return self.es.search(index=ix, body=dsl)
