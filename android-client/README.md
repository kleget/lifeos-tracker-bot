# LifeOS Sync (Android)

Minimal Android client that reads data from Health Connect and sends it to the LifeOS bot HTTP /sync endpoint.

## Requirements
- Android 13 (API 33) or newer
- Health Connect installed/available on the device

## Setup
1. Open `android-client` in Android Studio.
2. Build and run the app.
3. Enter server URL (example: `http://YOUR_SERVER_IP:8088`) and the token (SYNC_HTTP_TOKEN).
4. Tap **Save & Schedule**.
5. Tap **Grant Health Connect Permissions** and allow access.
6. Tap **Sync Now** to test.

## Notes
- Auto sync runs every 15 minutes (WorkManager).
- Each sync sends two days: yesterday and today (prevents late-night data loss).
- No persistent foreground notification is required.
- On some devices, battery optimization can delay background sync; set app battery mode to unrestricted for best reliability.
- Uses HTTP; if you switch to HTTPS later, update the URL.
- Required metrics: steps, sleep, weight, KBJU (nutrition).
