import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from intentkit.config.base import Base
from intentkit.models.user import User, UserTable


@pytest_asyncio.fixture()
async def user_engine(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[UserTable.__table__])

    yield db_engine


@pytest.mark.asyncio
async def test_get_by_evm_wallet(user_engine):
    session_factory = async_sessionmaker(user_engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            UserTable(
                id="user_with_wallet",
                evm_wallet_address="0x123",
            )
        )
        session.add(
            UserTable(
                id="user_id_only",
            )
        )
        await session.commit()

    direct_match = await User.get_by_evm_wallet("0x123")
    assert direct_match is not None
    assert direct_match.id == "user_with_wallet"

    id_fallback = await User.get_by_evm_wallet("user_id_only")
    assert id_fallback is not None
    assert id_fallback.id == "user_id_only"

    missing = await User.get_by_evm_wallet("0xnotfound")
    assert missing is None


@pytest.mark.asyncio
async def test_timezone_language_roundtrip(user_engine):
    session_factory = async_sessionmaker(user_engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            UserTable(
                id="user_with_locale",
                timezone="Asia/Shanghai",
                language="zh-CN",
            )
        )
        session.add(
            UserTable(
                id="user_without_locale",
            )
        )
        await session.commit()

    with_locale = await User.get("user_with_locale")
    assert with_locale is not None
    assert with_locale.timezone == "Asia/Shanghai"
    assert with_locale.language == "zh-CN"

    without_locale = await User.get("user_without_locale")
    assert without_locale is not None
    assert without_locale.timezone is None
    assert without_locale.language is None
