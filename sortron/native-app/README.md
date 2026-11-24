# Sortron App

Native Android/iOS shell around the existing Sortron customer area. The original website remains separate and unchanged in its account and AI logic.

## Requirements
- Node.js 20.19+ (or a compatible current LTS)
- Android Studio + Android SDK for Android builds
- macOS + Xcode for iOS builds

## Build
```bash
npm ci
npm run build
npx cap add android
npx cap add ios
npx cap sync
node scripts/patch-ios.mjs
```

Open Android Studio with `npx cap open android`, or Xcode with `npx cap open ios`.

The app uses the existing Sortron BLE protocol unchanged:
- BLE name: `MiniR4 Sorter`
- Service: `19b10000-e8f2-537e-4f6c-d104768a1214`
- Characteristic: `19b10001-e8f2-537e-4f6c-d104768a1214`
- ASCII commands `0`–`4`

## Android download build
The repository workflow is `.github/workflows/sortron-android.yml` and builds on changes under `sortron/`.
A GitHub Actions workflow builds a debug APK when Sortron app files are pushed. Download the APK from the workflow's Artifacts section. Android may ask the user to allow installation from the browser or file manager.

## iPhone and iPad
iOS apps must be signed. A normal public IPA download link does not install on every iPhone/iPad. Ad Hoc installation requires registered device identifiers and signing; wider private testing can use TestFlight. The iOS project also needs an Apple signing certificate/profile for a device-installable build.

## Important
The app build is a development build until tested on physical devices. BLE permissions, camera access, Supabase sign-in, and the existing Sortron firmware must be tested on a real iPhone/iPad and Android device before using it with the robot.
