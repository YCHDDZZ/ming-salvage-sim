# Electron Release Flow

## Local dev

```bash
cd web
MING_SIM_STEAM_APP_ID=4809750 npm run electron
```

This uses the local Python environment and starts `uvicorn web_app:app`.

## Build backend sidecar

```bash
cd web
npm run backend:build
```

Output:

```text
build/backend-dist/MingSalvageBackend/
```

## Build macOS app bundle

```bash
cd web
npm run dist:mac
```

Output:

```text
web/release/mac-arm64/MingSalvageSim.app
```

## Build Windows unpacked app

```bash
cd web
npm run dist:win
```

Output:

```text
web/release/win-x64-unpacked/
```

On macOS, a cross-build may also produce a platform-specific folder like `web/release/win-arm64-unpacked/`.
For a real Steam Windows upload build, prefer the native Windows GitHub Actions job so the backend sidecar is also built for Windows.

## Steam upload target

- macOS depot: upload the whole `.app`
- Windows depot: upload the full contents of `win-*-unpacked/`

Do not upload `web/dist`.

## GitHub Actions

Native per-platform Electron builds are defined in:

```text
.github/workflows/electron-release.yml
```

This is the recommended way to produce:

- macOS `.app` with macOS backend sidecar
- Windows `win-x64-unpacked/` with Windows backend sidecar
