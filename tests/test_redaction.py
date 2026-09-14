from harness.core.redaction import redact


def test_redacts_common_secrets():
    value = "key=sk-12345678901234567890 Bearer abc.def.ghi password=hunter2"
    result = redact(value)
    assert "123456" not in result
    assert "abc.def.ghi" not in result
    assert "hunter2" not in result
    assert "[REDACTED]" in result
