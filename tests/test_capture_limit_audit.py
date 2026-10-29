"""Changed source must not inherit conclusions from the current capture path."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture_audit', ROOT/'tools/kernel/audit_capture_limit.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = {
            a.FILTER: '''void dp_mon_set_local_pkt_capture_rx_filter(int pdev) {
                dst.tlv_filter.packet_header = 1;
                dst.tlv_filter.rx_hdr_length = RX_HDR_DMA_LENGTH_256B;
            }
            void dp_mon_start_local_pkt_capture(int pdev) {
                dp_mon_set_local_pkt_capture_rx_filter(pdev, filter);
            }''',
            a.ENUM: '''enum dp_rx_hdr_dma_length { DEFAULT_RX_HDR_DMA_LENGTH = 0,
                RX_HDR_DMA_LENGTH_64B=1, RX_HDR_DMA_LENGTH_128B=2, RX_HDR_DMA_LENGTH_256B=3 };''',
            a.RX: '''void dp_rx_handle_local_pkt_capture(void) {
                switch (type) {case HAL_TLV_STATUS_HEADER: qdf_nbuf_clone(nbuf);
                    first_msdu_payload; payload_len; qdf_nbuf_trim_tail(buf,len);}
            }''',
            a.CFG: '''void __wlan_hdd_cfg80211_update_mgmt_frame_registrations(void) {
                hdd_debug("{ this is only a log }"); /* sme_register_mgmt_frame(); */
            }''',
            'kernel/wonder/mac80211.c': 'void wonder_rx_80211_frame(void) { netif_receive_skb(skb); }',
            'native/wireless/action_tx.c': 'int awdl_main(void) {unsigned char frame[8192]; recvfrom(fd,frame,sizeof(frame),MSG_TRUNC);}',
        }
        self.save()

    def save(self):
        for name, text in self.files.items():
            p = self.root/name
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(text)

    def test_header_path_is_not_full_frame_claim(self):
        r = a.audit(self.root, self.root)
        self.assertEqual(r['configured_header_bytes'],256)
        self.assertEqual(r['maximum_declared_header_bytes'],256)
        self.assertEqual(r['listener_buffer_bytes'],8192)
        self.assertFalse(r['registration_callback_programs_sme'])
        self.assertFalse(r['stock_binary_matches_audited_source'])
        self.assertFalse(r['full_frame_rx_implemented'])

    def test_changed_enum_is_not_silently_reused(self):
        self.files[a.ENUM] = self.files[a.ENUM].replace('256B=3','256B=4')
        self.save()
        with self.assertRaises(ValueError): a.audit(self.root,self.root)

    def test_new_larger_enum_is_reported_separately_from_config(self):
        self.files[a.ENUM] = self.files[a.ENUM].replace(' };', ', RX_HDR_DMA_LENGTH_512B=4 };')
        self.save()
        r=a.audit(self.root,self.root)
        self.assertEqual(r['maximum_declared_header_bytes'],512)
        self.assertEqual(r['configured_header_bytes'],256)

    def test_changed_route_rejects_old_conclusion(self):
        self.files[a.FILTER] = self.files[a.FILTER].replace('rx_hdr_length = RX_HDR_DMA_LENGTH_256B','rx_hdr_length = custom_length')
        self.save()
        with self.assertRaises(ValueError): a.audit(self.root,self.root)

    def test_real_sme_call_and_bridge_trim_are_detected(self):
        self.files[a.CFG] = self.files[a.CFG].replace('hdd_debug(', 'sme_register_mgmt_frame(')
        self.files['kernel/wonder/mac80211.c'] = 'void wonder_rx_80211_frame(void) { skb_trim(skb,256); }'
        self.save()
        r=a.audit(self.root,self.root)
        self.assertTrue(r['registration_callback_programs_sme'])
        self.assertTrue(r['wonder_bridge_has_trim_call'])

if __name__=='__main__': unittest.main()
