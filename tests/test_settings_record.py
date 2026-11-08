# SPDX-License-Identifier: AGPL-3.0-or-later
import struct
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'mods/sd_settings/src'))
from settings_record import encode,decode,choose

class SettingsRecordTest(unittest.TestCase):
    def test_all_settings_roundtrip(self):
        for film in range(7):
            for dng in range(2):
                for generation in (0,1,0xffffffff):
                    with self.subTest(film=film,dng=dng,generation=generation):
                        r=decode(encode(film,dng,generation))
                        self.assertEqual((r['film_index'],r['dng'],r['generation']),(film,bool(dng),generation))
    def test_every_single_bit_corruption_is_rejected(self):
        original=encode(6,1,43)
        for bit in range(128):
            data=bytearray(original);data[bit//8]^=1<<(bit%8)
            with self.subTest(bit=bit),self.assertRaises(ValueError):decode(data)
    def test_reserved_bits_and_schema_with_valid_checksum_are_rejected(self):
        for config in (0x10002,0x10700,0x1ff00,0x20000,0x1010000):
            magic=0x444f4d4b;g=17;record=struct.pack('<4I',magic,config,g,~(magic^config^g)&0xffffffff)
            with self.subTest(config=hex(config)),self.assertRaises(ValueError):decode(record)
    def test_newest_and_wrap(self):
        self.assertEqual(choose(encode(1,0,4),encode(6,1,5))[0],1)
        self.assertEqual(choose(encode(1,0,0xffffffff),encode(6,1,0))[0],1)
        self.assertEqual(choose(encode(1,0,0),encode(6,1,0xffffffff))[0],0)
    def test_tie_prefers_a(self):
        self.assertEqual(choose(encode(1,0,5),encode(6,1,5))[0],0)
    def test_partial_newer_slot_preserves_previous(self):
        self.assertEqual(choose(encode(1,0,5),encode(6,1,6)[:7])[0],0)
    def test_no_valid_slots(self):self.assertIsNone(choose(b'',b'broken'))

if __name__=='__main__':unittest.main()
