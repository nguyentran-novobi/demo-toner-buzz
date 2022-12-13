# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import platform

PLATFORM = 'amazon'
NAME = 'Omni Amazon'
VERSION = '0.1'
PYTHON_VERSION = platform.python_version()
USER_AGENT = f'{NAME}/{VERSION} (Language=Python/{PYTHON_VERSION})'

DATE_STAMP_FORMAT = '%Y%m%d'
BASIC_ISO_DATE_STAMP_FORMAT = '%Y%m%dT%H%M%SZ'
