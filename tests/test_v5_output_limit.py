"""Supplemental independent static-review test, added after candidate inspection."""
import importlib.util
import json
from pathlib import Path
import unittest

import test_v5_contract as helpers


class ReviewOutputLimit(unittest.TestCase):
    def test_record_refuses_oversize_receipt_without_publishing(self):
        case = helpers.V5Contract('test_legacy_v1_roundtrip'); case.setUp()
        try:
            packetpath, packet = case.packet()
            decisions = case.decisions(packet)
            value = json.loads(decisions.read_bytes())
            value['decisions'][0]['rationale'] = ''
            limit = 2 * 1024 * 1024
            base = helpers.encoded(value)
            value['decisions'][0]['rationale'] = 'x' * (limit - len(base) - 1)
            raw = helpers.encoded(value)
            self.assertEqual(len(raw), limit - 1)
            decisions.write_bytes(raw)
            output = case.j / 'journey-review.json'
            case.cli('coherence_review.py', 'record', '--journey', case.j, '--packet', packetpath, '--decisions', decisions, '--output', output, code=2)
            self.assertFalse(output.exists())
            self.assertFalse(list(case.j.glob('.teach-me-review-*')))
        finally:
            case.tearDown()


if __name__ == '__main__':
    unittest.main()
