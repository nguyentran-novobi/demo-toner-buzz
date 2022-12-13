# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from dataclasses import dataclass

from ..restful import connection


@dataclass
class AmazonConnection(connection.RestfulConnectionLazyHeaders):
    access_key: str
    secret_access_key: str
    region: str
    service: str
