"""运行时API发现 — 参考gws-cli

运行时发现API并构建命令树:
  - discover: 发现API端点
  - build_skill_from_api: 从API描述构建skill
  - parse_openapi: 解析OpenAPI规范
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from cogu.tools.base import ToolSpec


@dataclass
class APIParameter:
    """API参数"""
    name: str = ""
    location: str = "query"
    type: str = "string"
    required: bool = False
    description: str = ""
    default: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "location": self.location,
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "default": self.default,
        }


@dataclass
class APIDescription:
    """API端点描述"""
    name: str = ""
    method: str = "GET"
    path: str = ""
    description: str = ""
    parameters: list[APIParameter] = field(default_factory=list)
    request_body: dict[str, Any] = field(default_factory=dict)
    response_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    base_url: str = ""
    auth_type: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "method": self.method,
            "path": self.path,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters],
            "request_body": self.request_body,
            "response_schema": self.response_schema,
            "tags": self.tags,
            "base_url": self.base_url,
            "auth_type": self.auth_type,
        }


@dataclass
class DiscoveryResult:
    """发现结果"""
    base_url: str = ""
    total_endpoints: int = 0
    apis: list[APIDescription] = field(default_factory=list)
    skills_generated: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "total_endpoints": self.total_endpoints,
            "apis": [a.to_dict() for a in self.apis],
            "skills_generated": self.skills_generated,
            "errors": self.errors,
            "elapsed_seconds": self.elapsed_seconds,
        }


class APIDiscovery:
    """运行时发现API并构建命令树

    参考gws-cli的动态发现:
      - 从OpenAPI/Swagger规范解析API端点
      - 自动构建skill定义
      - 支持增量发现和缓存
    """

    def __init__(self, llm_client: Any = None, cache_dir: str = ""):
        self.llm = llm_client
        self._cache_dir = cache_dir
        self._discovered_apis: dict[str, list[APIDescription]] = {}
        self._generated_skills: list[dict] = []

    async def discover(self, base_url: str, api_key: str = "") -> list[APIDescription]:
        """发现API端点

        Args:
            base_url: API基础URL
            api_key: API密钥

        Returns:
            发现的API端点列表
        """
        apis: list[APIDescription] = []

        openapi_url = self._guess_openapi_url(base_url)
        spec = await self._fetch_openapi_spec(openapi_url, api_key)
        if spec:
            apis = self._parse_openapi(spec)
            for api in apis:
                api.base_url = base_url
                api.auth_type = "bearer" if api_key else ""
        else:
            apis = await self._discover_by_crawling(base_url, api_key)

        self._discovered_apis[base_url] = apis
        return apis

    async def build_skill_from_api(self, api_desc: APIDescription) -> dict:
        """从API描述构建skill

        Args:
            api_desc: API端点描述

        Returns:
            skill定义字典
        """
        param_docs = []
        for p in api_desc.parameters:
            req = "必填" if p.required else "可选"
            param_docs.append(f"- {p.name}({p.type}, {p.location}, {req}): {p.description}")

        steps = [
            f"构造{api_desc.method}请求到 {api_desc.path}",
        ]
        if api_desc.parameters:
            steps.append("设置请求参数")
        if api_desc.request_body:
            steps.append("构造请求体")
        steps.append("发送请求并解析响应")

        skill = {
            "name": self._api_to_skill_name(api_desc),
            "version": "1.0.0",
            "description": api_desc.description or f"调用 {api_desc.method} {api_desc.path}",
            "category": "custom",
            "tags": ["api-discovery"] + api_desc.tags,
            "recipes": [{
                "name": f"调用 {api_desc.method} {api_desc.path}",
                "description": api_desc.description,
                "trigger": api_desc.path,
                "steps": steps,
                "example_input": json.dumps({
                    "method": api_desc.method,
                    "path": api_desc.path,
                    "params": {p.name: p.default or f"<{p.type}>" for p in api_desc.parameters if p.required},
                }, ensure_ascii=False),
            }],
            "required_tools": ["http_client"],
            "risk_level": "medium" if api_desc.method in ("POST", "PUT", "DELETE", "PATCH") else "low",
            "side_effects": [] if api_desc.method == "GET" else [f"执行{api_desc.method}操作"],
            "disclosure_level": "detail",
            "api_spec": api_desc.to_dict(),
        }

        self._generated_skills.append(skill)
        return skill

    def _parse_openapi(self, spec: dict) -> list[APIDescription]:
        """解析OpenAPI规范

        Args:
            spec: OpenAPI/Swagger规范字典

        Returns:
            API端点列表
        """
        apis: list[APIDescription] = []
        paths = spec.get("paths", {})

        for path, methods in paths.items():
            for method, details in methods.items():
                if method.lower() not in ("get", "post", "put", "delete", "patch"):
                    continue

                parameters = []
                for p in details.get("parameters", []):
                    param = APIParameter(
                        name=p.get("name", ""),
                        location=p.get("in", "query"),
                        type=p.get("schema", {}).get("type", "string"),
                        required=p.get("required", False),
                        description=p.get("description", ""),
                    )
                    parameters.append(param)

                request_body = {}
                rb = details.get("requestBody")
                if rb:
                    content = rb.get("content", {})
                    for ct, schema_info in content.items():
                        request_body = {
                            "content_type": ct,
                            "schema": schema_info.get("schema", {}),
                        }
                        break

                response_schema = {}
                responses = details.get("responses", {})
                for status_code, resp in responses.items():
                    if status_code.startswith("2"):
                        content = resp.get("content", {})
                        for ct, schema_info in content.items():
                            response_schema = schema_info.get("schema", {})
                            break
                        break

                api = APIDescription(
                    name=details.get("operationId", f"{method}_{path}"),
                    method=method.upper(),
                    path=path,
                    description=details.get("summary", "") or details.get("description", ""),
                    parameters=parameters,
                    request_body=request_body,
                    response_schema=response_schema,
                    tags=details.get("tags", []),
                )
                apis.append(api)

        return apis

    def _guess_openapi_url(self, base_url: str) -> str:
        """猜测OpenAPI文档URL"""
        base = base_url.rstrip("/")
        candidates = [
            f"{base}/openapi.json",
            f"{base}/swagger.json",
            f"{base}/api-docs",
            f"{base}/v3/api-docs",
            f"{base}/api/openapi.json",
            f"{base}/docs/openapi.json",
        ]
        return candidates[0]

    async def _fetch_openapi_spec(self, url: str, api_key: str = "") -> Optional[dict]:
        """获取OpenAPI规范"""
        import urllib.request
        import urllib.error

        candidates = [url]
        base = url.rsplit("/", 1)[0] if "/" in url else url
        candidates.extend([
            f"{base}/swagger.json",
            f"{base}/api-docs",
            f"{base}/v3/api-docs",
        ])

        for candidate_url in candidates:
            try:
                headers = {"User-Agent": "cogu-agent", "Accept": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                req = urllib.request.Request(candidate_url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read().decode("utf-8")
                    return json.loads(data)
            except (urllib.error.URLError, json.JSONDecodeError, OSError):
                continue

        return None

    async def _discover_by_crawling(self, base_url: str, api_key: str = "") -> list[APIDescription]:
        """通过爬取发现API端点"""
        apis: list[APIDescription] = []

        if self.llm:
            try:
                prompt = (
                    f"分析 {base_url} 可能提供的API端点，"
                    "列出常见的REST API路径和方法，返回JSON数组格式:\n"
                    '[{"method":"GET","path":"/api/...","description":"...","tags":["..."]}]'
                )
                if hasattr(self.llm, 'complete'):
                    import asyncio
                    if asyncio.iscoroutinefunction(self.llm.complete):
                        response = await self.llm.complete(prompt)
                    else:
                        response = self.llm.complete(prompt)
                else:
                    response = str(self.llm(prompt))

                try:
                    items = json.loads(response)
                    if isinstance(items, list):
                        for item in items:
                            apis.append(APIDescription(
                                name=item.get("path", "").replace("/", "_").strip("_"),
                                method=item.get("method", "GET").upper(),
                                path=item.get("path", ""),
                                description=item.get("description", ""),
                                tags=item.get("tags", []),
                            ))
                except json.JSONDecodeError:
                    pass
            except Exception:
                pass

        return apis

    @staticmethod
    def _api_to_skill_name(api: APIDescription) -> str:
        """将API路径转为skill名称"""
        name = api.name or f"{api.method}_{api.path}"
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        name = re.sub(r'_+', '_', name).strip('_').lower()
        return f"api_{name}" if not name.startswith("api") else name

    def get_discovered_apis(self, base_url: str = "") -> list[APIDescription]:
        """获取已发现的API"""
        if base_url:
            return self._discovered_apis.get(base_url, [])
        all_apis: list[APIDescription] = []
        for apis in self._discovered_apis.values():
            all_apis.extend(apis)
        return all_apis

    def get_generated_skills(self) -> list[dict]:
        """获取已生成的skill列表"""
        return self._generated_skills

    def get_stats(self) -> dict:
        """获取发现统计"""
        return {
            "base_urls_discovered": len(self._discovered_apis),
            "total_apis": sum(len(apis) for apis in self._discovered_apis.values()),
            "skills_generated": len(self._generated_skills),
        }


__all__ = ["APIDiscovery", "APIDescription", "APIParameter", "DiscoveryResult"]