from yiyan_dingzhen.markdown import identify_type, split_markdown


def test_split_markdown_preserves_code_and_image_blocks() -> None:
    blocks = split_markdown("第一段\n\n```python\nprint('ok')\n```\n\n![图](a.png)\n\n最后一段")

    assert [block.type for block in blocks] == ["text", "code", "image", "text"]
    assert "print('ok')" in blocks[1].content


def test_unclosed_code_block_does_not_crash() -> None:
    blocks = split_markdown("正文\n\n```python\nprint('open')")
    assert blocks[-1].type == "code"
    assert identify_type(blocks[-1].content) == "code"
