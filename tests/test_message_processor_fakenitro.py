import pytest

from src.chat.services.message_processor import MessageProcessor


@pytest.mark.asyncio
async def test_extract_fakenitro_emoji_link(monkeypatch):
    processor = MessageProcessor()

    async def fake_fetch(session, url, proxy=None):
        assert url == "https://cdn.discordapp.com/emojis/123456789.webp?size=48"
        return b"emoji-bytes"

    monkeypatch.setattr(processor, "_fetch_image_aio", fake_fetch)

    content, images = await processor._extract_fakenitro_emojis_from_text(
        "hello [smile](https://cdn.discordapp.com/emojis/123456789.webp?size=48)"
    )

    assert content == "hello __EMOJI_smile__"
    assert images == [
        {
            "mime_type": "image/webp",
            "data": b"emoji-bytes",
            "source": "emoji",
            "name": "smile",
            "origin": "fakenitro",
        }
    ]


@pytest.mark.asyncio
async def test_extract_fakenitro_sticker_link(monkeypatch):
    processor = MessageProcessor()

    async def fake_fetch(session, url, proxy=None):
        assert url == "https://media.discordapp.net/stickers/987654321.png?size=160"
        return b"sticker-bytes"

    monkeypatch.setattr(processor, "_fetch_image_aio", fake_fetch)

    original_url = "https://media.discordapp.net/stickers/987654321.png?size=160"
    content, images = await processor._extract_fakenitro_stickers_from_text(
        f"look [wave]({original_url})"
    )

    assert original_url not in content
    assert "wave" in content
    assert images == [
        {
            "mime_type": "image/png",
            "data": b"sticker-bytes",
            "source": "sticker",
            "name": "wave",
            "origin": "fakenitro",
        }
    ]


@pytest.mark.asyncio
async def test_extract_bare_fakenitro_urls(monkeypatch):
    processor = MessageProcessor()
    seen_urls = []

    async def fake_fetch(session, url, proxy=None):
        seen_urls.append(url)
        return f"bytes:{url}".encode()

    monkeypatch.setattr(processor, "_fetch_image_aio", fake_fetch)

    emoji_url = "https://cdn.discordapp.com/emojis/111222333.webp?size=48"
    sticker_url = "https://media.discordapp.net/stickers/444555666.png?size=160"

    emoji_content, emoji_images = await processor._extract_fakenitro_emojis_from_text(
        f"hello {emoji_url}"
    )
    sticker_content, sticker_images = await processor._extract_fakenitro_stickers_from_text(
        f"look {sticker_url}"
    )

    assert emoji_content == "hello __EMOJI_emoji_111222333__"
    assert sticker_content == "look [贴纸: sticker_444555666]"
    assert seen_urls == [emoji_url, sticker_url]
    assert emoji_images[0]["name"] == "emoji_111222333"
    assert sticker_images[0]["name"] == "sticker_444555666"


@pytest.mark.asyncio
async def test_oversized_fakenitro_gif_replaces_link(monkeypatch):
    processor = MessageProcessor()

    async def fake_fetch(session, url, proxy=None):
        return b"too-big"

    monkeypatch.setattr(processor, "_fetch_image_aio", fake_fetch)
    monkeypatch.setattr(processor, "_get_gif_size_limit_bytes", lambda source: 1)

    original_url = "https://cdn.discordapp.com/emojis/123456789.gif?size=48"
    content, images = await processor._extract_fakenitro_emojis_from_text(
        f"hello [dance]({original_url})"
    )

    assert original_url not in content
    assert content == "hello [表情: dance]"
    assert images == []
