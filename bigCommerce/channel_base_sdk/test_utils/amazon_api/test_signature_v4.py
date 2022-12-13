# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import datetime
import pytest
import json

from operator import itemgetter

from utils.amazon_api import signature_v4

cases = [(
    dict(
        uri='/',
        headers={'host': 'ec2.amazonaws.com', 'x-amz-date': '20201225T162345Z'},
        params={'Action': 'DescribeRegions', 'Version': '2013-10-15'},
        data='',
        method='GET',
        access_key='abc-def-ghi-jkl',
        secret_access_key='mno-pqr-stu-vw-xyz',
        request_time=datetime.datetime(2020, 12, 25, 16, 23, 45),
        region='us-east-1',
        service='ec2',
    ),
    'GET\n'
    '/\n'
    'Action=DescribeRegions&Version=2013-10-15\n'
    'host:ec2.amazonaws.com\n'
    'x-amz-date:20201225T162345Z\n'
    '\n'
    'host;x-amz-date\n'
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'AWS4-HMAC-SHA256\n'
    '20201225T162345Z\n'
    '20201225/us-east-1/ec2/aws4_request\n'
    '93fe1bac4aebfd1bbd5e8226ef9b780d72ede5d595bce04f099166f13d1ea6d3',
    '9ab946511ecd41f0cee1c864f5cec0e42312753481e4b50213a3703e4037c822',
    {
        'Authorization': 'AWS4-HMAC-SHA256'
                         ' Credential=abc-def-ghi-jkl/20201225/us-east-1/ec2/aws4_request,'
                         ' SignedHeaders=host;x-amz-date,'
                         ' Signature=9ab946511ecd41f0cee1c864f5cec0e42312753481e4b50213a3703e4037c822'
    }
), (
    dict(
        uri='/orders/v0/orders',
        headers={
            'host': 'sellingpartnerapi-na.amazon.com',
            'x-amz-date': '20190712T030154Z',
            'user-agent': 'My Selling Tool/2.0 (Language=Java/1.8.0.221;Platform=Windows/10)',
            'x-amz-access-token': 'Atza|IQEBLj'
        },
        params={},
        data='',
        method='GET',
        access_key='access-key-of-developer',
        secret_access_key='secret-key-of-developer',
        request_time=datetime.datetime(2019, 7, 12, 3, 1, 54),
        region='us-east-1',
        service='execute-api',
    ),
    'GET\n'
    '/orders/v0/orders\n'
    '\n'
    'host:sellingpartnerapi-na.amazon.com\n'
    'user-agent:My Selling Tool/2.0 (Language=Java/1.8.0.221;Platform=Windows/10)\n'
    'x-amz-access-token:Atza|IQEBLj\n'
    'x-amz-date:20190712T030154Z\n'
    '\n'
    'host;user-agent;x-amz-access-token;x-amz-date\n'
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'AWS4-HMAC-SHA256\n'
    '20190712T030154Z\n'
    '20190712/us-east-1/execute-api/aws4_request\n'
    '39c293bd70f3db5792fd54d50a83be1b370bfe6b6d5e3526a31ee44b80457a89',
    'bbd25e22e9f406757ee7ac0f47de323dad7f8261a39c874ba75af815156fb047',
    {
        'Authorization': 'AWS4-HMAC-SHA256'
                         ' Credential=access-key-of-developer/20190712/us-east-1/execute-api/aws4_request,'
                         ' SignedHeaders=host;user-agent;x-amz-access-token;x-amz-date,'
                         ' Signature=bbd25e22e9f406757ee7ac0f47de323dad7f8261a39c874ba75af815156fb047'
    }
), (
    dict(
        uri='/orders/v0/orders/123456 789',
        headers={
            'host': 'sellingpartnerapi-na.amazon.com',
            'x-amz-date': '20140301T230059Z',
            'user-agent': 'My Selling Tool/2.0 (Language=Java/1.8.0.221;Platform=Windows/10)',
            'x-amz-access-token': 'Atza|IQEBLj'
        },
        params={},
        data=json.dumps(dict(id=123456789, state='confirmed', delvered=True)),
        method='POST',
        access_key='access-key-of-developer',
        secret_access_key='secret-key-of-developer',
        request_time=datetime.datetime(2014, 3, 1, 23, 0, 59, 487856),
        region='eu-west-1',
        service='execute-api',
    ),
    'POST\n'
    '/orders/v0/orders/123456%20789\n'
    '\n'
    'host:sellingpartnerapi-na.amazon.com\n'
    'user-agent:My Selling Tool/2.0 (Language=Java/1.8.0.221;Platform=Windows/10)\n'
    'x-amz-access-token:Atza|IQEBLj\n'
    'x-amz-date:20140301T230059Z\n'
    '\n'
    'host;user-agent;x-amz-access-token;x-amz-date\n'
    '281d4d9ea6b23ca99a10b7cc0e3ab658617a6fc4d740c89cfaaf51989188747f',
    'AWS4-HMAC-SHA256\n'
    '20140301T230059Z\n'
    '20140301/eu-west-1/execute-api/aws4_request\n'
    '647faf717b2644d755afec08cf12082a063f8e2201ae16d92152b004cc3d7252',
    '05dae5630ee4029a96a719af0bf49a1be49d22791b65d600e64feae36c723866',
    {
        'Authorization': 'AWS4-HMAC-SHA256'
                         ' Credential=access-key-of-developer/20140301/eu-west-1/execute-api/aws4_request,'
                         ' SignedHeaders=host;user-agent;x-amz-access-token;x-amz-date,'
                         ' Signature=05dae5630ee4029a96a719af0bf49a1be49d22791b65d600e64feae36c723866'
    }
)]


@pytest.mark.parametrize('builder_kwargs,canon_req', map(itemgetter(0, 1), cases))
def test_task_1(builder_kwargs, canon_req):
    builder = signature_v4.AuthorizationBuilder(**builder_kwargs)
    canonical_request = builder.create_canonical_request()
    assert canonical_request == canon_req


@pytest.mark.parametrize('builder_kwargs,str_sign', map(itemgetter(0, 2), cases))
def test_task_2(builder_kwargs, str_sign):
    builder = signature_v4.AuthorizationBuilder(**builder_kwargs)
    canonical_request = builder.create_canonical_request()
    string_to_sign, credential_scope = builder.create_string_to_sign(canonical_request)
    assert string_to_sign == str_sign


@pytest.mark.parametrize('builder_kwargs,sign', map(itemgetter(0, 3), cases))
def test_task_3(builder_kwargs, sign):
    builder = signature_v4.AuthorizationBuilder(**builder_kwargs)
    canonical_request = builder.create_canonical_request()
    string_to_sign, credential_scope = builder.create_string_to_sign(canonical_request)
    signature = builder.calculate_signature(string_to_sign)
    assert signature == sign


@pytest.mark.parametrize('builder_kwargs,headers', map(itemgetter(0, 4), cases))
def test_task_4(builder_kwargs, headers):
    result = signature_v4.get_authorization_headers(**builder_kwargs)
    assert result == headers
