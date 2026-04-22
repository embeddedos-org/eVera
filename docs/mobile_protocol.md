# Mobile Device Control — WebSocket Protocol

## Overview

Vera can control a connected mobile device via a WebSocket connection at `/ws/mobile`.
The mobile companion app connects to this endpoint and receives commands from Vera's
`MobileControlAgent`.

## Configuration

```env
VERA_MOBILE_CONTROL_ENABLED=true          # Enable the feature
VERA_MOBILE_COMMAND_TIMEOUT_S=10          # Timeout for commands (seconds)
```

## Connection Flow

1. Mobile app connects to `ws://<server>:<port>/ws/mobile?api_key=<key>`
2. Server sends `{"type": "connected", "session_id": "mobile-xxx"}`
3. Mobile sends `device_status` with capabilities
4. Server sends `device_command` messages; mobile responds with `device_command_result`

## Message Types

### Mobile → Server

#### `device_status` (send on connect)
```json
{
  "type": "device_status",
  "platform": "android",       // "android" | "ios"
  "capabilities": [
    "notification", "clipboard", "open_app",
    "set_alarm", "toggle_setting", "device_info"
  ]
}
```

#### `device_command_result` (response to server command)
```json
{
  "type": "device_command_result",
  "id": "abc12345",            // matches the command id
  "success": true,
  "data": { ... },             // command-specific result data
  "message": ""                // human-readable status
}
```

#### `ping`
```json
{"type": "ping"}
```

### Server → Mobile

#### `connected`
```json
{
  "type": "connected",
  "session_id": "mobile-12345"
}
```

#### `device_command`
```json
{
  "type": "device_command",
  "id": "abc12345",
  "command": "notification",
  "params": {
    "title": "Vera",
    "body": "Hello from your assistant!"
  }
}
```

#### `pong`
```json
{"type": "pong"}
```

## Supported Commands

| Command | Params | Description |
|---------|--------|-------------|
| `notification` | `title`, `body` | Show a push notification |
| `open_app` | `app_name` | Open an app by name or package ID |
| `set_alarm` | `time` (HH:MM), `label` | Set an alarm |
| `toggle_setting` | `setting`, `enabled` | Toggle wifi, bluetooth, flashlight, airplane_mode, dnd |
| `clipboard` | `action` (read/write), `text` | Read/write clipboard |
| `device_info` | (none) | Get battery, storage, OS info |

## Example: Android Companion (Kotlin sketch)

```kotlin
val ws = OkHttpClient().newWebSocket(
    Request.Builder().url("ws://192.168.1.100:8000/ws/mobile?api_key=mykey").build(),
    object : WebSocketListener() {
        override fun onOpen(ws: WebSocket, response: Response) {
            ws.send("""{"type":"device_status","platform":"android","capabilities":["notification","open_app"]}""")
        }
        override fun onMessage(ws: WebSocket, text: String) {
            val msg = JSONObject(text)
            when (msg.getString("type")) {
                "device_command" -> handleCommand(ws, msg)
                "pong" -> {}
            }
        }
    }
)
```

## Security

- All connections require the `api_key` query parameter (if `VERA_SERVER_API_KEY` is set)
- The feature must be explicitly enabled via `VERA_MOBILE_CONTROL_ENABLED=true`
- Commands are restricted to the whitelist in `VERA_MOBILE_CONTROL_COMMANDS`
