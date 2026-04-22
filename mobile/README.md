# 📱 Vera Mobile — React Native App

Voice-first mobile companion for the eVera AI assistant. Connects to your eVera server over WiFi.

## Features

- 🎙️ **Voice input** — Native speech-to-text via platform APIs
- 🔊 **Voice output** — Text-to-speech for Vera's responses
- 💬 **Real-time chat** — WebSocket connection with streaming support
- 🔔 **Push notifications** — FCM (Android) / APNs (iOS) for proactive alerts
- 📱 **Native permissions** — Microphone, camera, contacts, calendar, location
- 🎨 **Dark glassmorphism UI** — Matches the desktop app design
- 🔄 **Auto-reconnect** — Exponential backoff reconnection logic
- 🔒 **API key auth** — Secure WebSocket connection

## Setup

### Prerequisites

- Node.js 18+
- React Native CLI (`npm install -g react-native`)
- Android Studio (for Android) or Xcode (for iOS)
- eVera server running on your PC

### Install Dependencies

```bash
cd mobile
npm install
```

### iOS Additional Setup

```bash
cd ios && pod install && cd ..
```

### Configure eVera Server

On your PC, set the server to accept network connections:

```env
# In eVera/.env
VERA_SERVER_HOST=0.0.0.0
```

### Run

```bash
# Android
npx react-native run-android

# iOS
npx react-native run-ios
```

### Connect to Server

1. Launch the app — it opens the Settings screen
2. Enter your PC's IP address (find with `ipconfig` or `ifconfig`)
3. Enter port (default: 8000) and API key (if configured)
4. Tap "Test & Connect"
5. Grant microphone permission when prompted
6. Start talking to Vera! 🎙️

## Architecture

```
mobile/
├── index.js                    # App entry point
├── src/
│   ├── App.tsx                 # Navigation + config management
│   ├── screens/
│   │   ├── ChatScreen.tsx      # Main chat with voice + text input
│   │   └── SettingsScreen.tsx  # Server connection + permissions
│   ├── services/
│   │   ├── api.ts              # REST client + WebSocket client
│   │   ├── voice.ts            # STT + TTS service
│   │   ├── permissions.ts      # Native permission manager
│   │   └── notifications.ts   # FCM + local notifications
│   ├── components/             # Reusable UI components
│   ├── hooks/                  # Custom React hooks
│   └── utils/                  # Helper utilities
├── android/                    # Android native project
├── ios/                        # iOS native project
├── package.json
├── app.json                    # App config with permissions
└── tsconfig.json
```

## Native Permissions Used

| Permission | Platform | Purpose |
|------------|----------|---------|
| `RECORD_AUDIO` / Microphone | Android/iOS | Voice commands |
| `CAMERA` | Android/iOS | Visual analysis |
| `READ_CONTACTS` | Android/iOS | Contact management |
| `READ_CALENDAR` | Android/iOS | Schedule management |
| `ACCESS_FINE_LOCATION` | Android/iOS | Location-aware assistance |
| `POST_NOTIFICATIONS` | Android/iOS | Proactive alerts |
