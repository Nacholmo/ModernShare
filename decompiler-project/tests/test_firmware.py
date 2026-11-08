"""Corruption and extraction gates for the pinned stock analysis input."""
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('firmware',ROOT/'scripts/prepare_firmware.py')
firmware=importlib.util.module_from_spec(spec);spec.loader.exec_module(firmware)

class FirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.stock=(ROOT/'input/kc713.fw').read_bytes()
    def reject(self,blob,message):
        with self.assertRaisesRegex(firmware.FirmwareError,message):firmware.validate_firmware(blob)
    def test_stock_layout_and_identity(self):
        result=firmware.validate_firmware(self.stock)
        self.assertEqual(result['sha256'],firmware.STOCK_SHA256)
        self.assertEqual([s['ram_address'] for s in result['sections'][:3]],[0x30000,0x130000,0x1a0000])
        self.assertFalse(result['sections'][3]['mapped'])
        self.assertEqual(result['sections'][4]['checksum'],0)
        self.assertFalse(result['sections'][4]['checksum_verified'])
    def test_truncated_file(self):self.reject(self.stock[:-1],'Unexpected firmware size')
    def test_header_magic(self):
        blob=bytearray(self.stock);blob[0]=0;self.reject(blob,'RHIR')
    def test_wrong_model(self):
        blob=bytearray(self.stock);struct.pack_into('<I',blob,8,0x034300);self.reject(blob,'Wrong camera model')
    def test_header_sum(self):
        blob=bytearray(self.stock);blob[0x100]^=1;self.reject(blob,'Header checksum mismatch')
    def test_header_complement(self):
        blob=bytearray(self.stock);blob[0x1f8]^=1;self.reject(blob,'Header complement')
    def test_code_corruption(self):
        blob=bytearray(self.stock);blob[0x300]^=1;self.reject(blob,'Section 0 checksum mismatch')
    def test_graphics_corruption_caught_by_identity(self):
        blob=bytearray(self.stock);offset=firmware.validate_firmware(self.stock)['sections'][2]['file_offset'];blob[offset+8]^=1
        self.reject(blob,'pinned stock SHA256')
    def test_failed_validation_writes_nothing(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime/tmp') as folder:
            root=Path(folder);(root/'input').mkdir();(root/'input/kc713.fw').write_bytes(self.stock[:-1])
            with self.assertRaises(firmware.FirmwareError):firmware.prepare(root)
            self.assertEqual([p.name for p in (root/'input').iterdir()],['kc713.fw'])
    def test_extraction_preserves_every_section(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime/tmp') as folder:
            root=Path(folder);(root/'input').mkdir();(root/'input/kc713.fw').write_bytes(self.stock)
            result=firmware.prepare(root)
            for section in result['sections']:
                start=section['file_offset'];self.assertEqual((root/section['path']).read_bytes(),self.stock[start:start+section['size']])
            self.assertEqual((root/'input/kc713.fw').read_bytes(),self.stock)

if __name__=='__main__':unittest.main()
