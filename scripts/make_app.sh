#!/bin/zsh
# Buduje "Liquid Whisper.app" — natywny bundle macOS opakowujący venv projektu.
# Uprawnienia (Accessibility / Input Monitoring / Mikrofon) przypinają się wtedy
# do aplikacji, a nie do terminala. Logi: ~/Library/Logs/LiquidWhisper.log
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Liquid Whisper.app"
MACOS="$APP/Contents/MacOS"

rm -rf "$APP"
mkdir -p "$MACOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleName</key><string>Liquid Whisper</string>
    <key>CFBundleDisplayName</key><string>Liquid Whisper</string>
    <key>CFBundleExecutable</key><string>liquid-whisper</string>
    <key>CFBundleIdentifier</key><string>com.liquidwhisper.app</string>
    <key>CFBundleShortVersionString</key><string>0.1.0</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>CFBundleIconFile</key><string>AppIcon</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>LSUIElement</key><true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>Liquid Whisper nagrywa dyktando po przytrzymaniu hotkeya.</string>
</dict>
</plist>
PLIST

cat > "$MACOS/liquid-whisper" <<LAUNCHER
#!/bin/zsh
cd "$ROOT"
# bez exec: python jako proces potomny dziedziczy odpowiedzialność TCC
# od bundle'a Liquid Whisper — uprawnienia przypinają się do aplikacji
"$ROOT/.venv/bin/python" -m liquid_whisper >> "\$HOME/Library/Logs/LiquidWhisper.log" 2>&1
LAUNCHER
chmod +x "$MACOS/liquid-whisper"

if [[ -f "$ROOT/assets/AppIcon.icns" ]]; then
    cp "$ROOT/assets/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
fi

# podpis ad-hoc — stabilna tożsamość dla TCC (uprawnienia nie znikają po rebuildzie)
codesign --force -s - "$APP"

echo "zbudowano: $APP"
