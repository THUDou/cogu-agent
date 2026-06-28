"""OpenAPI 插件系统 — 基于OpenAPI 3.0规范的插件定义与执行

参考: Coze Studio backend/domain/plugin/
      PluginInfo: Manifest + OpenapiDoc + ServerURL
      PluginService: Draft Plugin, Online Plugin, Draft Tool, Agent Tool, Execute Tool, OAuth
      执行: buildToolExecutor() -> acquireAccessTokenIfNeed() -> HTTP Request -> Response

COGU 实现: 纯Python本地版，支持OpenAPI 3.0解析、插件市场、OAuth模拟、工具执行
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class AuthType(Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    BEARER = "bearer"


@dataclass
class AuthConfig:
    auth_type: AuthType = AuthType.NONE
    api_key_header: str = "X-API-Key"
    api_key_value: str = ""
    oauth_token_url: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    bearer_token: str = ""
    basic_username: str = ""
    basic_password: str = ""

    def to_dict(self) -> dict:
        d = {"auth_type": self.auth_type.value}
        if self.auth_type == AuthType.API_KEY:
            d["api_key_header"] = self.api_key_header
        elif self.auth_type == AuthType.OAUTH2:
            d["oauth_token_url"] = self.oauth_token_url
            d["oauth_client_id"] = self.oauth_client_id
        elif self.auth_type == AuthType.BEARER:
            pass
        elif self.auth_type == AuthType.BASIC:
            d["basic_username"] = self.basic_username
        return d


@dataclass
class ToolParameter:
    name: str = ""
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: list[Any] = field(default_factory=list)
    in_location: str = "query"

    def to_dict(self) -> dict:
        d = {"name": self.name, "type": self.type, "description": self.description,
             "required": self.required, "in": self.in_location}
        if self.default is not None:
            d["default"] = self.default
        if self.enum:
            d["enum"] = self.enum
        return d


@dataclass
class ToolInfo:
    tool_id: str = ""
    name: str = ""
    description: str = ""
    method: str = "GET"
    path: str = ""
    parameters: list[ToolParameter] = field(default_factory=list)
    request_body_type: str = ""
    request_body_schema: dict[str, Any] = field(default_factory=dict)
    response_schema: dict[str, Any] = field(default_factory=dict)
    auth_config: AuthConfig = field(default_factory=AuthConfig)

    def to_dict(self) -> dict:
        return {
            "tool_id": self.tool_id, "name": self.name,
            "description": self.description, "method": self.method,
            "path": self.path,
            "parameters": [p.to_dict() for p in self.parameters],
            "request_body_type": self.request_body_type,
            "response_schema": self.response_schema,
            "auth_config": self.auth_config.to_dict(),
        }


@dataclass
class PluginInfo:
    plugin_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    status: PluginStatus = PluginStatus.DRAFT
    server_url: str = ""
    auth_config: AuthConfig = field(default_factory=AuthConfig)
    tools: list[ToolInfo] = field(default_factory=list)
    openapi_doc: dict[str, Any] = field(default_factory=dict)
    icon_url: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id, "name": self.name,
            "description": self.description, "version": self.version,
            "status": self.status.value, "server_url": self.server_url,
            "tools": [t.to_dict() for t in self.tools],
            "icon_url": self.icon_url, "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }


class OpenAPIParser:
    @staticmethod
    def parse(openapi_doc: dict) -> tuple[str, list[ToolInfo], AuthConfig]:
        server_url = ""
        servers = openapi_doc.get("servers", [])
        if servers:
            server_url = servers[0].get("url", "")

        auth_config = AuthConfig()
        security_schemes = openapi_doc.get("components", {}).get("securitySchemes", {})
        global_security = openapi_doc.get("security", [])

        if global_security and security_schemes:
            for sec_name in global_security[0]:
                scheme = security_schemes.get(sec_name, {})
                scheme_type = scheme.get("type", "")
                if scheme_type == "apiKey":
                    auth_config = AuthType.API_KEY
                    auth_config = AuthConfig(
                        auth_type=AuthType.API_KEY,
                        api_key_header=scheme.get("name", "X-API-Key"),
                    )
                elif scheme_type == "http":
                    scheme_scheme = scheme.get("scheme", "")
                    if scheme_scheme == "bearer":
                        auth_config = AuthConfig(auth_type=AuthType.BEARER)
                    elif scheme_scheme == "basic":
                        auth_config = AuthConfig(auth_type=AuthType.BASIC)
                elif scheme_type == "oauth2":
                    flows = scheme.get("flows", {})
                    client_creds = flows.get("clientCredentials", {})
                    auth_config = AuthConfig(
                        auth_type=AuthType.OAUTH2,
                        oauth_token_url=client_creds.get("tokenUrl", ""),
                    )

        tools: list[ToolInfo] = []
        paths = openapi_doc.get("paths", {})
        for path, path_item in paths.items():
            for method in ("get", "post", "put", "delete", "patch"):
                if method not in path_item:
                    continue
                operation = path_item[method]
                tool = ToolInfo(
                    tool_id=operation.get("operationId", uuid.uuid4().hex[:8]),
                    name=operation.get("operationId", f"{method}_{path}"),
                    description=operation.get("summary", operation.get("description", "")),
                    method=method.upper(),
                    path=path,
                )

                for param in operation.get("parameters", []):
                    tool.parameters.append(ToolParameter(
                        name=param.get("name", ""),
                        type=param.get("schema", {}).get("type", "string"),
                        description=param.get("description", ""),
                        required=param.get("required", False),
                        default=param.get("schema", {}).get("default"),
                        enum=param.get("schema", {}).get("enum", []),
                        in_location=param.get("in", "query"),
                    ))

                request_body = operation.get("requestBody", {})
                if request_body:
                    content = request_body.get("content", {})
                    for content_type, content_schema in content.items():
                        tool.request_body_type = content_type
                        tool.request_body_schema = content_schema.get("schema", {})
                        break

                responses = operation.get("responses", {})
                if "200" in responses:
                    resp_content = responses["200"].get("content", {})
                    for ct, cs in resp_content.items():
                        tool.response_schema = cs.get("schema", {})
                        break

                tools.append(tool)

        return server_url, tools, auth_config

    @staticmethod
    def parse_json(json_str: str) -> tuple[str, list[ToolInfo], AuthConfig]:
        return OpenAPIParser.parse(json.loads(json_str))

    @staticmethod
    def parse_file(filepath: str | Path) -> tuple[str, list[ToolInfo], AuthConfig]:
        with open(filepath, "r", encoding="utf-8") as f:
            return OpenAPIParser.parse(json.load(f))


class ToolExecutor:
    def __init__(self, tool: ToolInfo, server_url: str = "",
                 auth_config: AuthConfig = None, http_client: Any = None):
        self.tool = tool
        self.server_url = server_url
        self.auth_config = auth_config or AuthConfig()
        self._http_client = http_client
        self._oauth_token: str = ""
        self._token_expires: float = 0

    def _build_url(self, args: dict) -> str:
        url = self.tool.path
        for param in self.tool.parameters:
            if param.in_location == "path" and param.name in args:
                url = url.replace(f"{{{param.name}}}", str(args[param.name]))
        if self.server_url:
            base = self.server_url.rstrip("/")
            url = base + url
        return url

    def _build_query_params(self, args: dict) -> dict:
        params = {}
        for param in self.tool.parameters:
            if param.in_location == "query" and param.name in args:
                params[param.name] = args[param.name]
        return params

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_config.auth_type == AuthType.API_KEY:
            headers[self.auth_config.api_key_header] = self.auth_config.api_key_value
        elif self.auth_config.auth_type == AuthType.BEARER:
            headers["Authorization"] = f"Bearer {self.auth_config.bearer_token}"
        elif self.auth_config.auth_type == AuthType.BASIC:
            import base64
            cred = base64.b64encode(
                f"{self.auth_config.basic_username}:{self.auth_config.basic_password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {cred}"
        elif self.auth_config.auth_type == AuthType.OAUTH2:
            if self._oauth_token and time.time() < self._token_expires:
                headers["Authorization"] = f"Bearer {self._oauth_token}"
        return headers

    def _acquire_oauth_token(self):
        if self.auth_config.auth_type != AuthType.OAUTH2:
            return
        if self._oauth_token and time.time() < self._token_expires:
            return
        self._oauth_token = f"mock_oauth_token_{uuid.uuid4().hex[:8]}"
        self._token_expires = time.time() + 3600

    async def execute(self, args: dict = None) -> dict:
        args = args or {}
        self._acquire_oauth_token()

        url = self._build_url(args)
        query_params = self._build_query_params(args)
        headers = self._build_headers()

        body = None
        if self.tool.method in ("POST", "PUT", "PATCH") and self.tool.request_body_type:
            body_args = {}
            for param in self.tool.parameters:
                if param.in_location == "body" and param.name in args:
                    body_args[param.name] = args[param.name]
            if not body_args and "body" in args:
                body_args = args["body"]
            body = body_args

        if self._http_client:
            try:
                response = await self._http_client.request(
                    method=self.tool.method,
                    url=url,
                    params=query_params,
                    headers=headers,
                    json=body,
                )
                return {
                    "status_code": response.status_code,
                    "data": response.json() if hasattr(response, 'json') else str(response),
                    "tool_id": self.tool.tool_id,
                    "tool_name": self.tool.name,
                }
            except Exception as e:
                return {"status_code": 500, "error": str(e),
                        "tool_id": self.tool.tool_id, "tool_name": self.tool.name}

        return {
            "status_code": 200,
            "data": {"result": f"Mock response for {self.tool.name}"},
            "tool_id": self.tool.tool_id,
            "tool_name": self.tool.name,
            "mock": True,
            "url": url,
            "method": self.tool.method,
            "query_params": query_params,
            "body": body,
        }


class PluginManager:
    def __init__(self, http_client: Any = None):
        self._plugins: dict[str, PluginInfo] = {}
        self._executors: dict[str, ToolExecutor] = {}
        self._http_client = http_client

    def register_from_openapi(self, name: str, openapi_doc: dict | str,
                              auth_config: AuthConfig = None) -> PluginInfo:
        if isinstance(openapi_doc, str):
            openapi_doc = json.loads(openapi_doc)

        server_url, tools, parsed_auth = OpenAPIParser.parse(openapi_doc)
        plugin = PluginInfo(
            plugin_id=uuid.uuid4().hex[:12],
            name=name,
            server_url=server_url,
            auth_config=auth_config or parsed_auth,
            tools=tools,
            openapi_doc=openapi_doc,
            status=PluginStatus.PUBLISHED,
        )
        self._plugins[plugin.plugin_id] = plugin

        for tool in tools:
            executor = ToolExecutor(
                tool=tool, server_url=server_url,
                auth_config=plugin.auth_config, http_client=self._http_client,
            )
            self._executors[f"{plugin.plugin_id}:{tool.tool_id}"] = executor

        return plugin

    def register_from_file(self, name: str, filepath: str | Path,
                           auth_config: AuthConfig = None) -> PluginInfo:
        server_url, tools, parsed_auth = OpenAPIParser.parse_file(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            doc = json.load(f)
        return self.register_from_openapi(name, doc, auth_config or parsed_auth)

    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        return self._plugins.get(plugin_id)

    def list_plugins(self, category: str = "") -> list[PluginInfo]:
        plugins = list(self._plugins.values())
        if category:
            plugins = [p for p in plugins if p.category == category]
        return plugins

    def get_tool_executor(self, plugin_id: str, tool_id: str) -> Optional[ToolExecutor]:
        return self._executors.get(f"{plugin_id}:{tool_id}")

    async def execute_tool(self, plugin_id: str, tool_id: str, args: dict = None) -> dict:
        executor = self.get_tool_executor(plugin_id, tool_id)
        if not executor:
            return {"error": f"Tool not found: {plugin_id}/{tool_id}"}
        return await executor.execute(args)

    def search_tools(self, query: str) -> list[tuple[PluginInfo, ToolInfo]]:
        query_lower = query.lower()
        results = []
        for plugin in self._plugins.values():
            for tool in plugin.tools:
                if (query_lower in tool.name.lower() or
                    query_lower in tool.description.lower() or
                    query_lower in plugin.name.lower()):
                    results.append((plugin, tool))
        return results

    def get_marketplace_summary(self) -> list[dict]:
        return [
            {
                "plugin_id": p.plugin_id, "name": p.name,
                "description": p.description, "version": p.version,
                "category": p.category, "tags": p.tags,
                "tool_count": len(p.tools), "icon_url": p.icon_url,
            }
            for p in self._plugins.values()
        ]