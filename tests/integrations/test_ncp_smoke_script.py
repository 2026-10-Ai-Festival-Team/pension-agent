from scripts.smoke_test_ncp_object_storage import _safe_error


class ProviderError(Exception):
    operation_name = "PutObject"
    response = {"Error": {"Code": "AccessDenied", "Message": "never print this"}}


def test_ncp_smoke_error_redacts_provider_message_and_configuration():
    assert _safe_error(ProviderError()) == {
        "exception_type": "ProviderError",
        "provider_error_code": "AccessDenied",
        "provider_operation": "PutObject",
    }
