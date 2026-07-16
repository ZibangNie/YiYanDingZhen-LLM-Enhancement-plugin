from concurrent.futures import ThreadPoolExecutor

from yiyan_dingzhen.domain import Document
from yiyan_dingzhen.memory import MemoryStore, MemoryTurn, SessionMemoryRegistry


def test_memory_store_keeps_exact_turn_limit() -> None:
    store = MemoryStore(max_turns=2)
    for index in range(3):
        store.add(
            MemoryTurn(
                tag=str(index),
                content=[Document(page_content=str(index))],
            )
        )

    assert [turn.tag for turn in store] == ["1", "2"]


def test_session_registry_isolates_sessions() -> None:
    registry = SessionMemoryRegistry(max_sessions=2, max_turns=2)
    first = registry.get("first")
    second = registry.get("second")
    first.add(MemoryTurn(tag="q", content=[Document("secret")]))

    assert first is registry.get("first")
    assert second is registry.get("second")
    assert second.all_documents() == []


def test_memory_store_is_safe_for_concurrent_requests() -> None:
    store = MemoryStore(max_turns=50)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda index: store.add(MemoryTurn(tag=str(index), content=[Document(str(index))])),
                range(200),
            )
        )

    turns = list(store)
    assert len(turns) == 50
    assert len({turn.tag for turn in turns}) == 50
