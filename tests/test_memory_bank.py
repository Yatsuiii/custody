"""The mapping D2's selective deletion depends on: pure, offline, exact."""

from __future__ import annotations

import re
import unittest

from custody.memory_bank import memory_id_for

_VALID_MEMORY_ID = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")


class MemoryIdForIsADeterministicMapping(unittest.TestCase):
    def test_the_same_record_id_always_maps_to_the_same_memory_id(self):
        record_id = "inv-1:0:0"
        self.assertEqual(memory_id_for(record_id), memory_id_for(record_id))

    def test_different_record_ids_map_to_different_memory_ids(self):
        self.assertNotEqual(memory_id_for("inv-1:0:0"), memory_id_for("inv-1:0:1"))

    def test_a_colon_joined_record_id_produces_a_valid_memory_id(self):
        """`CustodyRecord.id` is not itself Memory-Bank-valid; the mapping
        must be, regardless."""
        mapped = memory_id_for("f8b2c1:12:3")
        self.assertRegex(mapped, _VALID_MEMORY_ID)

    def test_an_empty_record_id_still_produces_a_valid_memory_id(self):
        self.assertRegex(memory_id_for(""), _VALID_MEMORY_ID)


if __name__ == "__main__":
    unittest.main()
