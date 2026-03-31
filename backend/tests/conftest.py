# backend/tests/conftest.py

import os
import uuid

import pytest
import pytest_asyncio

from app.core.application import Application
from app.core.module_discovery import discover_modules
from app.core.orm import Model


def _assert_test_database() -> None:
    """
    Blindaje para no ejecutar esta suite sobre una BD equivocada.

    Permitido si:
    - ERP_DB_NAME contiene 'test'
    - o ERP_TEST_MODE=1
    """
    db_name = (os.getenv("ERP_DB_NAME") or "").strip().lower()
    explicit_test_mode = (os.getenv("ERP_TEST_MODE") or "").strip() == "1"

    if explicit_test_mode:
        return

    if "test" in db_name:
        return

    raise RuntimeError(
        "🛑 Suite constitucional bloqueada.\n"
        "Configura una BD de pruebas dedicada (ERP_DB_NAME con 'test') "
        "o exporta ERP_TEST_MODE=1 si sabes exactamente lo que haces."
    )


@pytest_asyncio.fixture(scope="session")
async def booted_app():
    """
    Boot real del ERP para pruebas constitucionales.

    Importante:
    esta fixture es session-scoped y debe correr en el mismo loop
    que los tests async. Eso se fija en pytest.ini con:
      asyncio_default_fixture_loop_scope = session
      asyncio_default_test_loop_scope = session
    """
    _assert_test_database()

    app = Application()
    await app.boot(discover_modules("modules"))
    Model._graph = app.kernel.graph

    try:
        yield app
    finally:
        await app.shutdown()


@pytest.fixture
def unique_token() -> str:
    return uuid.uuid4().hex[:8]


@pytest_asyncio.fixture(scope="session")
async def master_data(booted_app):
    """
    Crea sujetos base de la suite:
    - una compañía
    - un producto
    - tres usuarios: admin, alpha, beta
    """
    from tests.helpers import create_company, create_product, create_user

    prefix = f"p5_{uuid.uuid4().hex[:6]}"

    company_id = await create_company(prefix)
    product_id = await create_product(prefix=prefix, price=1.0)

    admin_user = await create_user(prefix=f"{prefix}_admin", company_id=company_id, is_admin=True)
    alpha_user = await create_user(prefix=f"{prefix}_alpha", company_id=company_id, is_admin=False)
    beta_user = await create_user(prefix=f"{prefix}_beta", company_id=company_id, is_admin=False)

    return {
        "prefix": prefix,
        "company_id": company_id,
        "product_id": product_id,
        "admin": admin_user,
        "alpha": alpha_user,
        "beta": beta_user,
    }