import unittest
from types import SimpleNamespace

from iracing_local import raw_session_info


class SessionEncodingTests(unittest.TestCase):
    def sdk(self, payload, **attributes):
        return SimpleNamespace(
            _header=SimpleNamespace(session_info_offset=6, session_info_len=len(payload)),
            _shared_mem=b'prefix' + payload + b'not session data',
            **attributes,
        )

    def test_legacy_sdk_reads_windows_encoding_without_property(self):
        text = 'WeekendInfo:\n TrackName: Montr\u00e9al\n'
        sdk = self.sdk(text.encode('cp1252') + b'\x00\x00')
        self.assertEqual(raw_session_info(sdk), text)

    def test_legacy_sdk_detects_utf8_session_marker(self):
        text = '---\nWeekendInfo:\n Encoding: UTF8\n TrackName: Montr\u00e9al\n'
        self.assertEqual(raw_session_info(self.sdk(text.encode('utf-8'))), text)

    def test_current_sdk_encoding_flag_is_respected(self):
        text = 'WeekendInfo:\n TrackName: Montr\u00e9al\n'
        for is_utf8, encoding in [(True, 'utf-8'), (False, 'cp1252')]:
            with self.subTest(encoding=encoding):
                sdk = self.sdk(text.encode(encoding), is_session_info_utf8=is_utf8)
                self.assertEqual(raw_session_info(sdk), text)

    def test_unknown_flag_falls_back_to_session_marker(self):
        text = '---\nWeekendInfo:\n Encoding: UTF8\n TrackName: Montr\u00e9al\n'
        sdk = self.sdk(text.encode('utf-8'), is_session_info_utf8=None)
        self.assertEqual(raw_session_info(sdk), text)


if __name__ == '__main__':
    unittest.main()
