#!/usr/bin/env python3
"""Actions-only coherent configuration observation; no START submission."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import mishare_prestart_fixture as previous
ROOT=previous.ROOT
READY_VALUES=r'''
static void ready_values(struct mishare_runtime_status *s,struct mishare_prestart *c,
                         struct mishare_session *session,const struct mishare_init_request *q)
{
 const struct wondertap_init_params *p=&q->params;
 memset(s,0,sizeof(*s));memset(c,0,sizeof(*c));memset(session,0,sizeof(*session));
 c->selected=c->posted=true;c->freq=p->channel.freq;c->nss_2g=1;c->nss_5g=2;
 c->rate=(struct mishare_runtime_rate_request){.preamble=p->tx_rate.preamble,.bw=p->tx_rate.bw,
  .gi=p->tx_rate.gi,.nss=p->tx_rate.nss,.mcs=p->tx_rate.mcs};
 session->stage=MISHARE_SESSION_PLAN;session->configured=true;session->freq=c->freq;
 session->nss_2g=1;session->nss_5g=2;
 s->allocated=true;s->bssid.requested=s->bssid.applied=true;memcpy(s->bssid.value,p->bssid,6);
 s->ndi.active=s->ndi.create.wire_accepted=s->ndi.create.dp_attached=s->ndi.create.timer_ready=true;
 s->ndi.create.wire_attempted=s->ndi.create.dp_attempted=true;
 s->ndi.legacy_ready=s->ndi.wma_bound=s->ndi.peer_created=true;
 s->ndi.pe_requested=s->ndi.pe_submitted=s->ndi.pe_completed=s->ndi.pe_ready=true;
 s->ndi.channel_requested=s->ndi.channel_submitted=s->ndi.channel_completed=s->ndi.channel_prepared=true;
 s->ndi.channel_freq=c->freq;
 s->rate.requested=s->rate.posted=s->rate.accepted=s->rate.completed=true;s->rate.request=c->rate;
 s->rate.receipt.attempted=s->rate.receipt.complete=true;
 s->rate.receipt.attempted_mask=s->rate.receipt.submitted_mask=7;
 s->retry.requested=s->retry.posted=s->retry.accepted=s->retry.completed=true;
 s->retry.data_limit=p->data_retry_limit;s->retry.mgmt_limit=p->mgmt_retry_limit;s->retry.vdev_id=7;
 s->retry.receipt.attempted=s->retry.receipt.complete=true;s->retry.receipt.vdev_id=7;
 s->retry.receipt.data_limit=p->data_retry_limit;s->retry.receipt.mgmt_limit=p->mgmt_retry_limit;
 s->retry.receipt.attempted_mask=s->retry.receipt.submitted_mask=
  (p->data_retry_limit?1:0)|(p->mgmt_retry_limit?2:0);
 s->retry.receipt.skipped_mask=3^s->retry.receipt.attempted_mask;
}
'''
PLAN_VALUES=r'''
static void plan_values(struct mishare_runtime_status *s,bool committed)
{
 struct mishare_start_preview_status *p=&s->start_preview;
 *p=(struct mishare_start_preview_status){.requested=true,.posted=true,.completed=true,
  .committed=committed,.vdev_id=s->retry.vdev_id,.freq=s->ndi.channel_freq};
 p->summary=(struct mishare_ndi_start_summary){.freq=p->freq,.center_freq=p->freq,.phy_mode=3,
  .tx_streams=p->freq<3000?1:2,.rx_streams=p->freq<3000?1:2,.beacon_interval=100,.dtim_period=1};
 if(committed){s->ndi.start_plan_requested=s->ndi.start_plan_submitted=s->ndi.start_plan_completed=s->ndi.start_plan_ready=true;s->ndi.start_plan=p->summary;}
}
'''
MODEL=r'''
#include "wlan_hdd_mishare_start_ready.h"
READY_VALUES
static void readiness_cases(void)
{
 struct mishare_runtime_status s,copy;struct mishare_prestart c;struct mishare_session session;
 struct mishare_init_request q;struct wondertap_init_params p={0};
 p.channel.freq=5240;p.tx_rate.preamble=WONDERTAP_RATE_PREAMBLE_HT;p.tx_rate.nss=1;p.tx_rate.mcs=7;
 p.mac_addr[0]=2;p.mac_addr[5]=1;p.bssid[5]=8;memcpy(p.country_code,"CN",3);
 for(unsigned mode=0;mode<16;mode++) {
  p.data_retry_limit=mode&1?0:5;p.mgmt_retry_limit=mode&2?0:3;
  p.tx_rate.nss=mode&4?2:1;p.tx_rate.preamble=mode&8?WONDERTAP_RATE_PREAMBLE_HE:WONDERTAP_RATE_PREAMBLE_HT;
  assert(!mishare_init_parse(&p,&q));ready_values(&s,&c,&session,&q);copy=s;
  for(unsigned repeat=0;repeat<3;repeat++)assert(!mishare_start_ready_check(&s,&c,&session,&q,1,2) &&
   !memcmp(&copy,&s,sizeof(s)) && !s.ndi.start_plan_requested && !s.ndi.radio_requested &&
   "EXPECTED_START_READY_READ_ONLY");
 }
 for(unsigned fault=0;fault<56;fault++) {
  ready_values(&s,&c,&session,&q);int expected=-EUCLEAN;
  switch(fault) {
  case 0:s.quiesced=MISHARE_QUIESCE_SSR;expected=-ESHUTDOWN;break;
  case 1:s.draining=true;expected=-ESHUTDOWN;break;
  case 2:s.freed=true;expected=-ESHUTDOWN;break;
  case 3:session.closing=true;expected=-ESHUTDOWN;break;
  case 4:s.work_pending=1;expected=-EINPROGRESS;break;
  case 5:s.work_users=1;expected=-EINPROGRESS;break;
  case 6:s.work_error=-EIO;break;
  case 7:s.bssid.value[5]^=1;break;
  case 8:s.bssid.applied=false;expected=-EINPROGRESS;break;
  case 9:s.bssid.error=-EIO;expected=-EIO;break;
  case 10:s.rate.accepted=false;break;
  case 11:s.rate.receipt.submitted_mask=3;break;
  case 12:s.rate.receipt.attempted_mask=3;break;
  case 13:s.rate.receipt.busy=true;break;
  case 14:s.rate.receipt.first_error=-EIO;break;
  case 15:s.rate.request.mcs++;break;
  case 16:s.rate.integrity_error=true;break;
  case 17:s.retry.receipt.skipped_mask^=1;break;
  case 18:s.retry.receipt.vdev_id++;break;
  case 19:s.retry.receipt.data_limit++;break;
  case 20:s.retry.receipt.submitted_mask^=1;break;
  case 21:s.retry.accepted=false;break;
  case 22:s.retry.data_limit++;break;
  case 23:s.retry.integrity_error=true;break;
  case 24:s.retry.result=-EIO;expected=-EIO;break;
  case 25:s.rate.completed=false;expected=-EINPROGRESS;break;
  case 26:s.retry.completed=false;expected=-EINPROGRESS;break;
  case 27:session.freq++;break;
  case 28:c.rate.nss=1;break;
  case 29:s.ndi.channel_freq++;break;
  case 30:s.ndi.pe_completed=false;expected=-EINPROGRESS;break;
  case 31:s.ndi.channel_completed=false;expected=-EINPROGRESS;break;
  case 32:s.ndi.start_plan_requested=true;expected=-EBUSY;break;
  case 33:s.ndi.radio_requested=true;expected=-EBUSY;break;
  case 34:s.radio.host_up=true;expected=-EBUSY;break;
  case 35:s.ndi.dp_detaching=true;expected=-EBUSY;break;
  case 36:s.rate.ordinary_admitted=true;expected=-EBUSY;break;
  case 37:s.rate.peer_reset_armed=true;expected=-EBUSY;break;
  case 38:s.allocated=false;expected=-EINPROGRESS;break;
  case 39:c.posted=false;expected=-EINPROGRESS;break;
  case 40:session.stage=MISHARE_SESSION_START;expected=-EBUSY;break;
  case 41:s.rate.receipt.result=-EIO;expected=-EIO;break;
  case 42:s.ndi.create.timer_ready=false;expected=-EINPROGRESS;break;
  case 43:s.ndi.start_plan_completed=true;expected=-EBUSY;break;
  case 44:s.host_delete_accepted=true;expected=-EBUSY;break;
  case 45:s.ndi.completion_error=-EIO;break;
  case 46:s.retry.requested=false;expected=-EINPROGRESS;break;
  case 47:s.rate.requested=false;expected=-EINPROGRESS;break;
  case 48:s.rate.peer_reset_completed=true;expected=-EBUSY;break;
  case 49:s.rate.reset_completed=true;expected=-EBUSY;break;
  case 50:s.mc_stop_seen=true;expected=-EBUSY;break;
  case 51:s.recovery_window=true;expected=-EBUSY;break;
  case 52:s.ndi.pe_requested=false;expected=-EINPROGRESS;break;
  case 53:s.ndi.channel_requested=false;expected=-EINPROGRESS;break;
  case 54:s.ndi.create.wire_attempted=false;expected=-EINPROGRESS;break;
  case 55:s.ndi.create.dp_attempted=false;expected=-EINPROGRESS;break;
  }
  copy=s;assert(mishare_start_ready_check(&s,&c,&session,&q,1,2)==expected &&
   !memcmp(&copy,&s,sizeof(s)) && "EXPECTED_START_READY_BOUNDARY");
 }
 assert(mishare_start_ready_check(NULL,&c,&session,&q,1,2)==-EINVAL);
}

static void plan_commit_observation_cases(void)
{
 struct mishare_runtime_status s,copy;struct mishare_prestart c;struct mishare_session session;
 struct mishare_init_request q;struct wondertap_init_params p={0};
 p.tx_rate.nss=1;p.tx_rate.mcs=7;p.mac_addr[0]=2;p.bssid[5]=8;memcpy(p.country_code,"CN",3);
 for(unsigned band=0;band<2;band++)for(unsigned pair=0;pair<4;pair++)
 for(unsigned phase=0;phase<2;phase++)for(unsigned rate=0;rate<2;rate++) {
  p.channel.freq=band?5240:2437;p.data_retry_limit=pair&1?5:0;p.mgmt_retry_limit=pair&2?3:0;
  p.tx_rate.preamble=rate?WONDERTAP_RATE_PREAMBLE_HE:WONDERTAP_RATE_PREAMBLE_HT;
  assert(!mishare_init_parse(&p,&q));ready_values(&s,&c,&session,&q);plan_values(&s,!!phase);copy=s;
  for(unsigned repeat=0;repeat<3;repeat++)assert(!mishare_start_plan_commit_check(&s,&c,&session,&q,1,2) &&
   !memcmp(&copy,&s,sizeof(s)) && !s.ndi.radio_requested && session.stage==MISHARE_SESSION_PLAN &&
   "EXPECTED_PLAN_CALLER_READ_ONLY");
  assert(mishare_start_ready_check(&s,&c,&session,&q,1,2)==(phase?-EBUSY:0) && "EXPECTED_PLAN_CALLER_OLD_GATE");
 }
 for(unsigned fault=0;fault<32;fault++) {
  ready_values(&s,&c,&session,&q);plan_values(&s,true);int expected=-EUCLEAN;
  switch(fault) {
  case 0:s.start_preview.requested=false;break;
  case 1:s.start_preview.posted=false;break;
  case 2:s.start_preview.completed=false;break;
  case 3:s.start_preview.integrity_error=true;break;
  case 4:s.start_preview.freq=5180;s.start_preview.summary.freq=s.start_preview.summary.center_freq=5180;
         s.ndi.start_plan=s.start_preview.summary;break;
  case 5:s.start_preview.vdev_id++;break;
  case 6:s.start_preview.result=-EIO;break;
  case 7:s.start_preview.summary.freq++;break;
  case 8:s.start_preview.summary.center_freq++;break;
  case 9:s.start_preview.summary.phy_mode=0;break;
  case 10:s.start_preview.summary.tx_streams=0;break;
  case 11:s.start_preview.summary.rx_streams=1;break;
  case 12:s.ndi.start_plan.beacon_interval++;break;
  case 13:s.ndi.start_plan.dtim_period++;break;
  case 14:s.ndi.start_plan_requested=false;break;
  case 15:s.ndi.start_plan_submitted=false;break;
  case 16:s.ndi.start_plan_completed=false;break;
  case 17:s.ndi.start_plan_ready=false;break;
  case 18:s.work_pending=1;expected=-EINPROGRESS;break;
  case 19:s.work_users=1;expected=-EINPROGRESS;break;
  case 20:s.quiesced=MISHARE_QUIESCE_SSR;expected=-ESHUTDOWN;break;
  case 21:session.closing=true;expected=-ESHUTDOWN;break;
  case 22:s.rate.request.mcs++;break;
  case 23:s.retry.data_limit++;break;
  case 24:s.bssid.value[5]++;break;
  case 25:s.ndi.radio_requested=true;expected=-EBUSY;break;
  case 26:s.start_preview.committed=false;expected=-EBUSY;break;
  case 27:s.ndi.start_plan_error=-EIO;break;
  case 28:s.ndi.dp_detaching=true;expected=-EBUSY;break;
  case 29:session.stage=MISHARE_SESSION_START;expected=-EBUSY;break;
  case 30:s.start_preview.summary.phy_mode++;break;
  case 31:s.start_preview.summary.tx_streams=s.start_preview.summary.rx_streams=1;
          s.ndi.start_plan=s.start_preview.summary;break;
  }
  copy=s;
  assert(mishare_start_plan_commit_check(&s,&c,&session,&q,1,2)==expected && !memcmp(&copy,&s,sizeof(s)) &&
   "EXPECTED_PLAN_CALLER_BOUNDARY");
 }
 ready_values(&s,&c,&session,&q);
 assert(mishare_start_plan_commit_check(&s,&c,&session,&q,1,2)==-EINPROGRESS && "EXPECTED_PLAN_CALLER_NO_PREVIEW");
 plan_values(&s,false);s.start_preview.completed=false;s.start_preview.summary=(struct mishare_ndi_start_summary){0};
 assert(mishare_start_plan_commit_check(&s,&c,&session,&q,1,2)==-EINPROGRESS && "EXPECTED_PLAN_CALLER_WAIT");
 s.start_preview.completed=true;s.start_preview.result=-ECANCELED;
 assert(mishare_start_plan_commit_check(&s,&c,&session,&q,1,2)==-ECANCELED && "EXPECTED_PLAN_CALLER_ERROR");
 assert(mishare_start_plan_commit_check(NULL,&c,&session,&q,1,2)==-EINVAL);
}
int main(void) {readiness_cases();plan_commit_observation_cases();assert(!previous_prestart_main());puts("MISHARE_START_READY_FIXTURE_PASS_ONLY");return 0;}
'''

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Native compilation runs only on Actions')
    prod=ROOT/'kernel/popsicle-hdd';header=(prod/'wlan_hdd_mishare_start_ready.h').read_text()
    code=previous.fixture().replace('int main(void)','static int previous_prestart_main(void)',1)+'\n'+MODEL.replace('READY_VALUES',READY_VALUES+'\n'+PLAN_VALUES,1)
    controls=[('s->work_pending || s->work_users','s->work_pending'),
              ('s->quiesced ||','(false && s->quiesced) ||'),
              ('!rate->accepted ||','false ||'),
              ('rate->receipt.submitted_mask != 7','false'),
              ('!mishare_runtime_retry_receipt_valid(retry, &retry->receipt, 0, retry->vdev_id)','(false && !mishare_runtime_retry_receipt_valid(retry, &retry->receipt, 0, retry->vdev_id))'),
              ('memcmp(s->bssid.value, p->bssid, ETH_ALEN)','(false && memcmp(s->bssid.value, p->bssid, ETH_ALEN))'),
              ('session->stage > MISHARE_SESSION_PLAN','false'),
              ('session->freq != p->channel.freq','false'),
              ('n->channel_freq != p->channel.freq','false')]
    plan_controls=[('preview->integrity_error ||','false ||'),
                   ('preview->vdev_id != s->retry.vdev_id','false'),
                   ('preview->freq != request->params.channel.freq','false'),
                   ('!plan->start_plan_submitted ||','false ||'),
                   ('!mishare_start_plan_summary_equal(&preview->summary, &plan->start_plan)','false'),
                   ('preview->summary.tx_streams != (preview->freq < 3000 ? nss_2g : nss_5g)','false')]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name,text in [('types.h','/* modeled types */\n'),('errno.h','#include_next <linux/errno.h>\n'),('if_ether.h','#define ETH_ALEN 6\n'),('etherdevice.h','static inline bool is_valid_ether_addr(const u8 *m) { u8 any=0;for(unsigned i=0;i<6;i++)any|=m[i];return any && !(m[0]&1);}\n'),('string.h','#include <string.h>\n')]: (d/'linux'/name).write_text(text)
        (d/'wlan_hdd_mishare_wonder_api.h').write_bytes((ROOT/'kernel/provider/wondertap.h').read_bytes())
        for p in prod.glob('*.h'):(d/p.name).write_bytes(p.read_bytes())
        f=d/'test.c';exe=d/'test';f.write_text(code)
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+tmp,str(f),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        subprocess.run(command,check=True);subprocess.run([exe],check=True,env=env,timeout=15)
        for old,new in controls:
            assert header.count(old)==1,old
            (d/'wlan_hdd_mishare_start_ready.h').write_text(header.replace(old,new,1));subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=15)
            assert bad.returncode==-6 and 'EXPECTED_START_READY_' in bad.stderr,(old,bad.returncode,bad.stderr[-1800:])
        for old,new in plan_controls:
            assert header.count(old)==1,old
            (d/'wlan_hdd_mishare_start_ready.h').write_text(header.replace(old,new,1));subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=15)
            assert bad.returncode==-6 and 'EXPECTED_PLAN_CALLER_' in bad.stderr,(old,bad.returncode,bad.stderr[-1800:])
    out=ROOT/'.popsicle-ci/artifacts/reports/mishare-start-ready-fixture.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'status':'MISHARE_START_READY_FIXTURE_PASS_ONLY','success_modes':16,'boundary_cases':56,'mutations':len(controls),'plan_success_modes':32,'plan_boundaries':35,'plan_mutations':len(plan_controls),'limitations':'Production pure snapshot predicate with modeled rate/retry/BSSID/native state, plus preceding production prestart/session fixture regressions. No START admission, active-radio teardown, firmware ACK, public init or phone proof.'},indent=2)+'\n')
    print('MISHARE_START_READY_FIXTURE_PASS_ONLY')

if __name__=='__main__':main()
