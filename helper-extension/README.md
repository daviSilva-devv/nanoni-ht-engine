# Nanoni Collector Helper

MV3 helper for Telegram Web. It captures the currently visible post, sends a normalized
manifest to the local Nanoni backend, and can associate files explicitly selected by the
operator with that same candidate.

It intentionally does **not** implement or reuse protected-content bypass logic. The main engine therefore never depends on fragile browser reverse-engineering to launch.

## Local bridge

Run the backend only on loopback for helper use:

```powershell
cd backend
.\.venv\Scripts\uvicorn.exe nanoni.api.main:app --host 127.0.0.1 --port 8010
```

Set a per-installation `NANONI_HELPER_SHARED_SECRET`, load this folder as an unpacked
extension in Chrome/Edge, and enter the same secret in the popup. The Source ID is optional;
the backend creates a `telegram-helper` source when it is left blank.
