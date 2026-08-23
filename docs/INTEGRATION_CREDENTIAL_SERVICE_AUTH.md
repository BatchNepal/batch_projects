# Integration credential service-auth contract

Decrypted values from `BP Integration Credential` cross the Frappe → Gateway
boundary through exactly one endpoint:

`POST /api/method/batch_projects.api.credentials.get_credential_secret`

Ordinary Frappe authentication is necessary but not sufficient. The request
must also carry a Gateway-only HMAC proof made with the existing
`bp_gateway_shared_secret` / `frappe.shared_secret` deployment secret:

- `X-BP-Gateway-Timestamp`: Unix seconds
- `X-BP-Gateway-Nonce`: 16 or more random bytes encoded as lowercase hex
- `X-BP-Gateway-Signature`: `v1=<hex HMAC-SHA256>`

The signed message is:

```text
UPPERCASE_METHOD
REQUEST_PATH
TIMESTAMP
NONCE
SHA256_HEX(EXACT_REQUEST_BODY)
```

Frappe accepts at most five minutes of clock skew and atomically claims each
nonce in Redis for the same interval. Signatures are bound to the HTTP method,
exact endpoint, exact body, timestamp, and nonce. A captured request therefore
cannot be replayed or moved to another API.

Administrator and System Manager roles do not bypass this proof. Human
administrators may use the metadata/configuration APIs to create, rotate, list,
or delete credentials, but no human-role check authorizes plaintext export.

Compatibility: Gateway and batch_projects must be deployed together for this
change. An upgraded Frappe app rejects older unsigned Gateway lookups; an
upgraded Gateway fails closed if its shared signing secret is not configured.
Secret response bodies are never included in Gateway errors.
