# Security policy

LineSight is a local inspection research application. Report reproducible
security issues privately to Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.

Only load the supplied or locally trained joblib artifact: Python pickle
artifacts can execute code. Never load third-party untrusted model files.
The API bounds request bytes and decoded image size, allows PNG/JPEG/WebP,
serializes inference, and resolves replay images through an internal index.
The event store keeps decision metadata; it does not retain uploaded images.

The default binds to 127.0.0.1. Before exposing it to a network, add TLS,
authentication, authorization, reverse-proxy request timeouts and rate limits,
resource budgets, retention policy, backups and monitoring. A deployment recipe
is supplied; external hosting and hardware deployment have not been validated.

Dataset-derived assets and pretrained models are noncommercial. This project
has no rejector/PLC actuator and cannot make a physical safety guarantee.
