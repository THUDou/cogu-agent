from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Optional

from cogu.state.backend import StateBackend, StateBackendType, StateRecord

logger = logging.getLogger(__name__)

S3_PREFIX = "cogu/state/"


class S3StateBackend(StateBackend):
    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key: str = "",
        secret_key: str = "",
        region: str = "us-east-1",
        name: str = "s3",
    ):
        super().__init__(name=name, backend_type=StateBackendType.S3)
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self._client = None
        self._index: dict[str, StateRecord] = {}

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _obj_key(self, key: str) -> str:
        return f"{S3_PREFIX}{key}.json"

    async def push(self, key: str, value: Any, metadata: Optional[dict[str, Any]] = None) -> StateRecord:
        if self._client is None:
            return StateRecord(key=key, value=value, version=1)

        existing = self._index.get(key)
        now = self._now()
        if existing is not None:
            existing.value = value
            existing.version += 1
            existing.updated_at = now
            if metadata:
                existing.metadata.update(metadata)
            record = existing
        else:
            record = StateRecord(
                key=key,
                value=value,
                version=1,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
            )
            self._index[key] = record

        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=self._obj_key(key),
                Body=json.dumps(
                    {
                        "key": record.key,
                        "value": record.value,
                        "version": record.version,
                        "created_at": record.created_at,
                        "updated_at": record.updated_at,
                        "metadata": record.metadata,
                    },
                    ensure_ascii=False,
                ),
                ContentType="application/json",
            )
        except Exception:
            logger.exception("S3StateBackend push failed for key %s", key)

        await self._notify_watchers(key, [record])
        return record

    async def pull(self, key: str) -> Optional[StateRecord]:
        if key in self._index:
            return self._index[key]
        if self._client is None:
            return None
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=self._obj_key(key))
            body = json.loads(resp["Body"].read().decode("utf-8"))
            record = StateRecord(
                key=body["key"],
                value=body.get("value"),
                version=body.get("version", 1),
                created_at=body.get("created_at", ""),
                updated_at=body.get("updated_at", ""),
                metadata=body.get("metadata", {}),
            )
            self._index[key] = record
            return record
        except self._client.exceptions.NoSuchKey:
            return None
        except Exception:
            logger.debug("S3StateBackend pull failed for key %s", key)
            return None

    async def delete(self, key: str) -> bool:
        self._index.pop(key, None)
        if self._client is None:
            return True
        try:
            self._client.delete_object(Bucket=self.bucket, Key=self._obj_key(key))
            return True
        except Exception:
            return False

    async def list_keys(self, prefix: str = "") -> list[str]:
        if self._client is None:
            return list(self._index.keys())
        try:
            resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix=f"{S3_PREFIX}{prefix}")
            keys = []
            for obj in resp.get("Contents", []):
                obj_key = obj["Key"]
                if obj_key.endswith(".json"):
                    key = obj_key[len(S3_PREFIX):-5]
                    keys.append(key)
            return keys
        except Exception:
            return list(self._index.keys())

    async def pull_batch(self, keys: list[str]) -> dict[str, Optional[StateRecord]]:
        results: dict[str, Optional[StateRecord]] = {}
        for key in keys:
            results[key] = await self.pull(key)
        return results

    async def push_batch(self, records: list[tuple[str, Any]]) -> list[StateRecord]:
        results = []
        for key, value in records:
            results.append(await self.push(key, value))
        return results

    async def start(self) -> None:
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3StateBackend. Install with: pip install cogu-agent[s3]"
            )
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception:
            self._client.create_bucket(Bucket=self.bucket)
            logger.info("S3StateBackend created bucket %s", self.bucket)
        self._running = True
        logger.info("S3StateBackend connected to %s/%s", self.endpoint_url, self.bucket)

    async def stop(self) -> None:
        self._running = False
        self._client = None
        self._index.clear()
