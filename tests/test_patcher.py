# SPDX-License-Identifier: AGPL-3.0-or-later
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch as mockpatch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import modernshare_patcher as engine

class InputRejectionTest(unittest.TestCase):
    def test_wrong_model_and_arbitrary_files(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'wrong.exe';p.write_bytes(b'not a Kodak updater')
            with self.assertRaises(ValueError):engine.read_stock(p)
    def test_zip_without_firmware(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'wrong.exe'
            with zipfile.ZipFile(p,'w') as z:z.writestr('setup.exe',b'unsupported')
            with self.assertRaisesRegex(ValueError,'exactly one'):engine.read_stock(p)
    def test_duplicate_firmware(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'wrong.exe'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('one/kc713.fw',b'a');z.writestr('two/KC713.FW',b'b')
            with self.assertRaisesRegex(ValueError,'exactly one'):engine.read_stock(p)
    def test_rejects_zip_bomb_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'wrong.exe'
            with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('kc713.fw',bytes(3000000))
            with self.assertRaisesRegex(ValueError,'unsupported'):engine.read_stock(p)
    def test_archive_paths_are_never_extracted(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'wrong.exe'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../../kc713.fw',b'wrong')
            with self.assertRaises(ValueError):engine.read_stock(p)
            self.assertEqual([p.name for p in Path(folder).iterdir()],['wrong.exe'])
    def test_refuses_existing_output_before_reading_input(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'KC713.FW';p.write_bytes(b'keep this')
            with self.assertRaises(FileExistsError):engine.generate('missing.exe',p)
            self.assertEqual(p.read_bytes(),b'keep this')
    def test_invalid_input_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'bad.exe';source.write_bytes(b'bad');output=Path(folder)/'KC713.FW'
            with self.assertRaises(ValueError):engine.generate(source,output)
            self.assertFalse(output.exists())

@unittest.skipUnless(os.environ.get('MODERNSHARE_STOCK'),'Provide MODERNSHARE_STOCK for local proprietary-input integration tests')
class LocalFirmwareIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.stock=Path(os.environ['MODERNSHARE_STOCK']).read_bytes()
    def test_bundle_reproduces_camera_confirmed_hash(self):
        result=engine.patch(self.stock)
        self.assertEqual(hashlib.sha256(result).hexdigest(),engine.RELEASE_SHA256)
    def test_damaged_bundle_fails(self):
        bundle=json.loads((ROOT/'src/release/bundle-0.8.json').read_text());bundle['patch_data_sha256']='0'*64
        with self.assertRaises(ValueError):engine.patch(self.stock,bundle)
    def test_crc_valid_wrong_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'wrong.exe';bad=bytearray(self.stock);bad[-1]^=1
            with zipfile.ZipFile(p,'w') as z:z.writestr('kc713.fw',bad)
            with self.assertRaisesRegex(ValueError,'SHA-256'):engine.read_stock(p)
    def test_sfx_container_and_output(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'synthetic.exe';p.write_bytes(b'MZ'+bytes(1234))
            with zipfile.ZipFile(p,'a',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('nested/kc713.fw',self.stock)
            before=p.read_bytes();output=Path(folder)/'KC713.FW';events=[]
            result=engine.generate(p,output,lambda n,s:events.append(n))
            self.assertEqual(result['sha256'],engine.RELEASE_SHA256);self.assertEqual(p.read_bytes(),before)
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),engine.RELEASE_SHA256)
            self.assertEqual(events,[10,40,85,100])
    @unittest.skipUnless(os.environ.get('MODERNSHARE_UPDATER'),'Provide MODERNSHARE_UPDATER for original updater test')
    def test_original_updater_extracts_exact_stock(self):
        self.assertEqual(engine.read_stock(Path(os.environ['MODERNSHARE_UPDATER'])),self.stock)

if __name__=='__main__':unittest.main()
