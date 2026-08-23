"""Security contract for decrypted integration-credential retrieval.

Run with:
    bench run-tests --module batch_projects.tests.test_credential_service_identity
"""
import hashlib
import hmac
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api.credentials import (
    _GATEWAY_CREDENTIAL_PATH,
    _gateway_credential_signature_message,
    _verify_gateway_credential_signature,
)


_SECRET = "gateway-only-shared-secret"
_NOW = 1_700_000_000
_BODY = b'{"name":"CRED-1"}'


def _signed_headers(nonce="0123456789abcdef0123456789abcdef", timestamp=_NOW, body=_BODY):
    timestamp = str(timestamp)
    message = _gateway_credential_signature_message(
        "POST", _GATEWAY_CREDENTIAL_PATH, timestamp, nonce, body
    )
    signature = hmac.new(_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {
        "X-BP-Gateway-Timestamp": timestamp,
        "X-BP-Gateway-Nonce": nonce,
        "X-BP-Gateway-Signature": f"v1={signature}",
    }


class TestCredentialServiceIdentity(FrappeTestCase):

    def test_gateway_service_signature_is_accepted(self):
        claimed = []
        _verify_gateway_credential_signature(
            _SECRET, "POST", _GATEWAY_CREDENTIAL_PATH, _BODY,
            _signed_headers(), now=_NOW,
            claim_nonce=lambda nonce: not claimed.append(nonce),
        )
        self.assertEqual(claimed, ["0123456789abcdef0123456789abcdef"])

    def test_human_admin_sessions_have_no_plaintext_capability(self):
        # Roles are intentionally irrelevant: without the Gateway proof,
        # Administrator and System Manager fail like every other human.
        for human in ("Administrator", "system-manager@example.com", "user@example.com"):
            with self.subTest(human=human), self.assertRaises(frappe.PermissionError):
                _verify_gateway_credential_signature(
                    _SECRET, "POST", _GATEWAY_CREDENTIAL_PATH, _BODY, {},
                    now=_NOW, claim_nonce=lambda _nonce: True,
                )

    def test_stale_signature_is_rejected(self):
        with self.assertRaises(frappe.PermissionError):
            _verify_gateway_credential_signature(
                _SECRET, "POST", _GATEWAY_CREDENTIAL_PATH, _BODY,
                _signed_headers(timestamp=_NOW - 301), now=_NOW,
                claim_nonce=lambda _nonce: True,
            )

    def test_signature_is_bound_to_body_and_endpoint(self):
        headers = _signed_headers()
        for path, body in (
            (_GATEWAY_CREDENTIAL_PATH, b'{"name":"CRED-2"}'),
            ("/api/method/batch_projects.api.credentials.list_credentials", _BODY),
        ):
            with self.subTest(path=path, body=body), self.assertRaises(frappe.PermissionError):
                _verify_gateway_credential_signature(
                    _SECRET, "POST", path, body, headers, now=_NOW,
                    claim_nonce=lambda _nonce: True,
                )

    def test_nonce_replay_is_rejected(self):
        claims = set()

        def claim(nonce):
            if nonce in claims:
                return False
            claims.add(nonce)
            return True

        headers = _signed_headers()
        _verify_gateway_credential_signature(
            _SECRET, "POST", _GATEWAY_CREDENTIAL_PATH, _BODY, headers,
            now=_NOW, claim_nonce=claim,
        )
        with self.assertRaises(frappe.PermissionError):
            _verify_gateway_credential_signature(
                _SECRET, "POST", _GATEWAY_CREDENTIAL_PATH, _BODY, headers,
                now=_NOW, claim_nonce=claim,
            )


if __name__ == "__main__":
    unittest.main()
