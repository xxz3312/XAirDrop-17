#!/usr/bin/env python3
"""Actions-only pinned generic SM engine, native table/enums and PAS lifecycle."""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
import mishare_native_lifecycle_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
SM=previous.SM
ENGINE='qca-wifi-host-cmn/umac/cmn_services/sm_engine/src/wlan_sm_engine.c'
HEADER='qca-wifi-host-cmn/umac/cmn_services/sm_engine/inc/wlan_sm_engine.h'
ENUMS='qca-wifi-host-cmn/umac/mlme/mlme_objmgr/dispatcher/inc/wlan_vdev_mlme_main.h'
SMHEADER='qca-wifi-host-cmn/umac/mlme/vdev_mgr/core/src/vdev_mlme_sm.h'
MLME='qcacld-3.0/components/mlme/core/src/wlan_mlme_vdev_mgr_interface.c'
PLATFORM=r'''
#pragma push_macro("QDF_BUG")
#pragma push_macro("qdf_mem_malloc")
#pragma push_macro("qdf_mem_free")
#pragma push_macro("qdf_atomic_read")
#pragma push_macro("qdf_atomic_set")
#undef QDF_BUG
#define QDF_BUG(x) assert(x)
static unsigned engine_allocations;
static void *engine_mem_malloc(size_t n) {void *p=calloc(1,n);if(p)engine_allocations++;return p;}
static void engine_mem_free(void *p) {assert(p && engine_allocations);engine_allocations--;free(p);}
static void engine_log(const char *fmt,...) {(void)fmt;}
#include "native-sm-engine.c"
#undef qdf_mem_malloc
#undef qdf_mem_free
#pragma pop_macro("qdf_mem_free")
#pragma pop_macro("qdf_mem_malloc")
#undef qdf_atomic_read
#undef qdf_atomic_set
#pragma pop_macro("qdf_atomic_set")
#pragma pop_macro("qdf_atomic_read")
#pragma pop_macro("QDF_BUG")
'''
UNIT=r'''
static unsigned unit_parent,unit_child,unit_enter,unit_exit;
static bool unit_parent_event(void *ctx,uint16_t e,uint16_t n,void *p) {assert(ctx);unit_parent++;return true;}
static bool unit_child_event(void *ctx,uint16_t e,uint16_t n,void *p) {assert(ctx);unit_child++;return false;}
static void unit_parent_entry(void *ctx) {assert(ctx);unit_enter=unit_enter*10+1;}
static void unit_child_entry(void *ctx) {assert(ctx);unit_enter=unit_enter*10+2;}
static void unit_parent_exit(void *ctx) {assert(ctx);unit_exit=unit_exit*10+1;}
static void unit_child_exit(void *ctx) {assert(ctx);unit_exit=unit_exit*10+2;}
static void engine_contract(void) {
 int ctx=1;struct wlan_sm_state_info table[]={
  {0,255,1,true,"parent",unit_parent_entry,unit_parent_exit,unit_parent_event},
  {1,0,255,false,"child",unit_child_entry,unit_child_exit,unit_child_event},
  {2,255,255,false,"other",NULL,NULL,unit_parent_event}};
 struct wlan_sm *s=wlan_sm_create("contract",&ctx,2,table,3,NULL,0);assert(s && engine_allocations==1);
 wlan_sm_transition_to(s,0);assert(s->cur_state==1 && unit_enter==12 && "EXPECTED_NATIVE_DEFAULT_CHILD_ENTRY");
 assert(wlan_sm_dispatch(s,33,0,NULL)==QDF_STATUS_E_INVAL && unit_child==1 && !unit_parent && "EXPECTED_NATIVE_NO_PARENT_FALLBACK");
 wlan_sm_transition_to(s,2);assert(unit_exit==21 && s->cur_state==2 && !engine_atomic_read(&s->in_state_transition));
 assert(wlan_sm_dispatch(s,WLAN_SM_ENGINE_EVENT_NONE,0,NULL)==QDF_STATUS_E_FAILURE);
 wlan_sm_delete(s);assert(!engine_allocations);
 table[1].state=2;assert(!wlan_sm_create("bad-order",&ctx,0,table,3,NULL,0));table[1].state=1;
 table[0].parent_state=1;table[1].has_substates=true;assert(!wlan_sm_create("cycle",&ctx,0,table,3,NULL,0));
}
static struct wlan_sm *attach_engine(struct mishare_runtime_owner *o) {
 struct vdev_mlme_obj *m=last_vdev->mlme;assert(o && !m->sm_hdl && ch_state==WLAN_VDEV_S_INIT && radio_native_substate==0);
 struct wlan_sm *s=wlan_sm_create("owned",m,WLAN_VDEV_S_INIT,sm_info,sizeof(sm_info)/sizeof(sm_info[0]),vdev_sm_event_names,sizeof(vdev_sm_event_names)/sizeof(vdev_sm_event_names[0]));assert(s);
 m->sm_hdl=s;m->ops=&engine_exit_ops;native_full=true;return s;
}
static void engine_cycle(unsigned freq,bool early) {
 reset_pe_test();radio_native_substate=0;struct mishare_runtime_owner *o=queued_start_owner(freq);struct wlan_sm *s=attach_engine(o);
 radio_early_start=radio_early_stop=early;radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_START && s->cur_state==WLAN_VDEV_SS_START_START_PROGRESS && radio_native_substate==s->cur_state && radio_starts==1);
 /* The real engine refuses an event unhandled by the current child; no parent retry. */
 assert(wlan_vdev_mlme_sm_deliver_evt(last_vdev,WLAN_VDEV_SM_EV_START,0,NULL)==QDF_STATUS_E_INVAL && radio_starts==1 && state(o).radio.phase==MISHARE_RADIO_WAIT_START);
 if(!early) {assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);}radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_UP && ch_state==WLAN_VDEV_S_UP && s->cur_state==WLAN_VDEV_SS_UP_ACTIVE && !radio_start_pm && !radio_rt);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_STOP && s->cur_state==WLAN_VDEV_SS_STOP_STOP_PROGRESS && radio_stops==1 && !radio_downs && radio_stop_pm);
 if(!early) {assert(radio_reply_stop()==QDF_STATUS_SUCCESS);}radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_DOWN && s->cur_state==WLAN_VDEV_S_INIT && ch_state==WLAN_VDEV_S_INIT && radio_native_substate==WLAN_VDEV_SS_IDLE && radio_downs==1 && !radio_timer && !radio_stop_pm && !radio_rt && !sm_depth);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !o->radio && pe_pending.bodyptr && ctx_peer_present && objects_live && dp_objects && !dp_detaches);
 wlan_sm_delete(s);last_vdev->mlme->sm_hdl=NULL;assert(!engine_allocations);
}
static void engine_init_rejection(void) {
 reset_pe_test();radio_native_substate=0;struct mishare_runtime_owner *o=queued_start_owner(5240);struct wlan_sm *s=attach_engine(o);engine_fence_before_validate=true;radio_run(false);
 assert(s->cur_state==WLAN_VDEV_S_INIT && radio_native_substate==0 && !radio_starts && !state(o).recovery_radio_init_rejected && !sm_depth);
 stop_recovery(o);assert(mishare_runtime_reclaim_ndi(&o)==-EUCLEAN && o->radio && pe_heap_live && !pe_deletes && !dp_detaches);
 wlan_sm_delete(s);assert(!engine_allocations);
}
static void engine_drift_rejected(void) {
 reset_pe_test();radio_native_substate=0;struct mishare_runtime_owner *o=queued_start_owner(5240);struct wlan_sm *s=attach_engine(o);engine_drift_before_validate=true;radio_run(false);
 assert(!radio_starts && "EXPECTED_INITIAL_NATIVE_SUBSTATE_RECHECK");assert(state(o).radio.phase==MISHARE_RADIO_BLOCKED && !dp_detaches && !pe_deletes);wlan_sm_delete(s);
}
int main(void) {
 engine_contract();
 for(unsigned band=0;band<2;band++)for(unsigned early=0;early<2;early++) {pid_t child=fork();assert(child>=0);if(!child) {engine_cycle(band?5240:2437,early);_Exit(0);}int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));}
 pid_t child=fork();assert(child>=0);if(!child) {engine_init_rejection();_Exit(0);}int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 child=fork();assert(child>=0);if(!child) {engine_drift_rejected();_Exit(0);}assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 puts("MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE='int main(void) {engine_contract();_Exit(0);}'

def native_table(text):
    return re.search(r'struct wlan_sm_state_info sm_info\[\] = \{.*?^\};',text,re.S|re.M)[0]

def native_names(text):
    return re.search(r'static const char \*vdev_sm_event_names\[\] = \{.*?^\};',text,re.S|re.M)[0]

def fixture(root):
    src=previous.fixture(root);sm=(root/SM).read_text();enums=(root/ENUMS).read_text()
    native_enums='\n'.join(re.search(r'enum '+n+r' \{.*?^\};',enums,re.S|re.M)[0] for n in ['wlan_vdev_state','wlan_vdev_sm_evt'])
    src=re.sub(r'^#define WLAN_VDEV_(?:S_|SS_|SM_EV_)\w+[^\n]*\n','',src,flags=re.M)
    src=re.sub(r'enum wlan_vdev_sm_evt \{[^}]+\};',native_enums,src,count=1)
    # Enum definitions must precede modeled object field getters and reset helpers.
    a=src.index('enum wlan_vdev_state {');b=src.index('\n};',src.index('enum wlan_vdev_sm_evt {',a))+3
    block=src[a:b];src=src[:a]+src[b:];needle='typedef int QDF_STATUS;';assert src.count(needle)==1;src=src.replace(needle,needle+'\n'+block+'\n'+PLATFORM,1)
    src=src.replace('struct vdev_mlme_obj {','struct vdev_mlme_obj;\nstruct engine_exit_ops_type {QDF_STATUS (*mlme_vdev_notify_start_state_exit)(struct vdev_mlme_obj *);};\nstruct vdev_mlme_obj { struct wlan_sm *sm_hdl;const struct engine_exit_ops_type *ops;',1)
    src=src.replace('static unsigned radio_native_substate;','static unsigned radio_native_substate=WLAN_VDEV_SS_IDLE;',1).replace('radio_native_substate=0;','radio_native_substate=WLAN_VDEV_SS_IDLE;',1)
    src=src.replace('static bool native_full,native_bad_start_substate,native_bad_stop_substate;','static bool engine_fence_before_validate,engine_drift_before_validate;\nstatic bool native_full,native_bad_start_substate,native_bad_stop_substate;',1)
    needle='return mishare_radio_validate(m,n,p);';assert src.count(needle)==1;src=src.replace(needle,'if(engine_drift_before_validate) {engine_drift_before_validate=false;radio_native_substate=WLAN_VDEV_SS_IDLE;}if(engine_fence_before_validate) {engine_fence_before_validate=false;assert(mishare_runtime_quiesce_psoc(wlan_vdev_get_psoc(m->vdev),MISHARE_QUIESCE_SSR)==1);}'+needle,1)
    src,count=re.subn(r'^static void mlme_vdev_sm_transition_to\([^\n]+\{[^\n]+\}\n',function(sm,'mlme_vdev_sm_transition_to')+'\n',src,count=1,flags=re.M);assert count==1
    src,count=re.subn(r'^static QDF_STATUS mlme_vdev_sm_deliver_event\([^\n]+\{[^\n]+\}\n',function(sm,'mlme_vdev_sm_deliver_event')+'\n',src,count=1,flags=re.M);assert count==1
    src=src.replace('static QDF_STATUS mlme_vdev_sm_deliver_event(struct vdev_mlme_obj *,uint16_t,uint16_t,void *);','QDF_STATUS mlme_vdev_sm_deliver_event(struct vdev_mlme_obj *,enum wlan_vdev_sm_evt,uint16_t,void *);',1)
    old=function(src,'native_full_transition');src=src.replace(old,'',1).replace('static void native_full_transition(struct vdev_mlme_obj *,unsigned);\n','',1)
    old=function(src,'native_full_deliver');src=src.replace(old,'static QDF_STATUS native_full_deliver(struct vdev_mlme_obj *m,uint16_t e,uint16_t n,void *p) {return mlme_vdev_sm_deliver_event(m,e,n,p);}\n',1)
    table=native_table(sm);names=native_names(sm)
    callback=re.search(r'static inline QDF_STATUS mlme_vdev_notify_start_state_exit\(.*?^\}',(root/SMHEADER).read_text(),re.S|re.M)[0]
    reject=function((root/MLME).read_text(),'passthru_mlme_reject_6')
    assert re.search(r'\.mlme_vdev_notify_start_state_exit\s*=\s*passthru_mlme_reject_6',(root/MLME).read_text())
    extra_prefix=reject+'\nstatic const struct engine_exit_ops_type engine_exit_ops={passthru_mlme_reject_6};\n'+callback+'\n'
    refs=set(re.findall(r'\b(mlme_vdev_\w+(?:_entry|_exit|_event))\b',table));available=set(previous.SELECTED+['mlme_vdev_state_init_event'])
    extra=[];stubbed=[];exit_names=[]
    for n in sorted(refs-available):
        if n.endswith('_exit') and (n[:-5]+'_entry') in previous.SELECTED:
            extra.append(function(sm,n));exit_names.append(n)
        else:
            stubbed.append(n)
            extra.append(('static bool '+n+'(void *c,uint16_t e,uint16_t n,void *p) {assert(!"UNSUPPORTED_NATIVE_SM_BRANCH");return false;}' if n.endswith('_event') else 'static void '+n+'(void *c) {assert(!"UNSUPPORTED_NATIVE_SM_BRANCH");}'))
    src=src.replace('static QDF_STATUS native_full_deliver(struct vdev_mlme_obj *m,uint16_t e,uint16_t n,void *p) {return mlme_vdev_sm_deliver_event(m,e,n,p);}', extra_prefix+'\n'.join(extra)+'\n'+names+'\n'+table+'\nstatic QDF_STATUS native_full_deliver(struct vdev_mlme_obj *m,uint16_t e,uint16_t n,void *p) {return mlme_vdev_sm_deliver_event(m,e,n,p);}',1)
    dispatch=function(src,'radio_sm_dispatch');assert dispatch.count('\n }\n assert(0);')==1;src=src.replace(dispatch,dispatch.replace('\n }\n assert(0);','\n default:break;\n }\n assert(0);',1),1)
    src=src.replace(function(src,'main'),UNIT.strip(),1)
    return src,exit_names,stubbed

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!='36df473046706a5259942e1bf7222108dbbb860f':raise ValueError('Unexpected revision')
    source,exits,stubbed=fixture(root);production=ROOT/'kernel/popsicle-hdd';engine=(root/ENGINE).read_text()
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model */\n')
        (d/'qdf_types.h').write_text('#pragma once\ntypedef uint32_t u_int32_t;\n')
        (d/'qdf_atomic.h').write_text('#pragma once\ntypedef struct {int value;} qdf_atomic_t;\n#define qdf_atomic_read engine_atomic_read\n#define qdf_atomic_set engine_atomic_set\nstatic inline int engine_atomic_read(qdf_atomic_t *v) {return v->value;}\nstatic inline void engine_atomic_set(qdf_atomic_t *v,int n) {v->value=n;}\n')
        (d/'qdf_mem.h').write_text('#define qdf_mem_malloc engine_mem_malloc\n#define qdf_mem_free engine_mem_free\n')
        (d/'qdf_module.h').write_text('#define qdf_export_symbol(n)\n')
        (d/'qdf_str.h').write_text('static void qdf_str_lcopy(void *d,const char *s,size_t n) {snprintf(d,n,"%s",s);}\n')
        (d/'wlan_sm_engine_dbg.h').write_text('#pragma once\n#define sm_engine_err(...) engine_log(__VA_ARGS__)\n#define sm_engine_alert(...) engine_log(__VA_ARGS__)\n#define sm_engine_nofl_debug(...) engine_log(__VA_ARGS__)\n#define sm_engine_nofl_info(...) engine_log(__VA_ARGS__)\n#define sm_engine_debug(...) engine_log(__VA_ARGS__)\n#define wlan_sm_save_history(...) ((void)0)\n#define wlan_sm_history_init(...) ((void)0)\n#define wlan_sm_history_delete(...) ((void)0)\n')
        (d/'wlan_sm_engine.h').write_text((root/HEADER).read_text());(d/'native-sm-engine.c').write_text(engine)
        c=d/'engine.c';exe=d/'engine';command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(c),'-o',str(exe)]
        env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
        c.write_text(source);subprocess.run(command,check=True);out=subprocess.check_output([exe],text=True,timeout=60,env=env)
        c.write_text(source.replace(function(source,'main'),NEGATIVE,1));subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
        needle='cur_state = state_info[cur_state].initial_substate;';assert engine.count(needle)==1
        (d/'native-sm-engine.c').write_text(engine.replace(needle,'cur_state = WLAN_SM_ENGINE_STATE_NONE; /* negative: omit default child */',1));subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env);assert bad.returncode==-6 and 'EXPECTED_NATIVE_DEFAULT_CHILD_ENTRY' in bad.stderr
        needle='if (!event_handled) {';assert engine.count(needle)==1
        mutation='if (!event_handled && sm->state_info[state].parent_state != WLAN_SM_ENGINE_STATE_NONE) event_handled = sm->state_info[sm->state_info[state].parent_state].wlan_sm_event(sm->ctx,event,event_data_len,event_data);\n\t\t'+needle
        (d/'native-sm-engine.c').write_text(engine.replace(needle,mutation,1));subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env);assert bad.returncode==-6 and 'EXPECTED_NATIVE_NO_PARENT_FALLBACK' in bad.stderr
        (d/'native-sm-engine.c').write_text(engine)
        target=source.replace(function(source,'main'),'int main(void) {engine_drift_rejected();_Exit(0);}',1)
        c.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
        radio=(production/'wlan_hdd_mishare_radio.c').read_text();needle='wlan_vdev_mlme_get_substate(r->vdev) != r->initial_native_substate ||';assert radio.count(needle)==1
        (d/'wlan_hdd_mishare_radio.c').write_text(radio.replace(needle,'/* negative: omit initial substate equality */',1));subprocess.run(command,check=True)
        bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env);assert bad.returncode==-6 and 'EXPECTED_INITIAL_NATIVE_SUBSTATE_RECHECK' in bad.stderr
    assert out.strip()=='MISHARE_PINNED_NATIVE_SM_ENGINE_FIXTURE_PASS_ONLY'
    sm=(root/SM).read_text()
    return {'status':out.strip(),'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},'native_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [ENGINE,HEADER,ENUMS,SM]},'native_state_table_sha256':hashlib.sha256(native_table(sm).encode()).hexdigest(),'native_event_names_sha256':hashlib.sha256(native_names(sm).encode()).hexdigest(),'native_bridge_sha256':{n:hashlib.sha256(function(sm,n).encode()).hexdigest() for n in ['mlme_vdev_sm_transition_to','mlme_vdev_sm_deliver_event']},'native_exit_sha256':{n:hashlib.sha256(function(sm,n).encode()).hexdigest() for n in exits},'stubbed_unexercised_table_functions':stubbed,'native_exit_callback_sha256':{'inline':hashlib.sha256(re.search(r'static inline QDF_STATUS mlme_vdev_notify_start_state_exit\(.*?^\}',(root/SMHEADER).read_text(),re.S|re.M)[0].encode()).hexdigest(),'passthru_mlme_reject_6':hashlib.sha256(function((root/MLME).read_text(),'passthru_mlme_reject_6').encode()).hexdigest()},'native_SM_header_sha256':hashlib.sha256((root/SMHEADER).read_bytes()).hexdigest(),'PAS_exit_callback_binding_source_reviewed':True,'negative_control_missing_initial_substate_recheck_rejected':True,'negative_control_missing_default_child_rejected':True,'negative_control_parent_fallback_rejected':True,'checks':['complete pinned generic engine C file/header with original dense enum values, original state table and event-name array','unchanged native transition/deliver bridges and 0081 selected native handlers plus native exit functions','real engine dispatch has no parent fallback; default child entry and child/parent exit order verified','real engine create rejects state order and hierarchy cycles; invalid event sentinel rejected','2.4/5240 MHz ordinary/early response lifecycle reaches DOWN, retires controller and queues PE deletion with parents retained','fresh INIT/zero SSR rejection retains resources; it cannot substitute for native IDLE reclaim proof','engine allocations explicitly released in fixture; no synthetic native state reset'], 'limitations':'Generic engine history/logging/memory/atomic and QDF/SM locks/object state fields remain platform models. Actual driver SM create/destroy wrappers, native MLME callback adapters, full WMA postprocessing, physical DP/peer lifecycle and parent coordinator are not executed by this fixture. Full table is preserved; unused native handlers are aborting stubs, not full STA/MLO/DFS/restart support. Ordinary peer physical cleanup after queued PE deletion remains outside this composite. Initial zero substate is recorded and matched before first START; drift rejects. Fresh INIT/zero SSR stays held; existing qualified INIT/IDLE SSR scope only; no active START/UP recovery, backend activation, phone/firmware/RF or AirDrop proof.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
