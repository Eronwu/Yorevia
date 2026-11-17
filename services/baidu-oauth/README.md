# Baidu OAuth device broker prototype

**Not deployed, not a production service. No live Baidu authorization has been tested.** This isolated Node 22+ service is not included in desktop binaries. It uses no dependencies and holds credentials and sessions only in process memory. All test values are synthetic.

## Run after provisioning

1. Rotate any previously disclosed application secret in the Baidu developer console.
2. Configure `BAIDU_APP_KEY` and `BAIDU_SECRET_KEY` through your host's secret manager. Never put values in source, command arguments, screenshots, CI artifacts, or browser code. `SignKey` is not used by this OAuth flow.
3. Run `npm start` from this directory. Default `PORT=8787`; binds **only 127.0.0.1**. Place an HTTPS reverse proxy on the same host in front; do not expose plain HTTP. The desktop client requires an HTTPS origin.
4. Configure native client deployment URL separately. There is deliberately no production URL or shared credential in this repository.
5. Before public access, verify Baidu application status, device-flow eligibility, requested scope/download permissions, quota, terms/privacy, host TLS and logging policy. The `basic,netdisk` scope comes from Baidu's SDK; this is not a promise that Baidu grants a read-only scope. Yorevia itself only reads selected files.

`npm test` runs mock-based security tests. No real credentials are needed.

## Protocol

All endpoints accept POST with exact `Content-Type: application/json`. Browser-origin requests and other methods are rejected; there is no CORS permission. Responses always use `Cache-Control: no-store`. Never add analytics or request/body tracing here.

- `/v1/device/start`: `{proof_hash}` where `proof_hash` is lowercase SHA-256 hex of the **UTF-8 proof string**. Client generates a new random 32-byte proof per attempt, represented as 64-character lowercase hex or 43-character base64url. Returns `{session_id,verification_url,user_code,interval,expires_in}`. Keep proof in the native process; never expose it to browser or logs.
- Open the official verification page, show the user code to the user, and let the user authorize directly at Baidu. The broker only accepts `https://openapi.baidu.com/device` with no query, fragment, credentials, or nonstandard port. Unexpected provider URL fails closed and must be investigated, not loosened automatically.
- `/v1/device/poll`: `{session_id,proof}`. Returns `{status:"pending",interval}` or one-use `{status:"authorized",access_token}`. Honor the returned interval, including increases. Early or simultaneous polls stay pending without another upstream exchange. Access token should remain in native memory, not web UI or a browser URL.
- `/v1/device/cancel`: same body; returns `{status:"cancelled"}`. Expiry or cancellation wins over an in-flight upstream exchange.
- Failures use `{error}` and HTTP 400/429/502, never upstream body or URL. Unknown, invalid proof, consumed and cancelled sessions return `invalid_session`; expired session returns `expired` on first lookup. Provider errors can be retried within lifetime except `denied`, which consumes the session. A lost success response requires a new authorization, not replay.

No callback or custom URL scheme is used. Device code and application secret never go to the client; refresh tokens and provider session secrets are discarded. Restart loses pending sessions and forces reauthorization. Session cap is 500, lifetime at most 10 minutes, global starts at most 30/minute. These are conservative prototype limits, not a public-service abuse prevention system.

## Provider contract and deployment limitations

Checked 2026-11-17 against official SDK:
- https://github.com/baidu-netdisk/baidu-drive-sdk-go/blob/main/baidudriver/api/auth_device_code.go
- https://github.com/baidu-netdisk/baidu-drive-sdk-go/blob/main/baidudriver/api/auth_device_token.go
- https://github.com/baidu-netdisk/baidu-drive-sdk-go/blob/main/baidudriver/api/auth.go

The official SDK uses GET query parameters for exchange. The service follows that contract; **outbound proxy/APM URL query capture must be disabled/redacted** because it would otherwise expose the application secret. Upstream endpoint is fixed to `openapi.baidu.com`, redirects are forbidden, 15-second timeout and 64-KiB response bound apply. No request URLs or response bodies are logged by this application.

This is a single-process in-memory design. Do not run multiple replicas without replacing session storage with atomic, expiring shared storage and reviewing concurrency again. The global rate limit can be exhausted by an attacker; a public deployment needs edge abuse controls, request-rate limits and connection/body timeouts, monitored quota and a privacy policy. Do not infer authorization from possession of a device code, and do not share codes with others. Device-flow phishing is still possible when people authorize codes received from attackers; the UI must clearly identify this app and instruct users to initiate authorization themselves.

This does not grant access to users' photos to Yorevia hosting. However, the broker necessarily handles user access tokens transiently during exchange, and the hosting provider can potentially observe runtime memory. Disclose that processing. File listing/download stays directly between the desktop and Baidu. The source's disconnect only clears the local process; it does not revoke authorization at Baidu. Provide the user's Baidu authorization-management route in a production rollout.
