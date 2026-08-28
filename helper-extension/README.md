# Nanoni Collector Helper

MV3 helper for Telegram Web. Its job is to capture the context of the currently viewed post and send a normalized manifest to the local Nanoni backend. A later phase can add a native/local import bridge for files the operator is authorized to save.

It intentionally does **not** implement or reuse protected-content bypass logic. The main engine therefore never depends on fragile browser reverse-engineering to launch.
