#!/usr/bin/env python3
"""Execute the production session controller with modeled native completions."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint32_t u32;
#include "wlan_hdd_mishare_session.h"
struct mishare_runtime_owner { int unused; };
static struct mishare_runtime_owner owner;
static struct mishare_runtime_status state;
static unsigned calls[6], snapshots;
static int failure, fail_at;
static int submit(unsigned i) { calls[i]++;return fail_at==(int)i+1?failure:0; }
int mishare_runtime_snapshot(struct mishare_runtime_owner *o,struct mishare_runtime_status *s)
{ assert(o==&owner);snapshots++;*s=state;return 0; }
int mishare_runtime_ndi_create(struct mishare_runtime_owner *o,u8 a,u8 b)
{ assert(o==&owner && a==1 && b==2);return submit(0); }
int mishare_runtime_ndi_prepare(struct mishare_runtime_owner *o)
{ assert(o==&owner);return submit(1); }
int mishare_runtime_ndi_session(struct mishare_runtime_owner *o)
{ assert(o==&owner);return submit(2)?failure:-EINPROGRESS; }
int mishare_runtime_ndi_channel(struct mishare_runtime_owner *o,u32 f)
{ assert(o==&owner && f==5240);return submit(3)?failure:-EINPROGRESS; }
int mishare_runtime_ndi_start_plan(struct mishare_runtime_owner *o)
{ assert(o==&owner);return submit(4)?failure:-EINPROGRESS; }
int mishare_runtime_ndi_start(struct mishare_runtime_owner *o)
{ assert(o==&owner);return submit(5)?failure:-EINPROGRESS; }
static int step(struct mishare_session *s) { return mishare_session_step(s,&owner,5240,1,2); }
static void reset(struct mishare_session *s)
{ memset(s,0,sizeof(*s));memset(&state,0,sizeof(state));memset(calls,0,sizeof(calls));snapshots=0;fail_at=0;failure=-ENOMEM; }
static void completed(unsigned i)
{
 struct mishare_ndi_status *n=&state.ndi;
 switch(i) {
 case 0:n->active=true;n->create.wire_accepted=true;n->create.dp_attached=true;break;
 case 1:n->legacy_ready=true;n->wma_bound=true;n->peer_created=true;break;
 case 2:n->pe_requested=true;n->pe_submitted=true;n->pe_completed=true;n->pe_ready=true;break;
 case 3:n->channel_requested=true;n->channel_submitted=true;n->channel_completed=true;n->channel_prepared=true;n->channel_freq=5240;break;
 case 4:n->start_plan_requested=true;n->start_plan_submitted=true;n->start_plan_completed=true;n->start_plan_ready=true;n->start_plan.freq=5240;break;
 case 5:n->radio_requested=true;state.radio.phase=MISHARE_RADIO_WAIT_START;break;
 }
}
int main(void)
{
 struct mishare_session s;
 reset(&s);
 assert(mishare_session_step(NULL,&owner,5240,1,2)==-EINVAL);
 assert(mishare_session_step(&s,NULL,5240,1,2)==-EINVAL);
 assert(mishare_session_step(&s,&owner,0,1,2)==-EINVAL);
 assert(mishare_session_step(&s,&owner,5240,0,2)==-EINVAL);
 assert(mishare_session_step(&s,&owner,5240,1,3)==-EINVAL);
 assert(!snapshots && !s.configured);
 for(unsigned i=0;i<6;i++) {
  assert(step(&s)==-EINPROGRESS && calls[i]==1);
  /* Queue acceptance must wait for actual PE/channel/plan completion. */
  if(i>=2 && i<5) {
   for(unsigned j=0;j<4;j++)assert(step(&s)==-EINPROGRESS);
   assert(calls[i]==1 && !calls[i+1]);
  }
  completed(i);
 }
 for(unsigned i=0;i<5;i++)assert(step(&s)==-EINPROGRESS && calls[5]==1);
 state.radio.phase=MISHARE_RADIO_UP;
 assert(step(&s)==-EUCLEAN); /* UP without host_up is inconsistent, not ready. */
 reset(&s);
 for(unsigned i=0;i<6;i++){assert(step(&s)==-EINPROGRESS);completed(i);}
 state.radio.phase=MISHARE_RADIO_UP;state.radio.host_up=true;
 assert(step(&s)==0 && step(&s)==0 && calls[5]==1);
 assert(mishare_session_step(&s,&owner,5745,1,2)==-EBUSY);
 assert(mishare_session_step(&s,&owner,5240,2,2)==-EBUSY);
 assert(step(&s)==0);
 state.quiesced=MISHARE_QUIESCE_SSR;
 assert(step(&s)==-ESHUTDOWN);state.quiesced=0;assert(step(&s)==-ESHUTDOWN);
 /* Every failing native stage is one-shot; no retry even on pre-wire failure. */
 for(unsigned fail=1;fail<=6;fail++) {
  reset(&s);fail_at=fail;
  for(unsigned i=0;i<fail-1;i++){assert(step(&s)==-EINPROGRESS);completed(i);}
  assert(step(&s)==-ENOMEM);assert(step(&s)==-ENOMEM && calls[fail-1]==1);
 }
 /* Close is permanent and prevents snapshots/submissions at every stage. */
 for(unsigned stop=0;stop<=6;stop++) {
  reset(&s);
  for(unsigned i=0;i<stop;i++){assert(step(&s)==-EINPROGRESS);completed(i);}
  unsigned before=snapshots;s.closing=true;
  assert(step(&s)==-ESHUTDOWN && snapshots==before);
 }
 reset(&s);state.ndi.active=true;assert(step(&s)==-EBUSY && !calls[0]);
 reset(&s);assert(step(&s)==-EINPROGRESS);assert(step(&s)==-EUCLEAN && !calls[1]);
 reset(&s);state.ndi.completion_error=-EINVAL;assert(step(&s)==-EUCLEAN && !calls[0]);
 reset(&s);state.draining=true;assert(step(&s)==-ESHUTDOWN && !calls[0]);
 reset(&s);s.stage=(enum mishare_session_stage)99;assert(step(&s)==-EUCLEAN && !calls[0]);
 puts("MISHARE_SESSION_DRIVER_FIXTURE_PASS_ONLY");return 0;
}
'''

def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Native compilation runs on Actions')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root/'linux').mkdir()
        (root/'linux/types.h').write_text('/* types supplied by harness */\n')
        (root/'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        source = root/'test.c'
        source.write_text(HARNESS)
        exe = root/'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-I'+str(root), '-I'+str(ROOT/'kernel/popsicle-hdd'),
                        str(source), '-o', str(exe)], check=True)
        subprocess.run([exe], check=True, timeout=10,
                       env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                                UBSAN_OPTIONS='halt_on_error=1'))

if __name__ == '__main__':
    main()
