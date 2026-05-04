from __future__ import annotations

import unittest

from gpu_idle_notifier.notifier import FeishuNotifier, MultiNotifier, _normalize_send_key


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"code": 0}


class _FakeSession:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.payloads.append({"url": url, **kwargs})
        return _FakeResponse()


class _FakeNotifier:
    def __init__(self, success: bool) -> None:
        self.success = success
        self.calls = 0

    def send_markdown(self, title: str, markdown_body: str) -> bool:
        self.calls += 1
        return self.success


class NotifierTests(unittest.TestCase):
    def test_normalize_send_key_removes_suffix_and_whitespace(self) -> None:
        self.assertEqual(_normalize_send_key("  SCT123.send  "), "SCT123")
        self.assertEqual(_normalize_send_key("SCT123"), "SCT123")
        self.assertEqual(_normalize_send_key(""), "")

    def test_normalize_send_key_accepts_full_serverchan_url(self) -> None:
        self.assertEqual(
            _normalize_send_key("https://sctapi.ftqq.com/SCT123.send"),
            "SCT123",
        )
        self.assertEqual(
            _normalize_send_key("https://sctapi.ftqq.com/SCT123"),
            "SCT123",
        )

    def test_feishu_notifier_sends_text_payload(self) -> None:
        notifier = FeishuNotifier("https://example.test/hook")
        fake_session = _FakeSession()
        notifier.session = fake_session

        self.assertTrue(notifier.send_markdown("GPU Idle", "body"))
        self.assertEqual(fake_session.payloads[0]["url"], "https://example.test/hook")
        self.assertEqual(
            fake_session.payloads[0]["json"],
            {"msg_type": "text", "content": {"text": "GPU Idle\n\nbody"}},
        )

    def test_multi_notifier_succeeds_if_any_provider_succeeds(self) -> None:
        failed = _FakeNotifier(False)
        succeeded = _FakeNotifier(True)
        notifier = MultiNotifier([failed, succeeded])

        self.assertTrue(notifier.send_markdown("title", "body"))
        self.assertEqual(failed.calls, 1)
        self.assertEqual(succeeded.calls, 1)


if __name__ == "__main__":
    unittest.main()
