from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from cogu.permission.credentials import CredentialType, CredentialVault, Credential
from cogu.permission.policy import AccessPolicy, PolicyEffect, PolicySet, DefaultPolicies


class AuthLevel(str, Enum):
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    PRIVILEGED = "privileged"
    ADMIN = "admin"


@dataclass
class AuthContext:
    user_id: str
    auth_level: AuthLevel = AuthLevel.AUTHENTICATED
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    session_id: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def is_admin(self) -> bool:
        return self.auth_level == AuthLevel.ADMIN

    @property
    def is_anonymous(self) -> bool:
        return self.auth_level == AuthLevel.ANONYMOUS

    def has_role(self, role: str) -> bool:
        return role in self.roles or self.is_admin

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or self.is_admin


@dataclass
class AuthResult:
    allowed: bool
    reason: str = ""
    auth_level: AuthLevel = AuthLevel.ANONYMOUS
    matched_policy: str = ""
    require_elevation: bool = False


@dataclass
class DeviceSession:
    device_id: str
    device_name: str = ""
    device_type: str = ""
    user_id: str = ""
    verified: bool = False
    verification_key: str = ""
    last_seen: float = 0.0
    metadata: dict = field(default_factory=dict)


class PermissionEngine:
    def __init__(self, credential_path: str = None):
        self._vault = CredentialVault(storage_path=credential_path)
        self._policy_set = PolicySet()
        self._sessions: dict[str, AuthContext] = {}
        self._devices: dict[str, DeviceSession] = {}
        self._role_policies: dict[str, list[str]] = {
            "admin": ["admin_full_access"],
            "reader": ["reader_read_only"],
            "operator": ["reader_read_only"],
        }

        self._policy_set.add(DefaultPolicies.deny_destructive_actions())
        self._policy_set.add(DefaultPolicies.read_only_reader())
        self._policy_set.add(DefaultPolicies.admin_full_access())

    @property
    def vault(self) -> CredentialVault:
        return self._vault

    def add_policy(self, policy: AccessPolicy):
        self._policy_set.add(policy)

    def remove_policy(self, name: str) -> bool:
        return self._policy_set.remove(name)

    def register_role_policies(self, role: str, policy_names: list[str]):
        self._role_policies[role] = policy_names

    def create_session(self, user_id: str, auth_level: AuthLevel = AuthLevel.AUTHENTICATED,
                       roles: list[str] = None, scopes: list[str] = None) -> AuthContext:
        session_id = str(uuid.uuid4())
        ctx = AuthContext(
            user_id=user_id,
            auth_level=auth_level,
            roles=roles or [],
            scopes=scopes or [],
            session_id=session_id,
        )
        self._sessions[session_id] = ctx
        return ctx

    def get_session(self, session_id: str) -> Optional[AuthContext]:
        return self._sessions.get(session_id)

    def destroy_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def authorize(self, session_id: str, action: str, resource: str,
                  context: dict = None) -> AuthResult:
        auth_ctx = self._sessions.get(session_id)
        if not auth_ctx:
            return AuthResult(allowed=False, reason="session not found")

        return self.authorize_context(auth_ctx, action, resource, context)

    def authorize_context(self, auth_ctx: AuthContext, action: str, resource: str,
                          context: dict = None) -> AuthResult:
        eval_ctx = context or {}
        eval_ctx.setdefault("user_id", auth_ctx.user_id)
        eval_ctx.setdefault("auth_level", auth_ctx.auth_level.value)
        eval_ctx.setdefault("roles", auth_ctx.roles)
        eval_ctx.setdefault("scopes", auth_ctx.scopes)

        if auth_ctx.is_admin:
            return AuthResult(
                allowed=True,
                auth_level=AuthLevel.ADMIN,
                matched_policy="admin_full_access",
            )

        for policy in self._policy_set.policies:
            result = policy.evaluate(action, resource, eval_ctx)
            if result == PolicyEffect.DENY:
                return AuthResult(
                    allowed=False,
                    reason=f"denied by policy: {policy.name}",
                    auth_level=auth_ctx.auth_level,
                    matched_policy=policy.name,
                )
            elif result == PolicyEffect.ALLOW:
                return AuthResult(
                    allowed=True,
                    auth_level=auth_ctx.auth_level,
                    matched_policy=policy.name,
                )

        return AuthResult(
            allowed=False,
            reason="no matching policy (default deny)",
            auth_level=auth_ctx.auth_level,
        )

    def elevate(self, session_id: str, target_level: AuthLevel,
                credential_key: str = None) -> AuthResult:
        auth_ctx = self._sessions.get(session_id)
        if not auth_ctx:
            return AuthResult(allowed=False, reason="session not found")

        level_order = {
            AuthLevel.ANONYMOUS: 0,
            AuthLevel.AUTHENTICATED: 1,
            AuthLevel.PRIVILEGED: 2,
            AuthLevel.ADMIN: 3,
        }

        if level_order[target_level] <= level_order[auth_ctx.auth_level]:
            return AuthResult(
                allowed=False,
                reason=f"cannot elevate from {auth_ctx.auth_level.value} to same or lower level",
            )

        if target_level == AuthLevel.ADMIN and credential_key:
            admin_cred = self._vault.get(credential_key)
            if not admin_cred:
                return AuthResult(allowed=False, reason="invalid admin credential")

        auth_ctx.auth_level = target_level
        return AuthResult(
            allowed=True,
            auth_level=target_level,
            reason=f"elevated to {target_level.value}",
        )

    def register_device(self, device_id: str, device_name: str = "",
                        device_type: str = "", user_id: str = "") -> DeviceSession:
        import time

        device = DeviceSession(
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            user_id=user_id,
            verification_key=str(uuid.uuid4()),
            last_seen=time.time(),
        )
        self._devices[device_id] = device
        return device

    def verify_device(self, device_id: str, verification_key: str) -> AuthResult:
        import time

        device = self._devices.get(device_id)
        if not device:
            return AuthResult(allowed=False, reason="device not registered")

        if device.verification_key != verification_key:
            return AuthResult(allowed=False, reason="verification key mismatch")

        device.verified = True
        device.last_seen = time.time()
        return AuthResult(allowed=True, reason="device verified")

    def is_device_verified(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        return device is not None and device.verified

    def list_verified_devices(self, user_id: str = "") -> list[DeviceSession]:
        if user_id:
            return [d for d in self._devices.values() if d.verified and d.user_id == user_id]
        return [d for d in self._devices.values() if d.verified]
