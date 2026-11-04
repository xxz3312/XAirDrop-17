#!/usr/bin/env python3
"""Actions-only native CE stop and IPCI ISR drain with a controlled producer."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
import mishare_native_transport_stop_fixture as previous
owner=previous.owner
engine=previous.engine
function=previous.function
native=previous.native
CE=previous.CE
BUS=previous.BUS
IPCI='qca-wifi-host-cmn/hif/src/ipcie/if_ipci.c'
BINDING='qca-wifi-host-cmn/hif/src/dispatcher/multibus_ipci.c'
NAMES=[(CE,'hif_ce_stop'),(CE,'hif_destroy_oom_work'),(CE,'hif_buffer_cleanup'),(BUS,'hif_disable_isr'),(IPCI,'hif_ipci_disable_isr')]
TYPES=r'''
struct hif_opaque_softc {int status;};
struct h102_lock {unsigned id,kind;bool destroyed;};
struct h102_timer {bool stopped,freed;};
struct h102_work {unsigned id;bool destroyed;};
struct CE_handle {unsigned id;bool live;};
struct CE_attr {unsigned src_nentries;};
struct CE_state {struct h102_work oom_allocation_work;bool htt_tx_data,htt_rx_data;};
struct hif_ipci_softc {int intr_tq;};
'''
SUPPORT=r'''
#include <pthread.h>
static unsigned h102_flags,h102_irq_step,h102_oom,h102_recv_count[16],h102_send_count[16],h102_fini,h102_completion_locks,h102_recv_locks;
static bool h102_masked,h102_joined,h102_irq_done,h102_reg_flushed,h102_deregistered,h102_proc_removed;
static bool h102_start,h102_ready,h102_finish;
static pthread_t h102_thread;
static pthread_mutex_t h102_mutex=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t h102_cond=PTHREAD_COND_INITIALIZER;
static struct hif_ipci_softc h102_ipci;
static struct CE_state h102_states[16];
static struct CE_handle h102_handles[16];
static int h102_device;
static bool h102_started(void) {return !!(h102_flags&8);}
static bool h102_diag(void) {return !!(h102_flags&16);}
static bool h102_timer_enabled(void) {return !!(h102_flags&32);}
static bool h102_proc_enabled(void) {return !!(h102_flags&64);}
static bool h102_nss_enabled(void) {return !!(h102_flags&128);}
static unsigned h102_count(void) {return h102_flags&4?16:6;}
static bool h102_skip(unsigned i) {return h102_nss_enabled() && (i==4 || i==5);}
static void *h102_producer(void *unused) {
 assert(!pthread_mutex_lock(&h102_mutex));while(!h102_start){assert(!pthread_cond_wait(&h102_cond,&h102_mutex));}
 h102_ready=true;assert(!pthread_cond_broadcast(&h102_cond));while(!h102_finish){assert(!pthread_cond_wait(&h102_cond,&h102_mutex));}assert(!pthread_mutex_unlock(&h102_mutex));
 struct h99_nbuf b;uint8_t mac[6]={0};h99_build(&b,h99_v2?0x1f:0x04,42,7,0,0,mac,h99_v2?20:4,h99_unaligned);h99_expected_calls=1;
 HTC_PACKET pkt={.pPktContext=&b,.Status=QDF_STATUS_SUCCESS};h100_deliver(&pkt);
 assert(!b.live && h99_frees==1 && h99_calls==1 && !h101_released && "EXPECTED_INFLIGHT_MESSAGE_BEFORE_CONTEXT_RELEASE");return NULL;
}
static struct hif_ipci_softc *h102_get_ipci(struct hif_softc *s) {assert(s==&h101_hif);return &h102_ipci;}
static void h102_exec_kill(struct hif_opaque_softc *o) {
 assert(o==&h101_hif.osc && !h102_irq_step && !h101_released && "EXPECTED_EXEC_DRAIN_FIRST");
 assert(!pthread_mutex_lock(&h102_mutex));h102_start=true;assert(!pthread_cond_broadcast(&h102_cond));while(!h102_ready){assert(!pthread_cond_wait(&h102_cond,&h102_mutex));}assert(!pthread_mutex_unlock(&h102_mutex));h102_irq_step=1;
}
static void h102_nointrs(struct hif_softc *s) {assert(s==&h101_hif && h102_irq_step==1 && !h102_masked && "EXPECTED_MASK_AFTER_EXEC_DRAIN");h102_masked=true;h102_irq_step=2;}
static void h102_ce_tasklet_kill(struct hif_softc *s) {
 assert(s==&h101_hif && h102_irq_step==2 && h102_masked && !h102_joined && "EXPECTED_CE_JOIN_AFTER_MASK");
 assert(!pthread_mutex_lock(&h102_mutex));h102_finish=true;assert(!pthread_cond_broadcast(&h102_cond));assert(!pthread_mutex_unlock(&h102_mutex));assert(!pthread_join(h102_thread,NULL));h102_joined=true;h102_irq_step=3;
 assert(h100_dispatches==1 && h99_calls==1 && h99_frees==1 && "EXPECTED_CALLBACK_DRAIN_BEFORE_CLEANUP");
}
static void h102_tasklet_kill(int *tasklet) {assert(tasklet==&h102_ipci.intr_tq && h102_irq_step==3 && h102_joined && "EXPECTED_INTR_TASKLET_AFTER_CE_JOIN");h102_irq_step=4;}
static void h102_atomic_set(int *p,int n) {
 assert(!n);
 if(p==&h101_hif.active_tasklet_cnt){assert(h102_irq_step==4 && "EXPECTED_TASKLET_COUNTER_AFTER_DRAIN");h102_irq_step=5;}
 else if(p==&h101_hif.active_grp_tasklet_cnt){assert(h102_irq_step==5 && "EXPECTED_GROUP_COUNTER_AFTER_TASKLET_COUNTER");h102_irq_step=6;h102_irq_done=true;}
 else {assert(p==&h101_hif.active_oom_work_cnt && h102_irq_step==6 && h102_oom==h102_count()-1 && "EXPECTED_ALL_OOM_WORK_DESTROYED");h102_irq_step=7;}
 *p=n;
}
static void h102_destroy_work(void *dev,struct h102_work *work) {assert(dev==&h102_device && h102_irq_done && h102_joined && h102_irq_step==6 && h101_hif.hif_init_done && !work->destroyed && "EXPECTED_OOM_AFTER_IRQ_DRAIN");work->destroyed=true;h102_oom++;}
static void h102_proc_remove(void) {assert(h102_irq_step==7 && !h101_hif.hif_init_done && h101_hif.athdiag_procfs_inited && !h102_proc_removed && "EXPECTED_CE_CLEANUP_AFTER_DRAIN");h102_proc_removed=true;}
static bool h102_nss(struct hif_softc *s) {assert(s==&h101_hif && h102_irq_step==7 && !s->hif_init_done && !s->athdiag_procfs_inited && "EXPECTED_CE_CLEANUP_AFTER_DRAIN");return h102_nss_enabled();}
static unsigned h102_pipe_index(struct HIF_CE_pipe_info *p) {assert(p>=h101_hif.ce.pipe_info && p<h101_hif.ce.pipe_info+h102_count());return p-h101_hif.ce.pipe_info;}
static void h102_recv_cleanup(struct HIF_CE_pipe_info *p) {unsigned i=h102_pipe_index(p);assert(!h102_skip(i) && "EXPECTED_NSS_BUFFER_OWNERSHIP");assert(h102_irq_done && h102_joined && !h101_hif.hif_init_done && !h102_recv_count[i] && !h102_send_count[i] && "EXPECTED_BUFFER_CLEANUP_AFTER_PRODUCER_DRAIN");h102_recv_count[i]++;}
static void h102_send_cleanup(struct HIF_CE_pipe_info *p) {unsigned i=h102_pipe_index(p);assert(h102_recv_count[i]==1 && !h102_send_count[i]);h102_send_count[i]++;}
static void h102_flush_reg(struct hif_softc *s) {assert(s==&h101_hif && !h102_reg_flushed);for(unsigned i=0;i<h102_count();i++){assert(h102_recv_count[i]==(unsigned)!h102_skip(i) && h102_send_count[i]==(unsigned)!h102_skip(i) && "EXPECTED_ALL_BUFFER_PIPES_CLEANED");}h102_reg_flushed=true;}
static void h102_lock_destroy(struct h102_lock *lock) {
 assert(h102_reg_flushed && h102_joined && !lock->destroyed && "EXPECTED_CE_FINALIZE_AFTER_REG_FLUSH");unsigned i=lock->id;struct HIF_CE_pipe_info *p=&h101_hif.ce.pipe_info[i];
 if(lock->kind==0){assert(h102_started() && (!h102_diag() || i!=0) && h101_hif.ce.host_ce_config[i].src_nentries && p->ce_hdl==&h102_handles[i] && h102_handles[i].live);h102_completion_locks++;}
 else {assert(lock->kind==1 && !p->ce_hdl && !p->buf_sz && !h102_handles[i].live && "EXPECTED_CE_HANDLE_AND_SIZE_CLEARED");h102_recv_locks++;}lock->destroyed=true;
}
static void h102_ce_fini(struct CE_handle *h) {assert(h102_reg_flushed && h102_joined && h->live && "EXPECTED_CE_FINALIZE_AFTER_REG_FLUSH");unsigned i=h->id;bool completion=h102_started() && (!h102_diag() || i!=0) && h101_hif.ce.host_ce_config[i].src_nentries;assert(h101_hif.ce.pipe_info[i].completion_freeq_lock.destroyed==completion);h->live=false;h102_fini++;}
static void h102_rx_deregister(struct hif_softc *s) {assert(s==&h101_hif && h102_fini==h102_count()-1 && h102_recv_locks==h102_fini && !h102_deregistered && "EXPECTED_ALL_CE_HANDLES_FINALIZED");for(unsigned i=0;i<h102_count();i++){if(i!=3){assert(!s->ce.pipe_info[i].ce_hdl && !s->ce.pipe_info[i].buf_sz);}else{assert(!s->ce.pipe_info[i].ce_hdl && s->ce.pipe_info[i].buf_sz==36);}}h102_deregistered=true;}
static void h102_timer_stop_fn(struct h102_timer *t) {assert(t==&h101_hif.ce.sleep_timer && h102_deregistered && h102_timer_enabled() && !t->stopped && !t->freed && "EXPECTED_SLEEP_TIMER_AFTER_RX_DEREGISTER");t->stopped=true;}
static void h102_timer_free_fn(struct h102_timer *t) {assert(t==&h101_hif.ce.sleep_timer && t->stopped && !t->freed && "EXPECTED_SLEEP_TIMER_STOP_BEFORE_FREE");t->freed=true;}
NATIVE_IPCI
NATIVE_DISABLE
NATIVE_OOM
NATIVE_BUFFERS
NATIVE_STOP
static void h102_prepare(void) {
 struct hif_softc *s=&h101_hif;s->ce_count=h102_count();s->qdf_dev=&h102_device;s->hif_init_done=true;s->athdiag_procfs_inited=h102_proc_enabled();s->active_tasklet_cnt=3;s->active_grp_tasklet_cnt=2;s->active_oom_work_cnt=s->ce_count-1;s->bus_ops.h102_disable_isr=h102_ipci_disable;
 s->ce.started=h102_started();s->ce.sleep_timer_init=h102_timer_enabled();s->ce.ce_diag=h102_diag()?&h102_handles[0]:NULL;
 for(unsigned i=0;i<h102_count();i++){struct HIF_CE_pipe_info *p=&s->ce.pipe_info[i];p->ce_hdl=i==3?NULL:&h102_handles[i];p->buf_sz=36;p->pipe_num=i;p->completion_freeq_lock=(struct h102_lock){.id=i,.kind=0};p->recv_bufs_needed_lock=(struct h102_lock){.id=i,.kind=1};h102_handles[i]=(struct CE_handle){.id=i,.live=i!=3};s->ce.host_ce_config[i].src_nentries=(i%2)?0:16;h102_states[i].oom_allocation_work.id=i;h102_states[i].htt_tx_data=i==4;h102_states[i].htt_rx_data=i==5;s->ce_id_to_state[i]=i==1?NULL:&h102_states[i];}
 assert(!pthread_create(&h102_thread,NULL,h102_producer,NULL));
}
static void h102_stop_bridge(struct hif_softc *s) {
 assert(s==&h101_hif && h101_stopping && h101_tx==ENDPOINT_MAX && h101_rx==ENDPOINT_MAX && h101_timer_stop==h101_expected_timers && h101_timer_free==h101_expected_timers && !h101_closed && !h101_reset && "EXPECTED_HTC_FLUSH_BEFORE_NATIVE_CE_STOP");
 h102_ce_stop(s);
 assert(h102_irq_done && h102_joined && h102_masked && h102_irq_step==7 && h102_deregistered && h102_proc_removed==h102_proc_enabled() && !s->hif_init_done && !s->athdiag_procfs_inited && !s->ce.started && !s->ce.sleep_timer_init && "EXPECTED_NATIVE_CE_STOP_FLAGS");
 assert(s->ce.sleep_timer.stopped==h102_timer_enabled() && s->ce.sleep_timer.freed==h102_timer_enabled() && !s->active_tasklet_cnt && !s->active_grp_tasklet_cnt && !s->active_oom_work_cnt);
 unsigned expected=0;for(unsigned i=0;i<h102_count();i++){if(i!=3 && h102_started() && (!h102_diag() || i!=0) && s->ce.host_ce_config[i].src_nentries){expected++;}}assert(h102_completion_locks==expected);
 h101_closed=true;h101_stop_calls++;
}
static void h102_case(unsigned flags) {h102_flags=flags;h102_enabled=true;h101_stop_contract(flags&1,flags&2,flags&8,flags&16,flags&4);assert(h102_joined && h102_masked && h101_released && !h101_model_late_attempt());}
static void h102_contracts(void) {
 unsigned count=0;for(unsigned flags=0;flags<256;flags++){pid_t c=fork();assert(c>=0);if(!c){h102_case(flags);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;}assert(count==256);
}
'''
def fixture(root):
    s,exits,stubbed=previous.fixture(root)
    s=owner.replace_once(s,'struct hif_opaque_softc {int status;};','/* HIF model definition moved before native transport models. */')
    s=owner.replace_once(s,'struct HIF_CE_pipe_info {',TYPES+'\nstruct HIF_CE_pipe_info {struct CE_handle *ce_hdl;struct h102_lock completion_freeq_lock,recv_bufs_needed_lock;')
    s=owner.replace_once(s,'struct HIF_CE_state {','struct HIF_CE_state {bool started,sleep_timer_init;struct h102_timer sleep_timer;struct CE_handle *ce_diag;struct CE_attr host_ce_config[16];')
    s=owner.replace_once(s,'struct hif_softc {','struct hif_softc {struct hif_opaque_softc osc;uint8_t ce_count;void *qdf_dev;bool hif_init_done,athdiag_procfs_inited;int active_tasklet_cnt,active_grp_tasklet_cnt,active_oom_work_cnt;struct CE_state *ce_id_to_state[16];')
    s=owner.replace_once(s,'void (*h101_bus_stop)(struct hif_softc *);','void (*h101_bus_stop)(struct hif_softc *);void (*h102_disable_isr)(struct hif_softc *);')
    s=owner.replace_once(s,'static struct hif_softc h101_hif;','static struct hif_softc h101_hif;\nstatic bool h102_enabled;\nstatic void h102_prepare(void);\nstatic void h102_stop_bridge(struct hif_softc *);')
    s=owner.replace_once(s,'opaque==&h100_hif_token || opaque==&h101_bus_token','opaque==&h100_hif_token || opaque==&h101_bus_token || opaque==&h101_hif.osc || opaque==&h101_hif.ce')
    body=function(s,'h101_model_bus_stop');s=owner.replace_once(s,body,body.replace('{','{\n if(h102_enabled){h102_stop_bridge(s);return;}',1))
    body=function(s,'h101_stop_contract');s=owner.replace_once(s,body,owner.replace_once(body,'if(sg){h101_stop_on','if(h102_enabled){h102_prepare();}\n if(sg){h101_stop_on'))
    block=SUPPORT
    wrappers={
      'NATIVE_IPCI':(IPCI,'hif_ipci_disable_isr',{'hif_ipci_disable_isr':'h102_ipci_disable','HIF_GET_IPCI_SOFTC':'h102_get_ipci','hif_exec_kill':'h102_exec_kill','hif_nointrs':'h102_nointrs','ce_tasklet_kill':'h102_ce_tasklet_kill','tasklet_kill':'h102_tasklet_kill','qdf_atomic_set':'h102_atomic_set'}),
      'NATIVE_DISABLE':(BUS,'hif_disable_isr',{'hif_disable_isr':'h102_disable_isr','HIF_GET_SOFTC':'h101_softc'}),
      'NATIVE_OOM':(CE,'hif_destroy_oom_work',{'hif_destroy_oom_work':'h102_destroy_oom','qdf_destroy_work':'h102_destroy_work','qdf_atomic_set':'h102_atomic_set'}),
      'NATIVE_BUFFERS':(CE,'hif_buffer_cleanup',{'hif_buffer_cleanup':'h102_buffer_cleanup','HIF_GET_SOFTC':'h101_softc','hif_is_nss_wifi_enabled':'h102_nss','hif_recv_buffer_cleanup_on_pipe':'h102_recv_cleanup','hif_send_buffer_cleanup_on_pipe':'h102_send_cleanup'}),
      'NATIVE_STOP':(CE,'hif_ce_stop',{'hif_ce_stop':'h102_ce_stop','HIF_GET_CE_STATE':'h101_ce','hif_disable_isr':'h102_disable_isr','hif_destroy_oom_work':'h102_destroy_oom','athdiag_procfs_remove':'h102_proc_remove','hif_buffer_cleanup':'h102_buffer_cleanup','hif_flush_delayed_reg_write_work':'h102_flush_reg','qdf_spinlock_destroy':'h102_lock_destroy','ce_fini':'h102_ce_fini','hif_ce_rx_wbuff_deregister':'h102_rx_deregister','qdf_timer_stop':'h102_timer_stop_fn','qdf_timer_free':'h102_timer_free_fn'})}
    for token,(path,name,mapping) in wrappers.items():block=block.replace('\n'+token+'\n','\n'+previous.scoped(native(root,path,name),mapping)+'\n')
    anchor=function(s,'h101_contracts');s=owner.replace_once(s,anchor,anchor+'\n'+block)
    main=function(s,'main');s=owner.replace_once(s,main,owner.replace_once(main,'h101_contracts();','h101_contracts();h102_contracts();'))
    for path,name in NAMES:assert s.count(native(root,path,name))==1
    binding=(root/BINDING).read_text();assert 'bus_ops->hif_stop = &hif_ce_stop;' in binding and 'bus_ops->hif_disable_isr = &hif_ipci_disable_isr;' in binding
    return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    old,*_=previous.fixture(root);previous.negative_controls(directory,c_file,command,env,old,root);exe=directory/'engine'
    controls=[
      (CE,'hif_ce_stop','hif_disable_isr(&scn->osc);','/* omit native disable */','EXPECTED_OOM_AFTER_IRQ_DRAIN'),
      (IPCI,'hif_ipci_disable_isr','hif_exec_kill(&scn->osc);','/* omit exec drain */','EXPECTED_MASK_AFTER_EXEC_DRAIN'),
      (IPCI,'hif_ipci_disable_isr','hif_nointrs(scn);','/* omit mask */','EXPECTED_CE_JOIN_AFTER_MASK'),
      (IPCI,'hif_ipci_disable_isr','ce_tasklet_kill(scn);','/* omit join */','EXPECTED_INTR_TASKLET_AFTER_CE_JOIN'),
      (IPCI,'hif_ipci_disable_isr','tasklet_kill(&sc->intr_tq);','(void)sc; /* omit intr tasklet */','EXPECTED_TASKLET_COUNTER_AFTER_DRAIN'),
      (IPCI,'hif_ipci_disable_isr','qdf_atomic_set(&scn->active_tasklet_cnt, 0);','/* omit counter */','EXPECTED_GROUP_COUNTER_AFTER_TASKLET_COUNTER'),
      (CE,'hif_destroy_oom_work','qdf_destroy_work(scn->qdf_dev,\n\t\t\t\t\t &ce_state->oom_allocation_work);','(void)ce_state;','EXPECTED_ALL_OOM_WORK_DESTROYED'),
      (CE,'hif_ce_stop','scn->hif_init_done = false;','/* omit init flag clear */','EXPECTED_CE_CLEANUP_AFTER_DRAIN'),
      (CE,'hif_ce_stop','hif_buffer_cleanup(hif_state);','/* omit buffers */','EXPECTED_ALL_BUFFER_PIPES_CLEANED'),
      (CE,'hif_ce_stop','hif_flush_delayed_reg_write_work(scn);','/* omit register work */','EXPECTED_CE_FINALIZE_AFTER_REG_FLUSH'),
      (CE,'hif_ce_stop','pipe_info->ce_hdl = NULL;','/* retain stale handle */','EXPECTED_CE_HANDLE_AND_SIZE_CLEARED'),
      (CE,'hif_ce_stop','pipe_info->buf_sz = 0;','/* retain stale size */','EXPECTED_CE_HANDLE_AND_SIZE_CLEARED'),
      (CE,'hif_ce_stop','hif_ce_rx_wbuff_deregister(scn);','/* omit deregister */','EXPECTED_SLEEP_TIMER_AFTER_RX_DEREGISTER'),
      (CE,'hif_ce_stop','qdf_timer_stop(&hif_state->sleep_timer);','/* omit timer stop */','EXPECTED_SLEEP_TIMER_STOP_BEFORE_FREE'),
      (CE,'hif_buffer_cleanup','continue;','(void)ce_state; /* omit NSS ownership gate */','EXPECTED_NSS_BUFFER_OWNERSHIP'),
      (CE,'hif_ce_stop','hif_state->started = false;','/* omit final stop flag */','EXPECTED_NATIVE_CE_STOP_FLAGS')]
    for path,name,needle,mutation,marker in controls:
        target=owner.replace_once(source,function(source,'main'),'int main(void) {h102_case(255);_Exit(0);}')
        body=native(root,path,name);c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(name,needle,bad.returncode,bad.stderr[-1200:])

def audit(root):
    r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_CE_STOP_FIXTURE_PASS_ONLY'
    r['native_function_sha256']={n:hashlib.sha256(native(root,p,n).encode()).hexdigest() for p,n in NAMES};r['source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [CE,BUS,IPCI,BINDING]}
    r['additional_composite_cases']=192;r['inherited_callback_contract_cases']=64;r['inherited_parser_contract_cases']=303;r['inherited_stop_contract_cases']=32;r['inherited_CE_length_contract_cases']=8;r['CE_stop_contract_cases']=256;r['negative_controls_rejected']=110
    r['checks']=['Five original native bodies execute through HTC stop, native multibus stop, original CE stop, original ISR delegate and original IPCI disable ISR','256 controlled producer contracts cover SG, WDI, 6/16 pipes, started/unstarted, diagnostic pipe, sleep timer, procfs and NSS ownership branches; format and alignment follow selected dimensions','Original OOM loop skips null CE state; original buffer loop respects modeled NSS ownership; original CE stop clears live handles and sizes, applies completion/receive lock policy and stops/frees sleep timer','A real host pthread delivers one admitted unmap through native callbacks and is joined by the modeled tasklet-kill primitive before native cleanup; 16 new mutations and 94 independent prior controls rejected','Source IPCI bus bindings reviewed, but bus ops initialization and physical primitive synchronization remain modeled']
    r['limitations']='No new production patch. Native control flow runs against model layouts, interrupts, tasklets, work destruction, residual send/receive buffer endpoints, locks, CE finalization and timers. Real pthread scheduling is deterministic and joins at a modeled primitive, not real kernel interrupt/tasklet/DMA synchronization or TSan coverage. The NSS on/off and 6/16 pipe configurations are selected host cases, not phone feature certification. Full receive/send cleanup bodies, CE ring teardown, physical HTT storage free and production parent shutdown coordinator remain unexecuted. Callback/context pointers are retained; post-stop producer admission remains a model contract. No backend activation, active SSR, phone/RF or AirDrop validation.'
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
