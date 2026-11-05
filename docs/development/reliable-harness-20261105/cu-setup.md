# User-local CU configuration

This is opt-in integration and requires a legally available local bridge and binaries. Do not copy them into a public package. Configure the environment in a local launch profile, substituting paths supplied by the owner:

```json
{
  "GCODE_PI_EXTENSION": "<absolute path to installed desktop extension.ts>",
  "GCODE_PI_SDK_PACKAGE": "<absolute path to installed pi-coding-agent package.json>",
  "GCODE_PI_MANIFEST": "<absolute path to frozen desktop-stability manifest.json>",
  "PI_AGENT_DESKTOP_BINARY": "<absolute path to original native AX program>",
  "PI_AGENT_DESKTOP_APP": "<explicit initial authorized app>",
  "PI_AGENT_DESKTOP_ALLOWED_APPS": "[\"<explicit initial authorized app>\"]",
  "PI_CU_WINDOW_KEYBOARD": "<optional absolute path to original keyboard program>"
}
```

The JSON is illustrative; do not set the optional keyboard variable to a placeholder. Use the default machine state for every invocation; if an override is needed, `GCODE_CU_MACHINE_DIR` must be the same private absolute directory for every sidecar on this user's desktop. Do not change it to escape an unknown-delivery fence. Secure the directory and retain its ledger. GCODE_PI_MANIFEST is required for a verified frozen manifest; hello without it reports `manifest_verified:false`.

The application owns transport lifecycle and authorization. The integration shape is:

```python
transport = CUTransport(node_path, sidecar_server, provider_adapter, private_transport_state)
await transport.start()
hello = await transport.hello(context.run_id, context.session_id)
tools = desktop_tools_from_hello(transport, hello, allow_write=context.allow_cu_write)
# Register these with the existing permission-aware runner; invoke using Tool.invoke(params, context).
# On shutdown, wait for the current call to finish, retain receipts, then:
await transport.shutdown(context.run_id, context.session_id)  # closes only a known, idle owner
```

All paths passed to CUTransport must be explicit absolute paths except the Node executable, which may resolve on PATH. Obtain schemas dynamically through hello. Child contexts must set `parent_run_id`; DesktopTool denies child writes independently of registration. Do not expose the provider path, binary, state directory or a shell command as model-supplied tool parameters.
