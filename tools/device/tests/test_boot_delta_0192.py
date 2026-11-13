"""Synthetic boot v4 images; no phone boot or kernel certification."""
import hashlib
import struct
import unittest
import test_identity_0189 as fixtures
from stock_cnss_boot_delta import compare

class BootDeltaTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.IdentityTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.capture=self.fixture.capture()
        self.kernel=b'synthetic kernel payload'
        self.raw=self.image(self.kernel)
        self.reviewed={'kernel_sha256':hashlib.sha256(self.kernel).hexdigest(),
                       'boot_sha256':hashlib.sha256(self.raw).hexdigest()}
    def image(self,kernel,ramdisk=b'ramdisk'):
        header=bytearray(4096);header[:8]=b'ANDROID!'
        struct.pack_into('<II',header,8,len(kernel),len(ramdisk))
        struct.pack_into('<I',header,20,1584);struct.pack_into('<I',header,40,4)
        return bytes(header)+kernel+b'\0'*((-len(kernel))%4096)+ramdisk
    def bound(self,raw):
        return self.fixture.edit(self.capture,'boot_sha256',hashlib.sha256(raw).hexdigest())
    def test_whole_boot_change_can_leave_payload_identical_without_authority(self):
        old=compare(self.raw,self.bound(self.raw),self.reviewed)
        self.assertTrue(old['boot_matches_old_capture'])
        changed=bytearray(self.raw);changed[16]=1;changed=bytes(changed)
        result=compare(changed,self.bound(changed),self.reviewed)
        self.assertEqual(result['status'],'KERNEL_PAYLOAD_MATCH_ONLY')
        self.assertFalse(result['boot_matches_old_capture'])
        for k in ['load_authorized','runtime_certified','accepted_profile_updated']:self.assertIs(result[k],False)
    def test_changed_kernel_is_not_accepted_from_unchanged_version_string(self):
        raw=self.image(b'new synthetic kernel')
        result=compare(raw,self.bound(raw),self.reviewed)
        self.assertEqual(result['status'],'KERNEL_PAYLOAD_CHANGED_REVIEW_REQUIRED')
        self.assertIs(result['load_authorized'],False)
    def test_truncated_headers_sizes_and_ramdisk_rejected(self):
        bad=[b'ANDROID!']
        for offset,value in [(40,3),(20,1583),(8,0),(8,0xffffffff),(12,0xffffffff)]:
            raw=bytearray(self.raw);struct.pack_into('<I',raw,offset,value);bad.append(bytes(raw))
        bad.append(b'BADMAGIC'+self.raw[8:]);bad.append(self.raw[:-1])
        for raw in bad:
            with self.subTest(size=len(raw)),self.assertRaises(ValueError):compare(raw,self.bound(raw),self.reviewed)
    def test_unbound_or_changed_identity_rejected(self):
        with self.assertRaises(ValueError):compare(self.raw,self.capture,self.reviewed)
        bound=self.bound(self.raw)
        for key,value in [('slot.after','_b'),('firmware.after','other'),('capture_status','CAPTURE_INCOMPLETE'),('uid','2000')]:
            with self.assertRaises(ValueError):compare(self.raw,self.fixture.edit(bound,key,value),self.reviewed)

if __name__=='__main__':unittest.main()
