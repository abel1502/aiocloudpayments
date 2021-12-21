import logging
from typing import Optional

from aiohttp import web
from aiohttp.abc import Application

from .callback import Result
from .router import Router
from ..types.notifications import CancelNotification, CheckNotification, ConfirmNotification, \
    FailNotification, PayNotification, RecurrentNotification, RefundNotification
from ..utils import json


logger = logging.getLogger("aiocloudpayments.dispatcher")

NOTIFICATION_TYPES = {
    "pay": PayNotification, "cancel": CancelNotification, "check": CheckNotification,
    "confirm": ConfirmNotification, "fail": FailNotification,
    "recurrent": RecurrentNotification, "refund": RefundNotification
}


class AiohttpDispatcher(Router):
    def __init__(self, index: int = None):
        self._web_paths = {}
        self.ip_whitelist = None

        super().__init__(index)

    async def process_request(self, request: web.Request) -> web.Response:
        if self.ip_whitelist and request.remote not in self.ip_whitelist and "0.0.0.0" not in self.ip_whitelist:
            logger.warning(f"skip request from ip {request.remote} because it is not in ip_whitelist")
            return web.json_response(status=401)
        name = self._web_paths[request.url.name]
        notification_type = NOTIFICATION_TYPES.get(name)
        if notification_type is None:
            logger.error(f"notification type {name} not supported")
            return web.json_response(status=500)
        notification = notification_type(**(await request.json(loads=json.loads)))
        result = await self.process_notification(notification)
        if result == Result.INTERNAL_ERROR:
            return web.json_response(status=500)
        if result:
            return web.json_response({"result": result.value})

    def register_app(
            self,
            app: Application,
            path: str,
            pay_path: str = None,
            cancel_path: str = None,
            check_path: str = None,
            confirm_path: str = None,
            fail_path: str = None,
            recurrent_path: str = None,
            refund_path: str = None):
        """
        Register route
        All if path doesn't end with "/", sub-paths should start with it and vice-versa
        Only not-null paths are registered :)

        :param app: instance of aiohttp Application
        :param path: route main path
        :param pay_path: sub-path for pay notifications
        :param cancel_path:
        :param check_path:
        :param confirm_path:
        :param fail_path:
        :param recurrent_path:
        :param refund_path:
        :param kwargs:
        """
        paths = {
            "pay": pay_path, "cancel": cancel_path, "check": check_path,
            "confirm": confirm_path, "fail": fail_path,
            "recurrent": recurrent_path, "refund": refund_path
        }
        paths = {k: v for k, v in paths.items() if v is not None}

        for name, path_ in paths.items():
            if path_ is None:
                continue
            self._web_paths[path_.replace("/", "")] = name
            app.router.add_route(
                "POST", path + path_, self.process_request
            )

    def run_app(
            self,
            path: str,
            pay_path: str = None,
            cancel_path: str = None,
            check_path: str = None,
            confirm_path: str = None,
            fail_path: str = None,
            recurrent_path: str = None,
            refund_path: str = None,
            allow_ips: Optional[set[str]] = frozenset({"127.0.0.1", "130.193.70.192",
                                                       "185.98.85.109", "91.142.84.0/27",
                                                       "87.251.91.160/27", "185.98.81.0/28"}),
            **kwargs
    ):
        """
        Create aiohttp app and run it
        All if path doesn't end with "/", sub-paths should start with it and vice-versa
        Only not-null paths are registered :)

        :param path: route main path
        :param pay_path: sub-path for pay notifications
        :param cancel_path:
        :param check_path:
        :param confirm_path:
        :param fail_path:
        :param recurrent_path:
        :param refund_path:
        :param allow_ips: only allow requests from this ips
        :param kwargs: aiohttp run_app parameters
        """
        self.ip_whitelist = allow_ips
        app = web.Application()
        self.register_app(
            app, path, pay_path, cancel_path, check_path, confirm_path,
            fail_path, recurrent_path, refund_path
        )
        web.run_app(app, **kwargs)
