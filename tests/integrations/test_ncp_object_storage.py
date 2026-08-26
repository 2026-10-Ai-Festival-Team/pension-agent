from pathlib import Path

import pytest

from src.integrations.ncp_object_storage import (
    ArtifactConflictError,
    NcpObjectStorageArtifacts,
    ObjectStorageSettings,
)


class NotFound(Exception):
    response = {"Error": {"Code": "404"}}


class FakeS3:
    def __init__(self):
        self.objects = {}

    def head_object(self, *, Bucket, Key):
        try:
            return self.objects[(Bucket, Key)]
        except KeyError as error:
            raise NotFound() from error

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata):
        self.objects[(Bucket, Key)] = {
            "Metadata": Metadata,
            "Body": Body.read(),
            "ContentType": ContentType,
        }


def _settings():
    return ObjectStorageSettings(
        enabled=True,
        endpoint="https://kr.object.ncloudstorage.com",
        access_key="access",
        secret_key="secret",
        bucket="pension-agent-artifacts",
    )


def test_artifact_upload_is_idempotent_by_sha256(tmp_path):
    artifact = tmp_path / "manifest.json"
    artifact.write_text('{"version": 1}', encoding="utf-8")
    client = FakeS3()
    store = NcpObjectStorageArtifacts(_settings(), client=client)

    first = store.upload_if_absent(artifact, "datasets/gold-seed-v2/manifest.json")
    second = store.upload_if_absent(artifact, "datasets/gold-seed-v2/manifest.json")

    assert first.uploaded is True
    assert second.uploaded is False
    assert first.sha256 == second.sha256
    assert client.objects[("pension-agent-artifacts", "datasets/gold-seed-v2/manifest.json")]["Metadata"]["sha256"] == first.sha256


def test_artifact_upload_refuses_to_overwrite_different_content(tmp_path):
    artifact = Path(tmp_path / "manifest.json")
    artifact.write_text("one", encoding="utf-8")
    store = NcpObjectStorageArtifacts(_settings(), client=FakeS3())
    store.upload_if_absent(artifact, "datasets/gold-seed-v2/manifest.json")
    artifact.write_text("two", encoding="utf-8")

    with pytest.raises(ArtifactConflictError):
        store.upload_if_absent(artifact, "datasets/gold-seed-v2/manifest.json")
