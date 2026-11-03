#!/usr/bin/env python3
"""Actions-only native HIF publication/CE receive and HTC stop ordering."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
import mishare_native_htt_callbacks_fixture as previous
owner=previous.owner
engine=previous.engine
function=previous.function
HIF='qca-wifi-host-cmn/hif/src/hif_main.c'
CE='qca-wifi-host-cmn/hif/src/ce/ce_main.c'
BUS='qca-wifi-host-cmn/hif/src/dispatcher/multibus.c'
HTC='qca-wifi-host-cmn/htc/htc.c'
def native(root,path,name):
    text=(root/path).read_text()
    pattern=r'(?:static\s+inline\s+|static\s+)?void\s+'+name+r'\s*\([^;{]+\)\s*\{.*?^\}'
    return re.search(pattern,text,re.S|re.M)[0]
NAMES=[(HIF,'hif_update_pipe_callback'),(CE,'hif_ce_do_recv'),(BUS,'hif_stop'),(HTC,'htc_stop'),(HTC,'reset_endpoint_states')]
SUPPORT=r'''
/* Model layouts and lower services; source-extracted functions appear below. */
typedef uint8_t u_int8_t;
struct HIF_CE_pipe_info {struct hif_msg_callbacks pipe_callbacks;int buf_sz;uint8_t pipe_num;};
struct HIF_CE_state {struct HIF_CE_pipe_info pipe_info[16];};
struct hif_softc {struct HIF_CE_state ce;struct {void (*h101_bus_stop)(struct hif_softc *);} bus_ops;};
struct hif_opaque_softc;
static struct hif_softc h101_hif;
static bool h101_enabled,h101_closed,h101_stopping,h101_reset,h101_released,h101_sg;
static unsigned h101_copy,h101_setlen,h101_oversize,h101_stop_calls,h101_reset_calls,h101_rx,h101_tx,h101_lookup,h101_timer_stop,h101_timer_free,h101_sg_frees,h101_queue_init;
static unsigned h101_expected_timers,h101_expected_lookup;
static int h101_bus_token;
static void h101_model_bus_stop(struct hif_softc *);
static struct hif_softc *h101_softc(void *opaque) {assert(opaque==&h100_hif_token || opaque==&h101_bus_token);return &h101_hif;}
static struct HIF_CE_state *h101_ce(struct hif_softc *s) {assert(s==&h101_hif);return &s->ce;}
static void h101_bug(bool ok) {assert(ok && "EXPECTED_NATIVE_PIPE_BOUND");}
static void h101_memcopy(void *dst,const void *src,size_t size) {
 assert(dst==&h101_hif.ce.pipe_info[5].pipe_callbacks && size==sizeof(struct hif_msg_callbacks) && "EXPECTED_NATIVE_PIPE_PUBLICATION");h101_copy++;memcpy(dst,src,size);
}
static void h101_pktlen(qdf_nbuf_t b,int len) {assert(b==h99_current && b->live && len>=0 && (unsigned)len<=b->len && "EXPECTED_CE_CAPACITY");b->len=len;h101_setlen++;}
static void h101_bad_len_free(qdf_nbuf_t b) {assert(!h101_setlen && !h100_dispatches && "EXPECTED_OVERSIZE_NO_CALLBACK");h101_oversize++;h99_free(b);}
NATIVE_HIF
NATIVE_CE
NATIVE_BUS
static void h101_publish(void *opaque,uint8_t pipe,struct hif_msg_callbacks *callbacks) {
 h101_hif.bus_ops.h101_bus_stop=h101_model_bus_stop;h101_store(opaque,pipe,callbacks);
 assert(h101_copy==1 && h101_hif.ce.pipe_info[5].pipe_callbacks.rxCompletionHandler==callbacks->rxCompletionHandler && h101_hif.ce.pipe_info[5].pipe_callbacks.Context==callbacks->Context && "EXPECTED_NATIVE_SAVED_CALLBACK");
}
static void h101_receive(qdf_nbuf_t b) {
 struct HIF_CE_pipe_info *p=&h101_hif.ce.pipe_info[5];p->pipe_num=5;p->buf_sz=36;
 unsigned before=h101_setlen;h101_recv(&p->pipe_callbacks,b,b->len,p);
 assert(h101_setlen==before+1 && "EXPECTED_NATIVE_CE_PACKET_LENGTH");
}
typedef struct {unsigned initialized;} h101_queue;
typedef struct {unsigned stopped,freed;} h101_timer;
typedef struct h101_target HTC_TARGET;
typedef struct {unsigned service_id,MaxMsgLength,MaxTxQueueDepth,Id;bool ul_is_polled,TxCreditFlowEnabled;h101_timer ul_poll_timer;h101_queue TxQueue,TxLookupQueue,RxBufferHoldQueue;HTC_TARGET *target;unsigned num_requeues_warn,total_num_requeues;int TxProcessCount;} HTC_ENDPOINT;
typedef struct {qdf_nbuf_t items[2];unsigned count;} qdf_nbuf_queue_t;
struct h101_target {HTC_ENDPOINT endpoint[ENDPOINT_MAX];void *hif_dev;qdf_nbuf_queue_t RxSgQueue;};
static HTC_TARGET h101_target;
static bool htc_credit_flow=true;
static struct h99_nbuf h101_sg_buffers[2];
static bool h101_rxlock;
static void h101_pm(HTC_TARGET *t) {assert(t==&h101_target && !h101_stop_calls && !h101_rx);h101_stopping=true;}
static unsigned h101_index(HTC_TARGET *t,HTC_ENDPOINT *e) {assert(t==&h101_target && e>=t->endpoint && e<t->endpoint+ENDPOINT_MAX);return e-t->endpoint;}
static void h101_flush_rx(HTC_TARGET *t,HTC_ENDPOINT *e) {unsigned i=h101_index(t,e);assert(h101_stopping && !h101_stop_calls && h101_rx==i && h101_tx==i && "EXPECTED_RX_TX_FLUSH_ORDER");h101_rx++;}
static void h101_flush_tx(HTC_TARGET *t,HTC_ENDPOINT *e,unsigned tag) {unsigned i=h101_index(t,e);assert(tag==0 && h101_rx==i+1 && h101_tx==i && !h101_stop_calls && "EXPECTED_ALL_TX_BEFORE_HIF_STOP");h101_tx++;}
static void h101_timer_stop_fn(h101_timer *timer) {assert(!timer->stopped && !timer->freed && !h101_stop_calls);timer->stopped=1;h101_timer_stop++;}
static void h101_timer_free_fn(h101_timer *timer) {assert(timer->stopped && !timer->freed && !h101_stop_calls && "EXPECTED_TIMER_STOP_BEFORE_FREE");timer->freed=1;h101_timer_free++;}
static void h101_lookup_fn(HTC_TARGET *t,int index,bool force) {
 assert(t==&h101_target && h101_closed && h101_stop_calls==1 && !h101_reset && "EXPECTED_LOOKUP_AFTER_HIF_STOP");
 unsigned service=t->endpoint[index].service_id;
 assert(((service==WMI_CONTROL_SVC && !force) || ((service==HTC_CTRL_RSVD_SVC || (service==HTT_DATA_MSG_SVC && !t->endpoint[index].ul_is_polled)) && force)) && "EXPECTED_NATIVE_LOOKUP_POLICY");h101_lookup++;
}
static void h101_queue_init_fn(h101_queue *q) {assert(h101_closed && h101_lookup==h101_expected_lookup && !q->initialized && "EXPECTED_RESET_AFTER_LOOKUP");q->initialized=1;h101_queue_init++;}
static void h101_atomic_init(int *p) {*p=0;}
static void h101_lock(HTC_TARGET *t) {assert(t==&h101_target && h101_closed && !h101_rxlock);h101_rxlock=true;}
static void h101_unlock(HTC_TARGET *t) {assert(t==&h101_target && h101_rxlock && !t->RxSgQueue.count);h101_rxlock=false;}
static qdf_nbuf_t h101_remove(qdf_nbuf_queue_t *q) {assert(q==&h101_target.RxSgQueue && h101_rxlock);return q->count?q->items[--q->count]:NULL;}
static void h101_sg_free(qdf_nbuf_t b) {assert(h101_rxlock && b>=h101_sg_buffers && b<h101_sg_buffers+2 && b->live);b->live=false;h101_sg_frees++;}
static void h101_sg_reset(HTC_TARGET *t) {assert(t==&h101_target && h101_rxlock && h101_sg_frees==2);}
NATIVE_RESET
static void h101_reset_fn(HTC_TARGET *t) {
 assert(h101_closed && !h101_reset && h101_lookup==h101_expected_lookup && h101_sg_frees==(h101_sg?2u:0u) && "EXPECTED_STOP_BEFORE_ENDPOINT_RESET");
 h101_reset_native(t);h101_reset=true;h101_reset_calls++;
}
NATIVE_STOP_OFF
NATIVE_STOP_ON
static void h101_model_bus_stop(struct hif_softc *s) {
 assert(s==&h101_hif && h101_stopping && h101_tx==ENDPOINT_MAX && h101_rx==ENDPOINT_MAX && h101_timer_stop==h101_expected_timers && h101_timer_free==h101_expected_timers && !h101_closed && !h101_reset && "EXPECTED_FLUSH_TIMERS_BEFORE_BUS_STOP");
 /* Model a final admitted producer while HTT storage remains alive. */
 assert(!h101_released);struct h99_nbuf b;uint8_t mac[6]={0};h99_build(&b,h99_v2?0x1f:0x04,42,7,0,0,mac,h99_v2?20:4,h99_unaligned);h99_expected_calls=1;HTC_PACKET pkt={.pPktContext=&b,.Status=QDF_STATUS_SUCCESS};h100_deliver(&pkt);
 assert(!b.live && h99_frees==1 && h99_calls==1 && "EXPECTED_ADMITTED_MESSAGE_BEFORE_RELEASE");
 /* This admission barrier is a model assumption, not a native bus proof. */
 h101_closed=true;h101_stop_calls++;
}
static bool h101_model_late_attempt(void) {if(h101_closed)return false;assert(!h101_released && "EXPECTED_NO_PRODUCER_AFTER_RELEASE");return true;}
static void h101_stop_contract(bool sg,bool wdi,bool polled,bool v2,bool offset) {
 h101_enabled=h100_enabled=h99_probe=true;h101_sg=sg;h100_wdi=wdi;h100_hp=wdi;h99_v2=v2;h99_unaligned=offset;h100_ensure();
 memset(&h101_target,0,sizeof(h101_target));h101_target.hif_dev=&h101_bus_token;h101_hif.bus_ops.h101_bus_stop=h101_model_bus_stop;
 for(unsigned i=0;i<ENDPOINT_MAX;i++){HTC_ENDPOINT *e=&h101_target.endpoint[i];e->service_id=i==0?HTC_CTRL_RSVD_SVC:i==1?WMI_CONTROL_SVC:i==2?HTT_DATA_MSG_SVC:i==3?HTT_DATA_MSG_SVC:0;e->ul_is_polled=(i==2?polled:i==3);e->MaxMsgLength=e->MaxTxQueueDepth=e->num_requeues_warn=e->total_num_requeues=9;e->TxProcessCount=9;h101_expected_timers+=e->ul_is_polled;}
 h101_expected_lookup=polled?2:3;
 if(sg){h101_target.RxSgQueue.count=2;for(unsigned i=0;i<2;i++){h101_sg_buffers[i].live=true;h101_target.RxSgQueue.items[i]=&h101_sg_buffers[i];}}
 if(sg){h101_stop_on(&h101_target);}else{h101_stop_off(&h101_target);}
 assert(h101_stop_calls==1 && h101_closed && h101_reset_calls==1 && h101_queue_init==3*ENDPOINT_MAX && "EXPECTED_NATIVE_STOP_COMPLETE");
 for(unsigned i=0;i<ENDPOINT_MAX;i++){HTC_ENDPOINT *e=&h101_target.endpoint[i];assert(!e->service_id && !e->MaxMsgLength && !e->MaxTxQueueDepth && e->Id==i && e->target==&h101_target && e->TxCreditFlowEnabled && !e->num_requeues_warn && !e->total_num_requeues && !e->TxProcessCount && "EXPECTED_NATIVE_ENDPOINT_RESET");}
 assert(h100_request.EpCallbacks.EpRecv && h100_request.EpCallbacks.pContext==&h99_soc && "EXPECTED_STOP_DOES_NOT_REVOKE_SAVED_POINTERS");
 if(wdi){assert(h101_hif.ce.pipe_info[5].pipe_callbacks.rxCompletionHandler && h101_hif.ce.pipe_info[5].pipe_callbacks.Context==&h99_soc);}
 h101_released=true;unsigned before=h100_dispatches;assert(!h101_model_late_attempt() && h100_dispatches==before && "EXPECTED_MODEL_ADMISSION_CLOSED");
}
static void h101_length_contract(unsigned mode,bool offset) {
 h101_enabled=h100_enabled=h99_probe=true;h100_wdi=h100_hp=true;h100_ensure();
 struct h99_nbuf b;uint8_t mac[6]={0};h99_build(&b,0x1f,42,7,0,0,mac,28,offset);h99_expected_calls=mode==0;
 struct HIF_CE_pipe_info *p=&h101_hif.ce.pipe_info[5];p->buf_sz=28;p->pipe_num=5;
 int bytes=mode==0?20:mode==1?3:mode==2?0:29;
 h100_in_hp=true;h100_pipe_asserts=0;h100_hp_zeroed=false;h100_expected_nbuf=&b;
 h101_recv(&p->pipe_callbacks,&b,bytes,p);
 assert(!b.live && h99_frees==1 && h99_calls==h99_expected_calls && "EXPECTED_CE_LENGTH_OWNERSHIP");
 assert(h101_setlen==(unsigned)(mode!=3) && h101_oversize==(unsigned)(mode==3) && h100_dispatches==(unsigned)(mode!=3) && "EXPECTED_CE_LENGTH_ROUTE");
}
static void h101_contracts(void) {
 unsigned count=0;
 for(unsigned sg=0;sg<2;sg++){for(unsigned wdi=0;wdi<2;wdi++){for(unsigned polled=0;polled<2;polled++){for(unsigned fmt=0;fmt<2;fmt++){for(unsigned off=0;off<2;off++){
  pid_t c=fork();assert(c>=0);if(!c){h101_stop_contract(sg,wdi,polled,fmt,off);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;
 }}}}}
 for(unsigned mode=0;mode<4;mode++){for(unsigned off=0;off<2;off++){
  pid_t c=fork();assert(c>=0);if(!c){h101_length_contract(mode,off);_Exit(0);}int st;assert(waitpid(c,&st,0)==c && WIFEXITED(st) && !WEXITSTATUS(st));count++;
 }}
 assert(count==40);
}
'''
def scoped(body,mapping,pre='',post=''):
    start,end=previous.previous.previous.macros(mapping)
    return start+'\n'+pre+'\n'+body+'\n'+post+'\n'+end
def fixture(root):
    s,exits,stubbed=previous.fixture(root)
    # Constants follow original headers; CE storage uses the QCN9224 16-pipe variant.
    header=(root/'qca-wifi-host-cmn/hif/inc/hif.h').read_text()
    assert '#define CE_COUNT_MAX 16' in header
    services=(root/previous.SERVICES).read_text()
    constants='\n'.join(previous.define(services,n) for n in ['HTC_CTRL_RSVD_SVC','WMI_CONTROL_SVC'])+'\n'+previous.define((root/previous.PACKET).read_text(),'HTC_TX_PACKET_TAG_ALL')
    block=constants+'\n'+SUPPORT
    mapping={'hif_update_pipe_callback':'h101_store','HIF_GET_SOFTC':'h101_softc','HIF_GET_CE_STATE':'h101_ce','QDF_BUG':'h101_bug','hif_debug':'h99_error','qdf_mem_copy':'h101_memcopy','CE_COUNT_MAX':'16'}
    block=block.replace('\nNATIVE_HIF\n','\n'+scoped(native(root,HIF,'hif_update_pipe_callback'),mapping)+'\n')
    block=block.replace('\nNATIVE_CE\n','\n'+scoped(native(root,CE,'hif_ce_do_recv'),{'hif_ce_do_recv':'h101_recv','qdf_nbuf_set_pktlen':'h101_pktlen','hif_err':'h99_error','hif_ce_rx_nbuf_free':'h101_bad_len_free'})+'\n')
    block=block.replace('\nNATIVE_BUS\n','\n'+scoped(native(root,BUS,'hif_stop'),{'HIF_GET_SOFTC':'h101_softc','hif_stop':'h101_bus_stop'})+'\n')
    block=block.replace('\nNATIVE_RESET\n','\n'+scoped(native(root,HTC,'reset_endpoint_states'),{'reset_endpoint_states':'h101_reset_native','INIT_HTC_PACKET_QUEUE':'h101_queue_init_fn','qdf_atomic_init':'h101_atomic_init'})+'\n')
    stopmap={'GET_HTC_TARGET_FROM_HANDLE':'','AR_DEBUG_PRINTF(a,b)':'((void)0)','HTC_INFO(...)':'((void)0)','htc_runtime_pm_deinit':'h101_pm','htc_flush_rx_hold_queue':'h101_flush_rx','htc_flush_endpoint_tx':'h101_flush_tx','qdf_timer_stop':'h101_timer_stop_fn','qdf_timer_free':'h101_timer_free_fn','hif_stop':'h101_bus_stop','htc_flush_endpoint_txlookupQ':'h101_lookup_fn','reset_endpoint_states':'h101_reset_fn','LOCK_HTC_RX':'h101_lock','UNLOCK_HTC_RX':'h101_unlock','qdf_nbuf_queue_remove':'h101_remove','qdf_nbuf_free':'h101_sg_free','RESET_RX_SG_CONFIG':'h101_sg_reset'}
    for sg in [False,True]:
        mapping=dict(stopmap,htc_stop='h101_stop_on' if sg else 'h101_stop_off')
        block=block.replace('\nNATIVE_STOP_'+('ON' if sg else 'OFF')+'\n','\n'+scoped(native(root,HTC,'htc_stop'),mapping,'#pragma push_macro("RX_SG_SUPPORT")\n#undef RX_SG_SUPPORT\n'+('#define RX_SG_SUPPORT' if sg else ''),'#pragma pop_macro("RX_SG_SUPPORT")')+'\n')
    # Defined after 0100 support so its types and helpers are in scope.
    anchor=function(s,'h100_contracts');s=owner.replace_once(s,anchor,anchor+'\n'+block)
    s=owner.replace_once(s,'static bool h100_enabled;','static bool h100_enabled;\nstruct hif_msg_callbacks;\nstatic void h101_publish(void *,uint8_t,struct hif_msg_callbacks *);\nstatic void h101_receive(qdf_nbuf_t);')
    s=owner.replace_once(s,'h100_pipe=*callbacks;','h101_publish(handle,pipe,callbacks);h100_pipe=*callbacks;')
    deliver=function(s,'h100_deliver')
    needle='assert(h100_pipe.rxCompletionHandler(h100_pipe.Context,h100_expected_nbuf,5)==QDF_STATUS_SUCCESS && "EXPECTED_NATIVE_HP_STATUS");'
    # Preserve null-input 0100 edge cases, which invoke the native adapter directly.
    s=owner.replace_once(s,deliver,owner.replace_once(deliver,needle,'h101_receive(h100_expected_nbuf);'))
    main=function(s,'main');s=owner.replace_once(s,main,owner.replace_once(main,'h100_contracts();','h100_contracts();h101_contracts();'))
    for path,name in NAMES:assert s.count(native(root,path,name))==(2 if name=='htc_stop' else 1)
    return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
    # Preserve the preceding independent path for inherited mutations.
    old,*_=previous.fixture(root)
    previous.negative_controls(directory,c_file,command,env,old,root)
    exe=directory/'engine'
    controls=[
      (HIF,'hif_update_pipe_callback','callbacks, sizeof(pipe_info->pipe_callbacks)','callbacks, 0','h101_stop_contract(false,true,false,false,false);','EXPECTED_NATIVE_PIPE_PUBLICATION'),
      (CE,'hif_ce_do_recv','nbytes <= pipe_info->buf_sz','true','h101_length_contract(3,false);','EXPECTED_CE_CAPACITY'),
      (CE,'hif_ce_do_recv','qdf_nbuf_set_pktlen(netbuf, nbytes);','/* missing length */','h101_length_contract(1,false);','EXPECTED_HTT_CALLBACK_BEFORE_NBUF_FREE'),
      (CE,'hif_ce_do_recv','rxCompletionHandler(msg_callbacks->Context,','rxCompletionHandler(NULL,','h101_length_contract(0,false);','EXPECTED_NATIVE_DELIVERY_CONTEXT'),
      (CE,'hif_ce_do_recv','hif_ce_rx_nbuf_free(netbuf);','/* leaked oversize */','h101_length_contract(3,false);','EXPECTED_CE_LENGTH_OWNERSHIP'),
      (BUS,'hif_stop','hif_sc->bus_ops.hif_stop(hif_sc);','/* stop omitted */ (void)hif_sc;','h101_stop_contract(false,true,false,false,false);','EXPECTED_LOOKUP_AFTER_HIF_STOP'),
      (HTC,'htc_stop','htc_flush_endpoint_tx(target, endpoint, HTC_TX_PACKET_TAG_ALL);','/* TX flush omitted */','h101_stop_contract(false,true,false,false,false);','EXPECTED_RX_TX_FLUSH_ORDER'),
      (HTC,'htc_stop','qdf_timer_stop(&endpoint->ul_poll_timer);','/* timer stop omitted */','h101_stop_contract(false,true,false,false,false);','EXPECTED_TIMER_STOP_BEFORE_FREE'),
      (HTC,'htc_stop','hif_stop(target->hif_dev);','reset_endpoint_states(target);\n\thif_stop(target->hif_dev);','h101_stop_contract(false,true,false,false,false);','EXPECTED_STOP_BEFORE_ENDPOINT_RESET'),
      (HTC,'htc_stop','!endpoint->ul_is_polled','endpoint->ul_is_polled','h101_stop_contract(false,true,false,false,false);','EXPECTED_NATIVE_LOOKUP_POLICY'),
      (HTC,'reset_endpoint_states','pEndpoint->service_id = 0;','pEndpoint->service_id = 42;','h101_stop_contract(false,true,false,false,false);','EXPECTED_NATIVE_ENDPOINT_RESET'),
      (HTC,'htc_stop','qdf_nbuf_free(netbuf);','/* SG leak */ (void)netbuf;','h101_stop_contract(true,true,false,false,false);','h101_sg_frees==2'),
    ]
    for path,name,needle,mutation,call,marker in controls:
        target=owner.replace_once(source,function(source,'main'),'int main(void) {'+call+'_Exit(0);}')
        body=native(root,path,name)
        # Two compile-time SG variants share the exact original stop function.
        assert target.count(body)==(2 if name=='htc_stop' else 1)
        target=target.replace(body,owner.replace_once(body,needle,mutation))
        c_file.write_text(target);subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env)
        assert bad.returncode==-6 and marker in bad.stderr,(name,needle,bad.returncode,bad.stderr[-1000:])

def audit(root):
    r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls)
    r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_TRANSPORT_STOP_FIXTURE_PASS_ONLY'
    r['native_function_sha256']={name:hashlib.sha256(native(root,path,name).encode()).hexdigest() for path,name in NAMES}
    r['source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [HIF,CE,BUS,HTC,'qca-wifi-host-cmn/hif/inc/hif.h',previous.SERVICES,previous.PACKET]}
    r['additional_composite_cases']=192;r['inherited_callback_contract_cases']=64;r['inherited_parser_contract_cases']=303
    r['stop_contract_cases']=32;r['CE_length_contract_cases']=8;r['negative_controls_rejected']=94
    r['checks']=['Original HIF callback copy and CE receive route feed original HP adapter and production unmap parser; 192 inherited composite selections retained','Original HTC stop executes both RX_SG_SUPPORT branches, endpoint RX/TX flushes and polled timer order before original multibus HIF stop delegate, then native endpoint reset','32 stop contracts cover SG on/off, WDI on/off, polled/nonpolled HTT lookup policy, v1/v2 and alignment; a final model-admitted message is consumed during lower stop while context is retained','8 CE contracts cover bounded packet length, zero/short unmap and oversize free ownership; 12 new mutations plus 82 prior controls rejected','Retained HTC/HIF callback pointers are explicitly observed after stop; post-stop admission closure and release are model assumptions, not callback revocation']
    r['limitations']='No production patch added. HIF copy uses the source QCN9224 16-pipe bound with modeled layouts, not phone feature selection. Real CE rings, DMA, interrupts, locks, timers, queue flushes and bus stop synchronization are not executed. Lower bus stop is a serial model admission barrier; no real concurrent producer, stale-pointer invocation, registration reentrancy, physical HTT free, production shutdown coordinator, SSR, phone/RF or AirDrop validation. HTC endpoint reset does not clear captured receive callback/context pointers. Native generic dispatcher remains consumed-prefix only. Backend stays disabled.'
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
