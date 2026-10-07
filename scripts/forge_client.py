"""Run forge without a shell and decode GitHub's standard API responses."""
import json
import subprocess


class Forge:
    def __init__(self, repository):
        self.repository = repository

    def run(self, *arguments, allow_missing=False):
        # Explicit --host/--forge-type overrides in forge 0.10.1 select the
        # enterprise API path. OWNER/REPO infers the normal GitHub backend.
        command = ["forge", "-R", self.repository, *map(str, arguments)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode:
            error = result.stderr or result.stdout
            if allow_missing and ("404" in error or "not found" in error.lower()):
                return None
            raise RuntimeError(error.strip() or f"forge exited with status {result.returncode}")
        return result.stdout

    def api(self, endpoint, allow_missing=False):
        response = self.run("api", endpoint, allow_missing=allow_missing)
        return None if response is None else json.loads(response)
