"""fps-adapters/rest/middleware/cors_config.py — CORS 設定 ★v3.0"""
CORS_DEFAULTS = {
    "allow_origins":     ["*"],
    "allow_credentials": False,
    "allow_methods":     ["*"],
    "allow_headers":     ["*", "X-Api-Key"],
}
_TRUSTED_ORIGINS = [
    "http://localhost:8188", "http://localhost:7860", "http://localhost:8420",
    "http://127.0.0.1:8188", "http://127.0.0.1:7860", "http://127.0.0.1:8420",
]
def get_cors_origins(extra: list[str] | None = None) -> list[str]:
    origins = list(_TRUSTED_ORIGINS)
    if extra: origins.extend(extra)
    return origins
