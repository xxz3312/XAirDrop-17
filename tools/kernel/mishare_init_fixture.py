#!/usr/bin/env python3
"""Actions-only request parser checks; no native allocation or radio model."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define ETH_ALEN 6
#define BIT(n) (1U << (n))
static inline bool is_valid_ether_addr(const u8 *m)
{ return !(m[0]&1) && (m[0]|m[1]|m[2]|m[3]|m[4]|m[5]); }
#include "wlan_hdd_mishare_init.h"
int main(void)
{
 struct wondertap_init_params p={0},q;
 struct mishare_init_request a,b;
 p.channel.freq=5240;p.tx_rate.nss=1;p.mac_addr[0]=2;p.bssid[5]=7;
 memcpy(p.country_code,"CN",3);p.mgmt_retry_limit=3;p.data_retry_limit=5;
 p.rate_adaptation_enable=1;p.tx_rate_mask.max_preamble=WONDERTAP_RATE_PREAMBLE_HE;
 p.tx_rate_mask.max_nss=1;p.tx_rate_mask.max_mcs=11;
 assert(mishare_init_parse(NULL,&a)==-EINVAL && mishare_init_parse(&p,NULL)==-EINVAL);
 assert(!mishare_init_parse(&p,&a));
 for(unsigned field=0;field<21;field++) {
  q=p;
  switch(field) {
   case 0:q.channel.freq=5745;break;
   case 1:q.channel.bandwidth=WONDERTAP_RATE_BW_40;break;
   case 2:q.tx_rate.preamble=WONDERTAP_RATE_PREAMBLE_VHT;break;
   case 3:q.tx_rate.bw=WONDERTAP_RATE_BW_40;break;
   case 4:q.tx_rate.gi=WONDERTAP_RATE_GI_SHORT;break;
   case 5:q.tx_rate.nss=2;break;
   case 6:q.tx_rate.mcs=7;break;
   case 7:q.mac_addr[5]=1;break;
   case 8:q.bssid[5]=8;break;
   case 9:memcpy(q.country_code,"JP",3);break;
   case 10:q.mgmt_retry_limit=255;break;
   case 11:q.data_retry_limit=255;break;
   case 12:q.amsdu_enable=1;break;
   case 13:q.ampdu_enable=1;break;
   case 14:q.rate_adaptation_enable=0;break;
   case 15:q.tx_rate_mask.max_preamble=WONDERTAP_RATE_PREAMBLE_VHT;break;
   case 16:q.tx_rate_mask.max_bw=WONDERTAP_RATE_BW_40;break;
   case 17:q.tx_rate_mask.max_nss=2;break;
   case 18:q.tx_rate_mask.max_mcs=9;break;
   case 19:q.channel.freq=2412;break;
   case 20:memcpy(q.country_code,"00",3);break;
  }
  assert(!mishare_init_parse(&q,&b) && !mishare_init_equal(&a,&b));
 }
 for(unsigned bad=0;bad<17;bad++) {
  q=p;b=a;
  switch(bad) {
   case 0:q.channel.freq=0;break;
   case 1:q.channel.bandwidth=(enum wondertap_rate_bw)-1;break;
   case 2:q.channel.bandwidth=(enum wondertap_rate_bw)5;break;
   case 3:q.tx_rate.preamble=(enum wondertap_rate_preamble)-1;break;
   case 4:q.tx_rate.preamble=WONDERTAP_RATE_PREAMBLE_MAX;break;
   case 5:q.tx_rate.bw=(enum wondertap_rate_bw)-1;break;
   case 6:q.tx_rate.gi=(enum wondertap_rate_gi)5;break;
   case 7:q.tx_rate.nss=0;break;
   case 8:q.tx_rate.nss=9;break;
   case 9:memset(q.mac_addr,0,6);break;
   case 10:q.mac_addr[0]=1;break;
   case 11:q.country_code[2]='X';break;
   case 12:q.country_code[0]='c';break;
   case 13:q.tx_rate_mask.max_preamble=WONDERTAP_RATE_PREAMBLE_MAX;break;
   case 14:q.tx_rate_mask.max_bw=(enum wondertap_rate_bw)-1;break;
   case 15:q.tx_rate_mask.max_nss=0;break;
   case 16:q.tx_rate_mask.max_nss=9;break;
  }
  assert(mishare_init_parse(&q,&b)==-EINVAL && mishare_init_equal(&a,&b));
 }
 q=p;q.reserved1=31;q.reserved2=q.reserved3=255;
 memset(q.tx_rate.reserved,255,sizeof(q.tx_rate.reserved));
 memset(q.tx_rate_mask.reserved,255,sizeof(q.tx_rate_mask.reserved));
 assert(!mishare_init_parse(&q,&b) && mishare_init_equal(&a,&b));
 assert(!b.params.reserved1 && !b.params.reserved2 && !b.params.reserved3 && !b.params.tx_rate.reserved[0]);
 p.rate_adaptation_enable=0;assert(!mishare_init_parse(&p,&a));
 q=p;q.tx_rate_mask.max_preamble=(enum wondertap_rate_preamble)-1;q.tx_rate_mask.max_nss=0;
 assert(!mishare_init_parse(&q,&b) && mishare_init_equal(&a,&b) && !b.params.tx_rate_mask.max_nss);
 assert(!mishare_init_parse(&a.params,&a) && mishare_init_equal(&a,&b));
 puts("MISHARE_INIT_REQUEST_FIXTURE_PASS_ONLY");return 0;
}
'''


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Native compilation runs on Actions')
    sources = {
        'wlan_hdd_mishare_init.h': ROOT/'kernel/popsicle-hdd/wlan_hdd_mishare_init.h',
        'wlan_hdd_mishare_wonder_api.h': ROOT/'kernel/provider/wondertap.h',
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root/'linux').mkdir()
        for name in ['etherdevice.h', 'if_ether.h']:
            (root/'linux'/name).write_text('/* declarations in harness */\n')
        (root/'linux/string.h').write_text('#include <string.h>\n')
        (root/'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        for name, path in sources.items():
            (root/name).write_bytes(path.read_bytes())
        source = root/'test.c'
        source.write_text(HARNESS)
        exe = root/'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-I'+str(root), str(source), '-o', str(exe)], check=True)
        result = subprocess.check_output([exe], text=True, timeout=10,
            env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                     UBSAN_OPTIONS='halt_on_error=1'))
    report = ROOT/'.popsicle-ci/artifacts/reports/mishare-init-fixture.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        'status': result.strip(), 'semantic_field_changes': 21, 'invalid_requests': 17,
        'production_sha256': {n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()},
        'limitations': 'Request parsing/equality only. No regulatory, MCS, platform NSS, parent lifetime, allocation, firmware or radio readiness proof.'
    }, indent=2)+'\n')
    print(result.strip())


if __name__ == '__main__':
    main()
