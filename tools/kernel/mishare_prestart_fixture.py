#!/usr/bin/env python3
"""Actions-only production pre-START controller with modeled native completions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import mishare_session_driver_fixture as legacy
ROOT=legacy.ROOT
MODEL=r'''
static unsigned rate_calls;
static bool rate_inline,rate_fail;
static void rate_done(void) {
 state.rate.completed=true;state.rate.receipt.attempted=state.rate.receipt.complete=true;
 state.rate.receipt.attempted_mask=state.rate.receipt.submitted_mask=7;
}
int mishare_runtime_rate_configure(struct mishare_runtime_owner *o,const struct wondertap_fixed_tx_rate_params *p) {
 assert(o==&owner && !state.rate.requested && !calls[4] && !calls[5]);rate_calls++;
 state.rate.requested=state.rate.posted=true;
 state.rate.request=(struct mishare_runtime_rate_request){.preamble=p->preamble,.bw=p->bw,.gi=p->gi,.nss=p->nss,.mcs=p->mcs};
 if(rate_fail){state.rate.completed=true;state.rate.receipt.result=-ENOMEM;return -ENOMEM;}
 state.rate.accepted=true;if(rate_inline)rate_done();return -EINPROGRESS;
}
static struct wondertap_fixed_tx_rate_params rate_params={.preamble=WONDERTAP_RATE_PREAMBLE_HT,.nss=1,.mcs=7};
static int prepare(struct mishare_prestart *c,struct mishare_session *s) {
 return mishare_prestart_step(c,s,&owner,5240,1,2,&rate_params);
}
static void pre_reset(struct mishare_prestart *c,struct mishare_session *s) {
 reset(s);memset(c,0,sizeof(*c));rate_calls=0;rate_inline=rate_fail=false;
 rate_params=(struct wondertap_fixed_tx_rate_params){.preamble=WONDERTAP_RATE_PREAMBLE_HT,.nss=1,.mcs=7};
}
static void reach_channel(struct mishare_prestart *c,struct mishare_session *s) {
 for(unsigned i=0;i<4;i++) {
  assert(prepare(c,s)==-EINPROGRESS && calls[i]==1 && c->selected && "EXPECTED_PRESTART_NATIVE_SEQUENCE");
  if(i==2)assert(prepare(c,s)==-EINPROGRESS && !calls[3] && "EXPECTED_PRESTART_PE_WAIT");
  if(i==3)assert(prepare(c,s)==-EINPROGRESS && !rate_calls && "EXPECTED_PRESTART_CHANNEL_WAIT");
  completed(i);
 }
 assert(s->stage==MISHARE_SESSION_PLAN && !calls[4] && !calls[5]);
 state.work_pending=state.work_users=1;
 assert(prepare(c,s)==-EINPROGRESS && !rate_calls && !c->posted && "EXPECTED_PRESTART_CHANNEL_WORK_DRAIN");
 state.work_pending=0;
 assert(prepare(c,s)==-EINPROGRESS && !rate_calls && !c->posted && "EXPECTED_PRESTART_CHANNEL_WORK_DRAIN");
 state.work_users=0;
}
static void config_tests(void) {
 struct mishare_prestart c;struct mishare_session s;
 for(unsigned mode=0;mode<16;mode++) {
  pre_reset(&c,&s);rate_inline=mode&1;rate_params.nss=mode&2?2:1;
  rate_params.preamble=mode&4?WONDERTAP_RATE_PREAMBLE_HE:WONDERTAP_RATE_PREAMBLE_HT;
  reach_channel(&c,&s);
  assert(prepare(&c,&s)==-EINPROGRESS && c.posted && rate_calls==1 && "EXPECTED_PRESTART_SUBMIT_BARRIER");
  if(!rate_inline){assert(prepare(&c,&s)==-EINPROGRESS && rate_calls==1 && "EXPECTED_PRESTART_RATE_WAIT");rate_done();}
  if(mode&8) {
   state.work_pending=state.work_users=1;
   assert(prepare(&c,&s)==-EINPROGRESS && "EXPECTED_PRESTART_WORK_DRAIN");
   state.work_pending=0;assert(prepare(&c,&s)==-EINPROGRESS && "EXPECTED_PRESTART_WORK_DRAIN");state.work_users=0;
  }
  assert(!prepare(&c,&s) && !prepare(&c,&s) && rate_calls==1 && !calls[4] && !calls[5] &&
   s.stage==MISHARE_SESSION_PLAN && !state.ndi.start_plan_requested && !state.ndi.radio_requested && "EXPECTED_PRESTART_READY_NOT_UP");
  rate_params.mcs--;assert(prepare(&c,&s)==-EBUSY && rate_calls==1 && "EXPECTED_PRESTART_IMMUTABLE_RATE");rate_params.mcs++;
  assert(mishare_prestart_step(&c,&s,&owner,5180,1,2,&rate_params)==-EBUSY && "EXPECTED_PRESTART_IMMUTABLE_CHANNEL");
  s.closing=true;assert(prepare(&c,&s)==-ESHUTDOWN && rate_calls==1 && "EXPECTED_PRESTART_CLOSE");
 }
 for(unsigned fault=0;fault<15;fault++) {
  pre_reset(&c,&s);reach_channel(&c,&s);assert(prepare(&c,&s)==-EINPROGRESS);rate_done();
  if(fault==0)state.rate.receipt.submitted_mask=3;
  if(fault==1)state.rate.receipt.result=-EIO;
  if(fault==2)state.rate.receipt.busy=true;
  if(fault==3)state.rate.receipt.complete=false;
  if(fault==4)state.rate.integrity_error=true;
  if(fault==5)state.rate.accepted=false;
  if(fault==6)state.rate.request.mcs++;
  if(fault==7)state.work_error=-EIO;
  if(fault==8)state.quiesced=MISHARE_QUIESCE_SSR;
  if(fault==9)state.rate.receipt.first_error=-EIO;
  if(fault==10)state.ndi.radio_requested=true;
  if(fault==11)state.ndi.channel_freq=5180;
  if(fault==12)state.rate.requested=false;
  if(fault==13)state.rate.receipt.attempted=false;
  if(fault==14)state.draining=true;
  int expected=fault==1?-EIO:fault==8||fault==14?-ESHUTDOWN:fault==10?-EBUSY:-EUCLEAN;
  assert(prepare(&c,&s)==expected && prepare(&c,&s)==expected && rate_calls==1 && !calls[4] && !calls[5] && "EXPECTED_PRESTART_FAULT_RETAIN");
 }
 pre_reset(&c,&s);reach_channel(&c,&s);rate_fail=true;
 assert(prepare(&c,&s)==-ENOMEM && prepare(&c,&s)==-ENOMEM && rate_calls==1 && "EXPECTED_PRESTART_POST_NO_RETRY");
 pre_reset(&c,&s);rate_params.bw=WONDERTAP_RATE_BW_40;
 assert(prepare(&c,&s)==-EOPNOTSUPP && !c.selected && !calls[0] && "EXPECTED_PRESTART_SUPPORT_CHECK");
 pre_reset(&c,&s);state.rate.requested=true;
 assert(prepare(&c,&s)==-EBUSY && !c.selected && !calls[0] && "EXPECTED_PRESTART_NO_ADOPTION");
 pre_reset(&c,&s);assert(step(&s)==-EINPROGRESS);
 assert(prepare(&c,&s)==-EBUSY && !c.selected && "EXPECTED_PRESTART_NO_ADOPTION");
}
int main(void) {config_tests();assert(!legacy_session_main());puts("MISHARE_PRESTART_CONTROLLER_FIXTURE_PASS_ONLY");return 0;}
'''


def fixture():
    s=legacy.HARNESS.replace('#include "wlan_hdd_mishare_session.h"',
        'typedef uint16_t u16;typedef uint64_t u64;\n#include "wlan_hdd_mishare_prestart.h"')
    return s.replace('int main(void)','static int legacy_session_main(void)',1)+'\n'+MODEL


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':
        raise SystemExit('Controller compilation runs on Actions')
    prod=ROOT/'kernel/popsicle-hdd'
    header=(prod/'wlan_hdd_mishare_prestart.h').read_text()
    controls=[
        ('if (s.work_users || s.work_pending)', 'if (false && (s.work_users || s.work_pending))'),
        ('c->selected = true;', 'c->selected = false;'),
        ('c->posted = true;', 'c->posted = false;'),
        ('if (!s.ndi.channel_completed)', 'if (false && !s.ndi.channel_completed)'),
        ('if (s.work_pending || s.work_users)', 'if (false && (s.work_pending || s.work_users))'),
        ('r->receipt.submitted_mask != 7)', 'false)'),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        (d/'linux/types.h').write_text('/* modeled types */\n')
        (d/'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        (d/'linux/if_ether.h').write_text('#define ETH_ALEN 6\n')
        (d/'wlan_hdd_mishare_wonder_api.h').write_bytes((ROOT/'kernel/provider/wondertap.h').read_bytes())
        for p in prod.glob('*.h'):
            if p.name!='wlan_hdd_mishare_wonder_api.h':(d/p.name).write_bytes(p.read_bytes())
        f=d/'test.c';f.write_text(fixture());exe=d/'test';override=d/'wlan_hdd_mishare_prestart.h'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+tmp,str(f),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        subprocess.run(command,check=True);subprocess.run([exe],check=True,env=env,timeout=15)
        for old,new in controls:
            assert header.count(old)==1,old
            override.write_text(header.replace(old,new,1));subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=15)
            assert bad.returncode==-6 and 'EXPECTED_PRESTART_' in bad.stderr,(old,bad.returncode,bad.stderr[-1800:])
    report=ROOT/'.popsicle-ci/artifacts/reports/mishare-prestart-fixture.json';report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({'status':'MISHARE_PRESTART_CONTROLLER_FIXTURE_PASS_ONLY','success_combinations':16,'receipt_retention_faults':15,'mutations':len(controls),'limitations':'Production controller plus old session controller with modeled native submissions and rate receipts. No native full configuration transaction, parent lease, START/UP or phone/RF/Apple proof.'},indent=2)+'\n')
    print('MISHARE_PRESTART_CONTROLLER_FIXTURE_PASS_ONLY')


if __name__=='__main__':main()
