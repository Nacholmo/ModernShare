# SPDX-License-Identifier: AGPL-3.0-or-later
"""Publishing a demo photo must not permit arbitrary camera captures."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('repo_audit',ROOT/'scripts/audit_repo.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
REQUIRED=['LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','LICENSES/MIT-Film-Luts.txt',
          'LICENSES/Apache-2.0.txt','boot_image.png','src/release/bundle-0.9.json']
PHOTO='photos/modernshare.jpg'

class PublicPhotoAuditTests(unittest.TestCase):
    def check_tree(self,photo_path=PHOTO,changed=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in REQUIRED:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture')
            p=root/photo_path;p.parent.mkdir(parents=True,exist_ok=True)
            data=(ROOT/PHOTO).read_bytes();p.write_bytes(data+(b'changed metadata' if changed else b''))
            with patch.object(audit,'ROOT',root),patch.object(audit,'public_files',return_value=REQUIRED+[photo_path]):
                return audit.audit()

    def test_authorized_photo_passes(self):
        self.assertIn(PHOTO,self.check_tree())

    def test_same_image_at_unapproved_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'private/generated file'):
            self.check_tree('photos/private-capture.jpg')

    def test_changed_content_at_authorized_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'unreviewed photo content'):
            self.check_tree(changed=True)
