# SPDX-License-Identifier: AGPL-3.0-or-later
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mods.ui.src.local_graphics import repack

class LocalGraphicsTest(unittest.TestCase):
    def test_noncanonical_stock_stream(self):
        # Literal A, zero-length packet, repeated final byte past image bounds.
        self.assertEqual(repack(bytes([3,65,0,0,254,66]),0,2),bytes([5,65,66]))
    def test_truncated_and_invalid_bounds(self):
        for source,offset,count in [(b'',0,1),(b'\x07A',0,3),(b'\x02',0,1),(b'',-1,1),(b'',0,0),(b'',0,480*240+1)]:
            with self.subTest(source=source,offset=offset,count=count),self.assertRaises(ValueError):
                repack(source,offset,count)
