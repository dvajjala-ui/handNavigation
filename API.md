# Run a saved HandNavigate workflow from a script

HandNavigate 0.6 adds a local HTTP API and a PowerShell client. The app must be running on the same Windows computer. The API uses the app's saved browser session and the same approved runner as **Run now** and **Daily**.

In **Daily**, turn on the local API. Its default address is `http://127.0.0.1:47831/v1`. You can choose another port. **Save script client** exports `Invoke-HandNavigate.ps1` from the packaged app; the same script is included at the repository root. It reads the local API token from `%APPDATA%\HandNavigate\integration.json`, so the token does not need to appear in a command or log.

```powershell
# List saved workflows and their approved value rows.
.\Invoke-HandNavigate.ps1 -Action list

# Start row 0 and wait for the result. Replace WORKFLOW_ID with the saved ID.
# Use the same request ID when checking or retrying this particular invocation.
.\Invoke-HandNavigate.ps1 -Action run -WorkflowId WORKFLOW_ID -RowIndex 0 -RequestId office-2026-10-27 -Wait

# Inspect a run or request a stop.
.\Invoke-HandNavigate.ps1 -Action status -RunId RUN_ID
.\Invoke-HandNavigate.ps1 -Action stop -RunId RUN_ID
```

With `-Wait`, the client exits successfully only when the run is `VERIFIED`. A partial, cancelled or unverified result exits with code 1. The app's History contains the actual saved files, duplicate count, visited pages and outcome details. For a custom app profile, supply `-SettingsPath` with that profile's `integration.json`.

## Direct HTTP calls

Every request requires `Authorization: Bearer YOUR_LOCAL_TOKEN`. Copy the token from **Daily** only when using your own client. Requests originating from web pages are rejected; the server binds only to `127.0.0.1`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/v1/health` | Report whether the app is ready and whether its runner is busy |
| GET | `/v1/workflows` | List saved workflows, IDs, configured rows and schedules |
| POST | `/v1/runs` | Start one approved workflow row |
| GET | `/v1/runs/RUN_ID` | Read its durable result and saved image metadata |
| POST | `/v1/runs/RUN_ID/stop` | Request cancellation of that active run; send `{}` |

The run request body is:

```json
{
  "workflowId": "WORKFLOW_ID",
  "rowIndex": 0,
  "requestId": "office-2026-10-27"
}
```

`requestId` must contain 8–128 letters, digits, dots, underscores or hyphens. A new request returns HTTP 202 with a run ID. Repeating the same request returns that same run, including after an app restart. Reusing an ID for another workflow, row or changed revision returns HTTP 409. Use a new ID only when you intend another execution. The API starts saved and approved values; it does not edit workflows or approve new instructions.

For automatic daily runs, the built-in **Daily** scheduler is sufficient. An external scheduler can call the script with a date-based request ID while HandNavigate is open. Closing the app stops this local API and worker. This is a Windows desktop worker; a separate unattended Linux/server deployment is still required for that environment.
