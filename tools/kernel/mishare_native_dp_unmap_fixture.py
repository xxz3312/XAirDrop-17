#!/usr/bin/env python3
"""Actions-only pinned DP peer unmap, lookup refs and map removal composite."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import mishare_native_dp_peer_free_fixture as previous
owner=previous.owner
engine=previous.engine
extract=previous.extract
function=previous.function
DP=previous.DP
PEER='qca-wifi-host-cmn/dp/wifi3.0/dp_peer.c'
HEADER='qca-wifi-host-cmn/dp/wifi3.0/dp_peer.h'
NAMES=['dp_rx_peer_unmap_handler','dp_peer_find_id_to_obj_remove','dp_peer_get_ref','__dp_peer_get_ref_by_id']
def native(root,name):
 text=(root/(PEER if name in NAMES[:2] else HEADER)).read_text()
 if name==NAMES[3]:return re.search(r'static inline struct dp_peer \*\s*'+name+r'\([^;{]+\)\s*\{.*?^\}',text,re.S|re.M)[0]
 return extract(text,name)
SUPPORT=r'''
struct cdp_txrx_peer_params_update {uint8_t vdev_id;uint8_t *peer_mac;unsigned chip_id,pdev_id;};
static struct dp_txrx_peer d98_txrx_storage;
static bool d98_txrx,d98_offload,d98_ipa,d98_ol,d98_partner_enabled,d98_probes,d98_wds_probe,d98_ast_missing;
static unsigned d98_step,d98_gets,d98_rejects,d98_map_puts,d98_htt_puts,d98_config_puts,d98_flow,d98_ol_calls,d98_partners,d98_wdi_calls,d98_wds_calls,d98_ipa_calls;
static int d98_cfg_token;
static void d98_map_lock(int *p) {assert(p==&d96_soc.peer_map_lock && !*p);*p=1;}
static void d98_map_unlock(int *p) {assert(p==&d96_soc.peer_map_lock && *p==1);*p=0;}
static bool d98_inc_alive(int *p) {
 assert(d97_peer && p==&d97_peer->ref_cnt && d96_soc.peer_map_lock==1);
 if(!*p){d98_rejects++;return false;}assert(*p>0);++*p;d98_gets++;return true;
}
static void d98_inc(int *p) {assert(d97_peer && p==&d97_peer->mod_refs[DP_MOD_ID_HTT] && d96_soc.peer_map_lock==1);++*p;}
static void d98_map_put(struct dp_peer *p,enum dp_mod_id id) {
 assert(p==d97_peer && id==DP_MOD_ID_CONFIG && d98_step==3 && d96_soc.peer_map_lock==1 && !d96_soc.peer_id_to_obj_map[42] && p->peer_id==HTT_INVALID_PEER && "EXPECTED_UNMAP_MAP_REF_ORDER");
 assert(p->ref_cnt>=3 && "EXPECTED_UNMAP_LOOKUP_PIN_DURING_REMOVE");d98_map_puts++;dp_peer_unref_delete(p,id);
}
HELPER_MACROS
NATIVE_REF
NATIVE_LOOKUP
NATIVE_REMOVE
HELPER_UNMACROS
static void d98_remove(struct dp_soc *s,uint16_t id) {
 assert(s==&d96_soc && id==42 && d98_step==3);
 d98_native_remove(s,id);
 assert(!s->peer_map_lock && !s->peer_id_to_obj_map[id] && d98_map_puts==1 && d97_peer->peer_id==HTT_INVALID_PEER && "EXPECTED_UNMAP_MAP_REMOVAL");
 if(d97_peer->txrx_peer){assert(d97_peer->txrx_peer->peer_id==HTT_INVALID_PEER && "EXPECTED_UNMAP_TXRX_ID_INVALIDATION");}d98_step=4;
}
static struct dp_peer *d98_lookup(struct dp_soc *s,uint16_t id,enum dp_mod_id mod) {assert(s==&d96_soc && mod==DP_MOD_ID_HTT);return __dp_peer_get_ref_by_id(s,id,mod);}
static void d98_wds_clean(struct dp_soc *s,struct dp_peer *p,uint32_t count) {assert(s==&d96_soc && p==d97_peer && count==0 && !d98_step);d98_step=1;}
static void d98_record(struct dp_soc *s,unsigned event,struct dp_peer *p,uint8_t *mac,unsigned a,uint16_t id,unsigned b,unsigned c,uint8_t vdev) {
 assert(s==&d96_soc && event==1 && p==d97_peer && mac && !a && id==42 && !b && !c && vdev==7 && d98_step==1 && "EXPECTED_UNMAP_WDS_BEFORE_RECORD");d98_step=2;
}
static void d98_qref(struct dp_soc *s,struct dp_peer *p) {assert(s==&d96_soc && p==d97_peer && d98_step==2);d98_step=3;}
static void d98_partner(struct dp_soc *s,uint16_t id) {assert(s==&d96_soc && id==42 && d98_step==4);d98_partners++;}
static void d98_reset_flow(struct dp_peer *p) {assert(p==d97_peer && p->peer_id==HTT_INVALID_PEER && d98_step==4 && "EXPECTED_UNMAP_INVALID_ID_BEFORE_FLOW");d98_flow++;}
static bool d98_ipa_enabled(void *cfg) {assert(cfg==&d98_cfg_token);return d98_ipa;}
static void d98_ol_event(void *psoc,uint16_t id,uint8_t vdev,uint8_t *mac) {assert(psoc==d96_soc.ctrl_psoc && id==42 && vdev==7 && mac && d98_step==4);d98_ol_calls++;}
static void d98_vdev_stats(struct dp_vdev *v,struct dp_peer *p) {
 assert(v==d96_vdev && p==d97_peer && d98_step==4 && !d96_soc.peer_id_to_obj_map[42] && p->peer_id==HTT_INVALID_PEER && "EXPECTED_UNMAP_MAP_BEFORE_STATS");
 assert(d98_flow==(unsigned)!d98_offload && d98_partners==(unsigned)d98_partner_enabled && d98_ol_calls==(unsigned)(!d98_ipa && d98_ol) && "EXPECTED_UNMAP_OPTIONAL_CALLBACKS");d98_step=5;
}
static void d98_event(struct dp_soc *s,unsigned event,uint16_t id,uint8_t vdev,uint8_t *mac) {assert(s==&d96_soc && event==2 && id==42 && vdev==7 && mac && d98_step==5 && "EXPECTED_UNMAP_STATS_BEFORE_EVENT");d98_step=6;}
static void d98_state(struct dp_soc *s,struct dp_peer *p,enum dp_peer_state state) {
 assert(s==&d96_soc && p==d97_peer && state==DP_PEER_STATE_INACTIVE && d98_step==6 && "EXPECTED_UNMAP_EVENT_BEFORE_STATE");p->state=state;d98_step=7;
}
static void d98_put(struct dp_peer *p,enum dp_mod_id id) {
 if(d98_wds_probe){assert(id==DP_MOD_ID_HTT && !d98_step);d98_htt_puts++;dp_peer_unref_delete(p,id);return;}
 assert(d98_step==7 && p==d97_peer && p->state==DP_PEER_STATE_INACTIVE && "EXPECTED_UNMAP_INACTIVE_BEFORE_PUT");
 if(id==DP_MOD_ID_HTT){assert(d98_htt_puts==(d98_probes?2u:0u) && !d98_config_puts);d98_htt_puts++;}
 else {assert(id==DP_MOD_ID_CONFIG && d98_htt_puts==(d98_probes?3u:1u) && !d98_config_puts && "EXPECTED_UNMAP_HTT_BEFORE_CONFIG");d98_config_puts++;}
 dp_peer_unref_delete(p,id);
}
static unsigned d98_chip(struct dp_soc *s) {assert(s==&d96_soc);return 0;}
static void d98_wdi(unsigned event,struct dp_soc *s,void *data,uint16_t id,unsigned value,unsigned pdev) {
 struct cdp_txrx_peer_params_update *p=data;assert(event==3 && s==&d96_soc && id==42 && !value && !pdev && p->vdev_id==7 && p->peer_mac==d97_peer->mac_addr.raw && !p->chip_id && !p->pdev_id);d98_wdi_calls++;
}
static bool d98_ast_free(struct dp_soc *s,struct dp_peer *p,uint8_t id,uint8_t *mac) {assert(d98_wds_probe && s==&d96_soc && p==d97_peer && id==7 && mac);d98_wds_calls++;return d98_ast_missing;}
static void d98_ipa_event(struct dp_soc *s,uint16_t id,uint8_t vdev,uint8_t *mac) {assert(d98_wds_probe && s==&d96_soc && id==42 && vdev==7 && mac);d98_ipa_calls++;}
static void d98_sta_cache(struct dp_soc *s,struct dp_vdev *v,bool map) {(void)s;(void)v;(void)map;assert(!"unselected STA branch");}
UNMAP_MACROS
NATIVE_UNMAP
UNMAP_UNMACROS
static void d98_attach(void) {
 struct dp_peer *p=d97_peer;assert(p && !d98_step);p->ref_cnt=2+d97_extra+d97_rx;p->mod_refs[DP_MOD_ID_HTT]=0;p->mod_refs[DP_MOD_ID_CONFIG]=2;p->state=DP_PEER_STATE_LOGICAL_DELETE;
 p->txrx_peer=d98_txrx?&d98_txrx_storage:NULL;d98_txrx_storage.peer_id=42;
 struct dp_soc *s=&d96_soc;s->max_peer_id=64;s->peer_id_to_obj_map[42]=p;s->ast_offload_support=d98_offload;s->host_ast_db_enable=true;s->wlan_cfg_ctx=&d98_cfg_token;
 d98_ol_ops.peer_unmap_event=d98_ol?d98_ol_event:NULL;s->cdp_soc.ol_ops=&d98_ol_ops;s->arch_ops.dp_partner_chips_unmap=d98_partner_enabled?d98_partner:NULL;
}
static void d98_extra_puts(struct dp_peer *p) {
 for(unsigned i=0;i<d97_extra;i++)dp_peer_unref_delete(p,DP_MOD_ID_TX);
 if(d97_rx)dp_peer_unref_delete(p,DP_MOD_ID_RX);
}
static void d98_preflight(uint8_t *mac) {
 struct dp_soc *s=&d96_soc;struct dp_peer *p=d97_peer;int refs=p->ref_cnt;
 dp_rx_peer_unmap_handler(s,43,7,mac,0,0);dp_rx_peer_unmap_handler(s,64,7,mac,0,0);
 assert(s->stats.t2h_msg_stats.invalid_peer_unmap==2 && p->ref_cnt==refs && !d98_gets && !d98_step && "EXPECTED_UNMAP_UNKNOWN_ID_NO_REFERENCE");
 p->ref_cnt=0;assert(!__dp_peer_get_ref_by_id(s,42,DP_MOD_ID_HTT) && d98_rejects==1 && !p->mod_refs[DP_MOD_ID_HTT] && "EXPECTED_UNMAP_ZERO_REF_ADMISSION");p->ref_cnt=refs;
 s->ast_offload_support=true;s->host_ast_db_enable=false;dp_rx_peer_unmap_handler(s,42,7,mac,1,0);assert(!d98_gets && p->ref_cnt==refs);
 s->host_ast_db_enable=true;d98_wds_probe=true;
 for(unsigned missing=0;missing<2;missing++){d98_ast_missing=missing;dp_rx_peer_unmap_handler(s,42,7,mac,1,0);assert(p->ref_cnt==refs && p->peer_id==42 && s->peer_id_to_obj_map[42]==p && !d98_map_puts && !d98_step && !d98_config_puts && "EXPECTED_WDS_RETAINS_CONFIG_AND_MAPPING");}
 d98_wds_probe=false;s->ast_offload_support=d98_offload;assert(d98_wds_calls==2 && d98_ipa_calls==1);
}
static void d98_finish(void) {
 struct dp_peer *p=d97_peer;uint8_t mac[6]={0};assert(p && p->peer_id==42 && d96_vdev && d96_vdev->ref_cnt==1);
 if(d97_reverse)d98_extra_puts(p);
 if(d98_probes)d98_preflight(mac);
 dp_rx_peer_unmap_handler(&d96_soc,42,7,mac,0,0);
 assert(d98_step==7 && d98_map_puts==1 && d98_config_puts==1 && d98_htt_puts==(d98_probes?3u:1u) && d98_gets==(d98_probes?3u:1u) && "EXPECTED_NATIVE_UNMAP_REFERENCE_BALANCE");
 if(!d97_reverse && (d97_extra || d97_rx)){assert(d97_peer==p && p->ref_cnt==(int)(d97_extra+d97_rx) && !d97_frees && !d96_callbacks && "EXPECTED_UNMAP_EXTERNAL_REFS_RETAIN_CHILD");d98_extra_puts(p);}
 assert(!d97_peer && d97_frees==1 && !d96_vdev && d96_callbacks==1 && "EXPECTED_NATIVE_UNMAP_FINAL_FREE");
 dp_rx_peer_unmap_handler(&d96_soc,42,7,mac,0,0);
 assert(d96_soc.stats.t2h_msg_stats.invalid_peer_unmap==(d98_probes?3u:1u) && d96_soc.stats.t2h_msg_stats.peer_unmap==(d98_probes?7u:2u) && d98_wdi_calls==(d98_txrx?(d98_probes?3u:1u):0u) && "EXPECTED_DUPLICATE_UNMAP_NO_DEREFERENCE");
}
'''
HELPERS={
 'QDF_ASSERT':'d97_assert','qdf_spin_lock_bh':'d98_map_lock','qdf_spin_unlock_bh':'d98_map_unlock','qdf_atomic_inc_not_zero':'d98_inc_alive','qdf_atomic_inc':'d98_inc','dp_err':'ref_log','dp_peer_unref_delete':'d98_map_put','dp_peer_find_id_to_obj_remove':'d98_native_remove',
}
UNMAP={
 'DP_STATS_INC(s,f,n)':'((s)->stats.f+=(n))','__dp_peer_get_ref_by_id':'d98_lookup','dp_err':'ref_log','dp_info':'ref_log','dp_alert':'ref_log',
 'dp_get_chip_id':'d98_chip','dp_wdi_event_handler':'d98_wdi','WDI_EVENT_PEER_UNMAP':'3','WDI_NO_VAL':'0',
 'dp_peer_ast_free_entry_by_mac':'d98_ast_free','dp_peer_unmap_ipa_evt':'d98_ipa_event','dp_peer_clean_wds_entries':'d98_wds_clean','dp_cfg_event_record_peer_map_unmap_evt':'d98_record','DP_CFG_EVENT_PEER_UNMAP':'1',
 'dp_peer_rx_reo_shared_qaddr_delete':'d98_qref','dp_tx_cfg_astidx_cache_mapping':'d98_sta_cache','dp_peer_find_id_to_obj_remove':'d98_remove','dp_peer_reset_flowq_map':'d98_reset_flow','wlan_cfg_is_ipa_enabled':'d98_ipa_enabled','dp_update_vdev_stats_on_peer_unmap':'d98_vdev_stats','__dp_peer_event_notify':'d98_event','CDP_PEER_EVENT_UNMAP':'2','dp_peer_update_state':'d98_state','dp_peer_unref_delete':'d98_put','QDF_MAC_ADDR_FMT':'"%p"','QDF_MAC_ADDR_REF(p)':'((void *)(p))',
}
def macros(mapping):
 start=[];end=[]
 for key,value in mapping.items():
  name=key.split('(')[0];start.extend([f'#pragma push_macro("{name}")',f'#undef {name}',f'#define {key} {value}']);end[0:0]=[f'#undef {name}',f'#pragma pop_macro("{name}")']
 return '\n'.join(start),'\n'.join(end)

def fixture(root):
 s,exits,stubbed=previous.fixture(root)
 s=owner.replace_once(s,'struct dp_soc;struct dp_peer;struct dp_pdev {int live;struct dp_soc *soc;};','struct dp_soc;struct dp_peer;struct dp_pdev {int live;struct dp_soc *soc;unsigned pdev_id;};\nstruct dp_txrx_peer {uint16_t peer_id;};\nstruct d98_ol {void (*peer_unmap_event)(void *,uint16_t,uint8_t,uint8_t *);};\nstatic struct d98_ol d98_ol_ops;')
 s=owner.replace_once(s,'struct dp_soc {int inactive_peer_list_lock;','struct dp_soc {unsigned max_peer_id;int peer_map_lock;struct dp_peer *peer_id_to_obj_map[64];bool ast_offload_support,host_ast_db_enable;void *wlan_cfg_ctx;struct {struct {unsigned peer_unmap,invalid_peer_unmap;} t2h_msg_stats;} stats;struct {void (*dp_partner_chips_unmap)(struct dp_soc *,uint16_t);} arch_ops;struct {struct d98_ol *ol_ops;} cdp_soc;int inactive_peer_list_lock;')
 s=owner.replace_once(s,'struct dp_vdev *vdev;uint16_t peer_id;int mod_refs','struct dp_vdev *vdev;uint16_t peer_id;struct dp_txrx_peer *txrx_peer;bool is_tdls_peer;int mod_refs')
 s=owner.replace_once(s,'static void d97_attach(void);','static bool d98_enabled;\nstatic void d98_attach(void);\nstatic void d98_finish(void);\nstatic void d97_attach(void);')
 attach=function(s,'d97_attach');s=owner.replace_once(s,attach,owner.replace_once(attach,'if(!d97_unlisted)d96_soc.inactive_peer_list=p;','if(!d97_unlisted)d96_soc.inactive_peer_list=p;if(d98_enabled)d98_attach();'))
 finish=function(s,'d97_finish');s=owner.replace_once(s,finish,owner.replace_once(finish,'struct dp_peer *p=d97_peer;','if(d98_enabled){d98_finish();return;}\n struct dp_peer *p=d97_peer;'))
 block=SUPPORT
 for mapping,prefix in [(HELPERS,'HELPER'),(UNMAP,'UNMAP')]:
  start,end=macros(mapping);block=block.replace('\n'+prefix+'_MACROS\n','\n'+start+'\n').replace('\n'+prefix+'_UNMACROS\n','\n'+end+'\n')
 for token,name in [('NATIVE_REF',NAMES[2]),('NATIVE_LOOKUP',NAMES[3]),('NATIVE_REMOVE',NAMES[1]),('NATIVE_UNMAP',NAMES[0])]:block=block.replace('\n'+token+'\n','\n'+native(root,name)+'\n')
 check=function(s,'d97_check');s=owner.replace_once(s,check,check+'\n'+block)
 case=function(s,'p92_case');s=owner.replace_once(s,case,owner.replace_once(case,'d96_enabled=true;','d98_enabled=true;d96_enabled=true;'))
 cases=function(s,'p92_cases');extra=r'''
 for(unsigned trace=0;trace<2;trace++)for(unsigned offload=0;offload<2;offload++)for(unsigned ipa=0;ipa<2;ipa++)for(unsigned txrx=0;txrx<2;txrx++)for(unsigned callbacks=0;callbacks<2;callbacks++) {
  pid_t c=fork();assert(c>=0);if(!c){d98_offload=offload;d98_ipa=ipa;d98_txrx=txrx;d98_ol=callbacks;d98_partner_enabled=callbacks;d98_probes=true;d97_extra=2;d97_rx=true;d97_reverse=trace;d96_extra=2;d96_notify_enabled=true;p92_case(trace,1,0,false);_Exit(0);}int status;assert(waitpid(c,&status,0)==c && WIFEXITED(status) && !WEXITSTATUS(status));count++;
 }
 assert(count==152);
'''
 s=owner.replace_once(s,cases,owner.replace_once(cases,'assert(count==120);','assert(count==120);\n'+extra))
 for name in NAMES:assert s.count(native(root,name))==1
 for name in [previous.NAME,previous.previous.NAME]:assert s.count(extract((root/DP).read_text(),name))==1
 return s,exits,stubbed

def negative_controls(directory,c_file,command,env,source,root):
 # The previous stage's tests retain their original modeled unmap setup.
 old=owner.replace_once(source,'d98_enabled=true;','d98_enabled=false;');previous.negative_controls(directory,c_file,command,env,old,root);exe=directory/'engine'
 controls=[
 ('lookup_pin',NAMES[2],'if (!qdf_atomic_inc_not_zero(&peer->ref_cnt))','if (false && !qdf_atomic_inc_not_zero(&peer->ref_cnt))','EXPECTED_UNMAP_LOOKUP_PIN_DURING_REMOVE'),
 ('map_slot',NAMES[1],'soc->peer_id_to_obj_map[peer_id] = NULL;','/* omit map slot clear */','EXPECTED_UNMAP_MAP_REF_ORDER'),
 ('map_ref',NAMES[1],'dp_peer_unref_delete(peer, DP_MOD_ID_CONFIG);','/* omit map CONFIG put */','EXPECTED_UNMAP_MAP_REMOVAL'),
 ('txrx_id',NAMES[1],'peer->txrx_peer->peer_id = HTT_INVALID_PEER;','(void)peer->txrx_peer;','EXPECTED_UNMAP_TXRX_ID_INVALIDATION'),
 ('qref',NAMES[0],'dp_peer_rx_reo_shared_qaddr_delete(soc, peer);','/* omit Qref delete */','d98_step==3'),
 ('flow',NAMES[0],'dp_peer_reset_flowq_map(peer);','(void)peer;','EXPECTED_UNMAP_OPTIONAL_CALLBACKS'),
 ('event',NAMES[0],'__dp_peer_event_notify(soc, CDP_PEER_EVENT_UNMAP, peer_id,\n\t\t\t       peer->vdev->vdev_id, peer->mac_addr.raw);','/* omit event */','EXPECTED_UNMAP_EVENT_BEFORE_STATE'),
 ('state',NAMES[0],'dp_peer_update_state(soc, peer, DP_PEER_STATE_INACTIVE);','/* omit state */','EXPECTED_UNMAP_INACTIVE_BEFORE_PUT'),
 ('htt_put',NAMES[0],'dp_peer_unref_delete(peer, DP_MOD_ID_HTT);\n\t/*','/* omit final HTT put */\n\t/*','EXPECTED_UNMAP_HTT_BEFORE_CONFIG'),
 ('config_put',NAMES[0],'dp_peer_unref_delete(peer, DP_MOD_ID_CONFIG);','/* omit final CONFIG put */','EXPECTED_NATIVE_UNMAP_REFERENCE_BALANCE'),
 ]
 for label,name,needle,mutation,marker in controls:
  target=owner.replace_once(source,function(source,'main'),'int main(void) {d98_txrx=true;p92_case(false,1,0,false);_Exit(0);}')
  body=native(root,name);assert target.count(body)==1;c_file.write_text(owner.replace_once(target,body,owner.replace_once(body,needle,mutation)));subprocess.run(command,check=True)
  bad=subprocess.run([exe],capture_output=True,text=True,timeout=60,env=env);assert bad.returncode==-6 and marker in bad.stderr,(label,bad.returncode,bad.stderr[-1000:])

def audit(root):
 r=engine.audit(root,fixture_builder=fixture,extra_audit=negative_controls);r['base_engine_status']=r['status'];r['status']='MISHARE_NATIVE_DP_UNMAP_COMPOSITE_FIXTURE_PASS_ONLY'
 r['native_DP_function_sha256']={n:hashlib.sha256(native(root,n).encode()).hexdigest() for n in NAMES}
 r['native_DP_function_sha256'].update({n:hashlib.sha256(extract((root/DP).read_text(),n).encode()).hexdigest() for n in [previous.NAME,previous.previous.NAME]})
 r['native_DP_source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [DP,PEER,HEADER]};r['native_DP_enum_source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [previous.TYPES,previous.previous.MODES,previous.HTT]}
 r['additional_composite_cases']=152;r['negative_controls_rejected']=56
 r['checks']=['120 previous combinations use original native unmap/ref lookup/map removal/peer and VDEV finalizers; 32 new combinations select offload, IPA, txrx notification, optional OL/partner callbacks, reference tracing and release timing','original map removal returns its own CONFIG reference separately from the final unmap CONFIG put; lookup acquires a temporary HTT pin through original nonzero-ref admission','invalid/out-of-range and duplicate IDs return without stale peer access; zero-ref lookup admission and WDS offload skip/AST-present/AST-absent paths preserve CONFIG and mapping','original non-WDS unmap records event/Qref/map invalidation/state, drops HTT then lifecycle CONFIG and reaches actual host peer/VDEV frees and production runtime completion','46 inherited controls execute with previous modeled unmap route; ten new mutations exercise native lookup/map/unmap path']
 r['limitations']='Native handler C execution from fixture calls, not real firmware delivery. DP construction, initial lifecycle/map/CHILD reference acquisition, map array and platform atomics/locks, event/Qref/AST/flow/IPA/WDI/OL/partner/statistics endpoints, peer-gone gate and release scheduling remain deterministic models. Map lookup/ref acquisition and removal functions are original, but peer create/map-add/delete, firmware HTT parser/transport and RX event registration do not execute. WDS AST helpers are models; STA cache branch and multi-soc/MLO ownership are unselected. DP and ObjMgr peer remain separate; no production bridge/concurrent late producer safety is certified. Prior component/shutdown boundaries remain; host heap free is not kernel allocator execution. No backend activation, active SSR, phone/RF or AirDrop certification.'
 return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
