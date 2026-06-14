from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from base64 import b64encode
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx

from cogu.skills.im_adapter import IMMessage, IMPlatform, IMResponse, PlatformAdapter


@dataclass
class DingTalkConfig:
    app_key: str = ""
    app_secret: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""
    agent_id: int = 0
    api_base: str = "https://api.dingtalk.com"
    token_ttl: int = 7200

    @classmethod
    def from_env(cls) -> "DingTalkConfig":
        import os
        return cls(
            app_key=os.getenv("DINGTALK_APP_KEY", ""),
            app_secret=os.getenv("DINGTALK_APP_SECRET", ""),
            webhook_url=os.getenv("DINGTALK_WEBHOOK", ""),
            webhook_secret=os.getenv("DINGTALK_WEBHOOK_SECRET", ""),
            agent_id=int(os.getenv("DINGTALK_AGENT_ID", "0")),
        )


@dataclass
class DingTalkMessage:
    msgtype: str
    text: dict = field(default_factory=dict)
    markdown: dict = field(default_factory=dict)
    at: dict = field(default_factory=dict)


class DingTalkAdapter(PlatformAdapter):

    def __init__(self, config: DingTalkConfig = None):
        self.config = config or DingTalkConfig.from_env()
        self._access_token: str = ""
        self._token_expires_at: float = 0
        self._http_client: Optional[httpx.AsyncClient] = None
        self._running: bool = False
        self._message_queue: asyncio.Queue[IMMessage] = asyncio.Queue()

    def platform(self) -> IMPlatform:
        return IMPlatform.DINGTALK

    async def _ensure_client(self):
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)

    async def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        await self._ensure_client()

        url = f"{self.config.api_base}/v1.0/oauth2/accessToken"
        headers = {"Content-Type": "application/json"}
        data = {
            "appKey": self.config.app_key,
            "appSecret": self.config.app_secret,
        }

        response = await self._http_client.post(url, headers=headers, json=data)
        result = response.json()

        if result.get("accessToken"):
            self._access_token = result["accessToken"]
            self._token_expires_at = now + result.get("expireIn", self.config.token_ttl)
            return self._access_token

        raise RuntimeError(f"Failed to get access token: {result}")

    def _sign_webhook(self) -> tuple[str, int]:
        timestamp = int(time.time() * 1000)
        if not self.config.webhook_secret:
            return "", timestamp

        secret_enc = self.config.webhook_secret.encode("utf-8")
        string_to_sign = f"{timestamp}\n{self.config.webhook_secret}"
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = b64encode(hmac_code).decode("utf-8")
        return sign, timestamp

    async def _send_webhook(self, message: DingTalkMessage) -> bool:
        if not self.config.webhook_url:
            return False

        await self._ensure_client()

        url = self.config.webhook_url
        if self.config.webhook_secret:
            sign, timestamp = self._sign_webhook()
            url += f"&timestamp={timestamp}&sign={sign}"

        headers = {"Content-Type": "application/json"}
        data = {
            "msgtype": message.msgtype,
        }
        if message.msgtype == "text":
            data["text"] = message.text
        elif message.msgtype == "markdown":
            data["markdown"] = message.markdown
        if message.at:
            data["at"] = message.at

        response = await self._http_client.post(url, headers=headers, json=data)
        result = response.json()
        return result.get("errcode") == 0

    async def _send_robot_message(
        self,
        userid_list: list[str],
        message: DingTalkMessage,
    ) -> tuple[bool, str]:
        token = await self._get_access_token()

        url = f"{self.config.api_base}/v1.0/robot/oToMessages/send"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": token,
        }

        data = {
            "useridList": ",".join(userid_list),
            "robotCode": self.config.app_key,
            "msgKey": message.msgtype,
            "msgParam": json.dumps(message.text or message.markdown),
        }

        response = await self._http_client.post(url, headers=headers, json=data)
        result = response.json()

        if result.get("taskId"):
            return True, result.get("taskId", "")
        return False, result.get("errorMessage", "Unknown error")

    async def _get_user_info(self, userid: str) -> Optional[dict]:
        token = await self._get_access_token()
        url = f"{self.config.api_base}/v1.0/contact/users/{userid}"
        headers = {
            "x-acs-dingtalk-access-token": token,
        }

        response = await self._http_client.get(url, headers=headers)
        result = response.json()
        if result.get("name"):
            return result
        return None

    async def send(self, response: IMResponse, target: str = "") -> bool:
        content = response.content

        message = DingTalkMessage(
            msgtype="text",
            text={"content": content},
        )

        if "\n" in content or ("**" in content and "__" in content):
            message.msgtype = "markdown"
            message.markdown = {
                "title": content[:50] + "..." if len(content) > 50 else content,
                "text": content,
            }

        if target:
            success, _ = await self._send_robot_message([target], message)
            return success
        elif self.config.webhook_url:
            return await self._send_webhook(message)
        return False

    async def send_markdown(
        self,
        title: str,
        text: str,
        at_userids: list[str] = None,
        at_mobiles: list[str] = None,
    ) -> bool:
        message = DingTalkMessage(
            msgtype="markdown",
            markdown={"title": title, "text": text},
        )
        if at_userids or at_mobiles:
            message.at = {
                "atUserIds": at_userids or [],
                "atMobiles": at_mobiles or [],
                "isAtAll": False,
            }
        return await self._send_webhook(message)

    async def send_text(
        self,
        text: str,
        at_userids: list[str] = None,
        at_mobiles: list[str] = None,
    ) -> bool:
        message = DingTalkMessage(
            msgtype="text",
            text={"content": text},
        )
        if at_userids or at_mobiles:
            message.at = {
                "atUserIds": at_userids or [],
                "atMobiles": at_mobiles or [],
                "isAtAll": False,
            }
        return await self._send_webhook(message)

    async def receive(self) -> AsyncIterator[IMMessage]:
        while self._running:
            try:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=0.1)
                yield message
            except asyncio.TimeoutError:
                continue

    def enqueue_message(self, message: IMMessage):
        self._message_queue.put_nowait(message)

    def handle_webhook_event(self, event_data: dict) -> Optional[IMMessage]:
        msg_type = event_data.get("msgtype")
        if not msg_type:
            return None

        sender_id = event_data.get("senderStaffId", "")
        content = ""
        if msg_type == "text":
            content = event_data.get("text", {}).get("content", "")
        elif msg_type == "markdown":
            content = event_data.get("markdown", {}).get("text", "")

        if not content:
            return None

        return IMMessage(
            content=content,
            sender=sender_id,
            platform=IMPlatform.DINGTALK,
            message_id=str(uuid.uuid4())[:12],
            metadata=event_data,
        )

    async def close(self):
        self._running = False
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def start_polling(self, interval: float = 1.0):
        self._running = True
        while self._running:
            await asyncio.sleep(interval)


@dataclass
class FeishuConfig:
    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    encrypt_key: str = ""
    api_base: str = "https://open.feishu.cn"
    token_ttl: int = 7200

    @classmethod
    def from_env(cls) -> "FeishuConfig":
        import os
        return cls(
            app_id=os.getenv("FEISHU_APP_ID", ""),
            app_secret=os.getenv("FEISHU_APP_SECRET", ""),
            verification_token=os.getenv("FEISHU_VERIFICATION_TOKEN", ""),
            encrypt_key=os.getenv("FEISHU_ENCRYPT_KEY", ""),
        )


class FeishuAdapter(PlatformAdapter):

    def __init__(self, config: FeishuConfig = None):
        self.config = config or FeishuConfig.from_env()
        self._tenant_access_token: str = ""
        self._token_expires_at: float = 0
        self._http_client: Optional[httpx.AsyncClient] = None
        self._running: bool = False
        self._message_queue: asyncio.Queue[IMMessage] = asyncio.Queue()

    def platform(self) -> IMPlatform:
        return IMPlatform.FEISHU

    async def _ensure_client(self):
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)

    async def _get_tenant_access_token(self) -> str:
        now = time.time()
        if self._tenant_access_token and now < self._token_expires_at - 60:
            return self._tenant_access_token

        await self._ensure_client()

        url = f"{self.config.api_base}/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret,
        }

        response = await self._http_client.post(url, headers=headers, json=data)
        result = response.json()

        if result.get("code") == 0:
            self._tenant_access_token = result["tenant_access_token"]
            self._token_expires_at = now + result.get("expire", self.config.token_ttl)
            return self._tenant_access_token

        raise RuntimeError(f"Failed to get tenant access token: {result}")

    async def _send_text_message(self, receive_id: str, content: str) -> tuple[bool, str]:
        token = await self._get_tenant_access_token()

        url = f"{self.config.api_base}/open-apis/im/v1/messages"
        params = {"receive_id_type": "user_id"}
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        }

        msg_content = json.dumps({"text": content})
        data = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": msg_content,
        }

        response = await self._http_client.post(url, params=params, headers=headers, json=data)
        result = response.json()

        if result.get("code") == 0:
            return True, result.get("data", {}).get("message_id", "")
        return False, result.get("msg", "Unknown error")

    async def _send_rich_message(self, receive_id: str, content: dict) -> tuple[bool, str]:
        token = await self._get_tenant_access_token()

        url = f"{self.config.api_base}/open-apis/im/v1/messages"
        params = {"receive_id_type": "user_id"}
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        }

        data = {
            "receive_id": receive_id,
            "msg_type": "post",
            "content": json.dumps(content),
        }

        response = await self._http_client.post(url, params=params, headers=headers, json=data)
        result = response.json()

        if result.get("code") == 0:
            return True, result.get("data", {}).get("message_id", "")
        return False, result.get("msg", "Unknown error")

    async def send(self, response: IMResponse, target: str = "") -> bool:
        if target:
            success, _ = await self._send_text_message(target, response.content)
            return success
        return False

    async def send_post_message(
        self,
        receive_id: str,
        title: str,
        elements: list[dict],
    ) -> bool:
        content = {
            "zh_cn": {
                "title": title,
                "content": elements,
            }
        }
        success, _ = await self._send_rich_message(receive_id, content)
        return success

    async def receive(self) -> AsyncIterator[IMMessage]:
        while self._running:
            try:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=0.1)
                yield message
            except asyncio.TimeoutError:
                continue

    def enqueue_message(self, message: IMMessage):
        self._message_queue.put_nowait(message)

    def verify_request(self, headers: dict, body: bytes) -> bool:
        if not self.config.verification_token:
            return True
        token = headers.get("X-Lark-Request-Token", "")
        return token == self.config.verification_token

    def handle_webhook_event(self, event_data: dict) -> Optional[IMMessage]:
        header = event_data.get("header", {})
        event_type = header.get("event_type", "")

        if event_type != "im.message.receive_v1":
            return None

        event = event_data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})

        msg_type = message.get("message_type", "")
        if msg_type != "text":
            return None

        content = json.loads(message.get("content", "{}"))
        text = content.get("text", "")

        return IMMessage(
            content=text,
            sender=sender.get("sender_id", {}).get("user_id", ""),
            message_id=message.get("message_id", ""),
            platform=IMPlatform.FEISHU,
            metadata=event_data,
        )

    async def close(self):
        self._running = False
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
