# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import time

from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from .connection import RestfulConnection, RestfulRequest


class RateLimitStatus:
    avg_rate: int

    threshold: Optional[int]
    current: Optional[int]
    ms_to_retry: Optional[int]
    time: Optional[datetime]

    @property
    def buildup(self) -> float:
        return self.current / self.threshold

    @property
    def predicted_buildup(self) -> float:
        return max(self.buildup - self.avg_rate * self.time_passed / 10**3, 0)

    @property
    def predicted_ms_to_retry(self) -> float:
        return max(self.ms_to_retry - self.time_passed, 0)

    @property
    def time_passed(self) -> int:
        diff = datetime.utcnow() - self.time
        return diff.days * 24 * 60 * 60 * 10**3 + diff.seconds * 10**3 + diff.microseconds / 10**3

    @property
    def is_throttled(self):
        return self.current >= self.threshold


class RateLimitGetter:
    def __call__(self, headers: dict) -> RateLimitStatus:
        """
        Get the current rate limit status out of the response headers
        """


@dataclass
class RateLimitedRestfulConnection(RestfulConnection):
    rate_limit_status = RateLimitStatus()

    rate_limit_getter: RateLimitGetter

    def update_rate_limit_status(self, headers):
        self.rate_limit_status = self.rate_limit_getter(headers)


class Strategy:
    conn_field = 'conn'
    request: 'RateLimitedRestfulRequest'

    def __get__(self, instance, owner):
        assert owner == RateLimitedRestfulRequest
        return self.init_with(instance)

    def execute(self):
        """
        Check the current situation and follow the strategy
        """

    @classmethod
    def init_with(cls, instance, **kwargs):
        strategy = cls()
        strategy.request = instance
        for k, v in kwargs.items():
            setattr(strategy, k, v)
        return strategy

    @property
    def conn(self):
        return self.request.__dict__[self.conn_field]

    @property
    def rate_limit_status(self):
        return self.conn.rate_limit_status


class BeforeSendStrategy(Strategy):
    pass


class SuspensionStrategy(BeforeSendStrategy):
    """
    This strategy checks the heat from calling requests.
    To keep the temperature from reaching the threshold,
    this suspends the process by a short time to reduce the heating rate.
    """

    delay_pattern = [
        (0.95, 1000),
        (0.9, 750),
        (0.85, 500),
        (0.8, 250),
        (0.75, 100),
    ]

    def execute(self):
        """
        Check the current situation and delay the execution if needed
        """
        self.delay_with_buildup(self.rate_limit_status.predicted_buildup)

    def delay_with_buildup(self, buildup):
        delayed_time = self.get_delayed_time(buildup)
        time.sleep(delayed_time)

    def get_delayed_time(self, buildup) -> float:
        pattern = sorted(self.delay_pattern)
        percent, res = next(filter(lambda item: item > (buildup, 0), pattern), pattern[-1])
        return res / 1e3


class AfterSendStrategy(Strategy):
    pass


class PersistentStrategy(AfterSendStrategy):
    """
    If the request did not make it, this will force the process to suspend until the request can be called again.
    """
    field_name = 'persistent_max_retry'
    max_retry = 3

    def __get__(self, instance, owner):
        res = super().__get__(instance, owner)
        instance.__dict__.set_default(self.field_name, self.max_retry)
        return res

    def execute(self):
        """
        Check the current situation and retry the request up to the designated maximum time
        """
        if self.rate_limit_status.is_throttled and self.request.__dict__[self.field_name] > 0:
            self.request.__dict__[self.field_name] -= 1
            self._execute()

    def _execute(self):
        t = self.rate_limit_status.predicted_ms_to_retry / 10 ** 3
        time.sleep(t)
        self.request.send()


@dataclass
class RateLimitedRestfulRequest(RestfulRequest):
    conn: RateLimitedRestfulConnection

    before_send_strategy = SuspensionStrategy()
    after_send_strategy = PersistentStrategy()

    def send(self):
        self.before_send_strategy.execute()
        res = super().send()
        self.conn.update_rate_limit_status(res.headers)
        self.after_send_strategy.execute()
        return res
