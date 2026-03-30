"""Tests for the SQLite message broker."""

from agentroom.broker import MessageBroker
from agentroom.protocol.models import Message, MessageType


def test_publish_and_poll() -> None:
    broker = MessageBroker(":memory:")

    msg = Message(
        room_id="room1",
        from_agent="@claude",
        type=MessageType.TEXT,
        content="Hello from Claude",
    )
    seq = broker.publish(msg)
    assert seq >= 1

    # Poll as a different agent
    results = broker.poll("room1", "@gpt4o")
    assert len(results) == 1
    assert results[0][1].content == "Hello from Claude"


def test_cursor_advance() -> None:
    broker = MessageBroker(":memory:")

    for i in range(5):
        broker.publish(
            Message(
                room_id="room1",
                from_agent="@claude",
                type=MessageType.TEXT,
                content=f"Message {i}",
            )
        )

    # First poll gets all 5
    results = broker.poll("room1", "@gpt4o")
    assert len(results) == 5

    # Advance cursor to last message
    last_seq = results[-1][0]
    broker.advance_cursor("@gpt4o", "room1", last_seq)

    # Second poll gets nothing
    results = broker.poll("room1", "@gpt4o")
    assert len(results) == 0

    # Publish one more
    broker.publish(
        Message(
            room_id="room1",
            from_agent="@claude",
            type=MessageType.TEXT,
            content="Message 5",
        )
    )

    # Third poll gets only the new one
    results = broker.poll("room1", "@gpt4o")
    assert len(results) == 1
    assert results[0][1].content == "Message 5"


def test_get_history() -> None:
    broker = MessageBroker(":memory:")

    for i in range(10):
        broker.publish(
            Message(
                room_id="room1",
                from_agent="@claude",
                type=MessageType.TEXT,
                content=f"Message {i}",
            )
        )

    history = broker.get_history("room1", limit=5)
    assert len(history) == 5
    # Should be in chronological order (oldest first)
    assert history[0].content == "Message 5"
    assert history[4].content == "Message 9"


def test_listener_callback() -> None:
    broker = MessageBroker(":memory:")
    received: list[Message] = []

    broker.on_message(lambda msg, seq: received.append(msg))

    broker.publish(
        Message(
            room_id="room1",
            from_agent="@claude",
            type=MessageType.TEXT,
            content="Hello",
        )
    )

    assert len(received) == 1
    assert received[0].content == "Hello"
