import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from utopiai.memory import add_memory, forget_memory, regenerate_vault
from utopiai.models import (
    Base,
    Character,
    MemoryKind,
    MemoryStatus,
    Persona,
    Relationship,
    User,
)


@pytest.fixture
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as value:
        yield value
    await engine.dispose()


async def relation(session):
    user = User()
    session.add(user)
    await session.flush()
    persona = Persona(user_id=user.id)
    character = Character(
        owner_id=user.id,
        name="C",
        normalized_card={},
        original_payload={},
        original_format="json",
        original_file_name="c.json",
        original_asset_path="c.json",
    )
    session.add_all([persona, character])
    await session.flush()
    value = Relationship(character_id=character.id, persona_id=persona.id)
    session.add(value)
    await session.flush()
    return value


async def test_deduplicate_supersede_forget_and_projection(session, tmp_path):
    relationship = await relation(session)
    first = await add_memory(session, relationship.id, MemoryKind.USER, "Prefere cafe", source="manual")
    duplicate = await add_memory(session, relationship.id, MemoryKind.USER, "Prefere cafe", source="manual")
    assert duplicate.id == first.id
    second = await add_memory(
        session,
        relationship.id,
        MemoryKind.USER,
        "Agora prefere cha",
        source="manual",
        supersedes_id=first.id,
    )
    assert first.status == MemoryStatus.SUPERSEDED
    assert await forget_memory(session, relationship.id, second.id)
    assert second.status == MemoryStatus.FORGOTTEN
    base = await regenerate_vault(session, tmp_path, relationship)
    projection = (base / "usuario.md").read_text(encoding="utf-8")
    assert "## Estado vigente\n\n- Nenhuma." in projection
    assert "(superseded) Prefere cafe" in projection
    assert "(forgotten) Agora prefere cha" in projection


async def test_memory_isolation_between_relationships(session):
    one = await relation(session)
    two = await relation(session)
    memory = await add_memory(session, one.id, MemoryKind.USER, "privado", source="manual")
    assert not await forget_memory(session, two.id, memory.id)
