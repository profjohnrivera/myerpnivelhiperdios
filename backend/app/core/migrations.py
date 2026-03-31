# backend/app/core/migrations.py

from __future__ import annotations

import hashlib
import importlib
import inspect
import pkgutil
import re
import traceback
from typing import Optional

from app.core.clock import utc_now_naive


class MigrationRunner:
    """
    Runner de migraciones versionadas por módulo.

    Convención:
    - modules/<mod>/migrations/0001_nombre.py
    - cada archivo debe exponer run(env)
    - si una migración ya fue aplicada con estado done, no se repite
    """

    MIGRATION_NAME_RE = re.compile(r"^\d+_[a-zA-Z0-9_]+$")

    @staticmethod
    def _package_path(module_name: str) -> str:
        return f"modules.{module_name}.migrations"

    @classmethod
    def _is_valid_migration_name(cls, name: str) -> bool:
        return bool(cls.MIGRATION_NAME_RE.match(name))

    @staticmethod
    def _checksum(module_obj) -> Optional[str]:
        try:
            run_func = getattr(module_obj, "run", None)
            if run_func is None:
                return None
            source = inspect.getsource(run_func)
            return hashlib.sha1(source.encode("utf-8")).hexdigest()
        except Exception:
            return None

    @staticmethod
    async def _run_maybe_async(func, *args, **kwargs):
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def run_module(self, env, module_name: str) -> int:
        package_path = self._package_path(module_name)

        try:
            package = importlib.import_module(package_path)
        except ModuleNotFoundError as e:
            if e.name == package_path:
                return 0
            raise RuntimeError(f"❌ Error importando paquete de migraciones '{package_path}': {e}") from e

        if not hasattr(package, "__path__"):
            return 0

        applied_count = 0
        children = sorted(pkgutil.iter_modules(package.__path__), key=lambda x: x[1])

        for _, migration_name, is_pkg in children:
            if is_pkg:
                continue
            if not self._is_valid_migration_name(migration_name):
                continue

            migration_module = importlib.import_module(f"{package_path}.{migration_name}")
            await self._apply_one(env, module_name, migration_name, migration_module)
            applied_count += 1

        return applied_count

    async def _apply_one(self, env, module_name: str, migration_name: str, migration_module) -> None:
        Migration = env["ir.module.migration"]

        rs = await Migration.search(
            [("module_name", "=", module_name), ("name", "=", migration_name)],
            limit=1,
        )
        if rs and hasattr(rs, "load_data"):
            await rs.load_data()

        existing = rs[0] if rs and len(rs) > 0 else None
        if existing and getattr(existing, "state", None) == "done":
            return

        run_func = getattr(migration_module, "run", None)
        if run_func is None:
            raise RuntimeError(
                f"❌ La migración '{module_name}.{migration_name}' no expone run(env)."
            )

        description = getattr(migration_module, "DESCRIPTION", migration_name.replace("_", " "))
        checksum = self._checksum(migration_module)
        started_at = utc_now_naive()

        try:
            await self._run_maybe_async(run_func, env)
            ended_at = utc_now_naive()
            duration_ms = int((ended_at - started_at).total_seconds() * 1000)

            payload = {
                "module_name": module_name,
                "name": migration_name,
                "description": description,
                "state": "done",
                "applied_at": ended_at,
                "duration_ms": duration_ms,
                "checksum": checksum,
                "error_log": None,
                "active": True,
            }

            if existing:
                await existing.write(payload)
            else:
                await Migration.create(payload)

            print(f"   🧬 [MIGRATION] {module_name}.{migration_name} aplicada.")
        except Exception as e:
            ended_at = utc_now_naive()
            duration_ms = int((ended_at - started_at).total_seconds() * 1000)
            error_log = f"{str(e)}\n\n{traceback.format_exc()}"

            payload = {
                "module_name": module_name,
                "name": migration_name,
                "description": description,
                "state": "failed",
                "applied_at": ended_at,
                "duration_ms": duration_ms,
                "checksum": checksum,
                "error_log": error_log,
                "active": True,
            }

            if existing:
                await existing.write(payload)
            else:
                await Migration.create(payload)

            raise RuntimeError(
                f"❌ Migración fallida: {module_name}.{migration_name}\n{str(e)}"
            ) from e