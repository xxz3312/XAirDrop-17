#!/usr/bin/env python3
"""Actions-only selected native MLME lifecycle handlers and strict wire substate gates."""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
import mishare_init_rejection_reset_fixture as previous
from mishare_recovery_fixture import function
ROOT=previous.ROOT
SM=previous.SM
TOP=['init','start','up','suspend','stop']
CHILD=['start_start_progress','start_conn_progress','start_disconn_progress','up_active','suspend_suspend_down','stop_stop_progress','stop_down_progress']
SELECTED=['mlme_vdev_state_'+n+'_entry' for n in TOP]+['mlme_vdev_subst_'+n+'_entry' for n in CHILD]+['mlme_vdev_state_'+n+'_event' for n in ['start','up','suspend','stop']]+['mlme_vdev_subst_'+n+'_event' for n in CHILD]
GLUE=r'''
static unsigned native_lifecycle_events,native_lifecycle_transitions;
static void mlme_vdev_sm_state_update(struct vdev_mlme_obj *m,unsigned state,unsigned substate) {assert(m->vdev==last_vdev && sm_depth==1);ch_state=state;radio_native_substate=substate;}
static void mlme_vdev_set_substate(struct wlan_objmgr_vdev *v,unsigned substate) {assert(v==last_vdev && sm_depth==1);radio_native_substate=substate;}
static QDF_STATUS mlme_vdev_start_send(struct vdev_mlme_obj *m,uint16_t n,void *p) {if(native_bad_start_substate)radio_native_substate=WLAN_VDEV_SS_IDLE;return mishare_radio_start_send(m,n,p);}
static QDF_STATUS mlme_vdev_stop_send(struct vdev_mlme_obj *m,uint16_t n,void *p) {if(native_bad_stop_substate)radio_native_substate=WLAN_VDEV_SS_IDLE;return mishare_radio_stop_send(m,n,p);}
static QDF_STATUS mlme_vdev_start_continue(struct vdev_mlme_obj *m,uint16_t n,void *p) {return mishare_radio_start_continue(m,n,p);}
static QDF_STATUS mlme_vdev_stop_continue(struct vdev_mlme_obj *m,uint16_t n,void *p) {return mishare_radio_stop_continue(m,n,p);}
static QDF_STATUS mlme_vdev_update_beacon(struct vdev_mlme_obj *m,enum beacon_update_op op,uint16_t n,void *p) {return passthru_radio_beacon(m,op,n,p);}
static QDF_STATUS mlme_vdev_up_send(struct vdev_mlme_obj *m,uint16_t n,void *p) {return mishare_radio_up_send(m,n,p);}
static QDF_STATUS mlme_vdev_notify_up_complete(struct vdev_mlme_obj *m,uint16_t n,void *p) {return mishare_radio_up_complete(m,n,p);}
static QDF_STATUS mlme_vdev_down_send(struct vdev_mlme_obj *m,uint16_t n,void *p) {return mishare_radio_down_send(m,n,p);}
static QDF_STATUS mlme_vdev_disconnect_peers(struct vdev_mlme_obj *m,uint16_t n,void *p,bool legacy) {return passthru_radio_disconnect(m,n,p,legacy);}
static bool wlan_vdev_mlme_is_mlo_ap(struct wlan_objmgr_vdev *v) {assert(v==last_vdev);return false;}
static bool wlan_vdev_mlme_is_mlo_ap_sync_disabled(struct wlan_objmgr_vdev *v) {assert(v==last_vdev);return false;}
static void mlme_vdev_start_rsp_notify_mlo_mgr(struct vdev_mlme_obj *m) {assert(m->vdev==last_vdev);}
static void mlme_vdev_up_active_notify_mlo_mgr(struct vdev_mlme_obj *m) {assert(m->vdev==last_vdev);}
static void mlme_vdev_notify_mlo_sync_wait_entry(struct vdev_mlme_obj *m) {assert(!"unsupported MLO path");}
static void mlme_vdev_start_req_failed(struct vdev_mlme_obj *m,uint16_t n,void *p) {assert(!"unsupported native START failure notification");}
static void mlme_vdev_stop_start_send(struct vdev_mlme_obj *m,unsigned kind,uint16_t n,void *p) {assert(!"unsupported pending START cancellation");}
static void mlme_vdev_sta_conn_start(struct vdev_mlme_obj *m,uint16_t n,void *p) {assert(!"unsupported STA path");}
static void mlme_vdev_sta_disconn_start(struct vdev_mlme_obj *m,uint16_t n,void *p) {assert(!"unsupported STA path");}
static QDF_STATUS mlme_vdev_notify_roam_start(struct vdev_mlme_obj *m,uint16_t n,void *p) {assert(!"unsupported roam path");return QDF_STATUS_E_FAILURE;}
NATIVE_HANDLERS
/* Modeled hierarchy/transition adapter: native entry/event bodies above are unchanged. */
static void native_full_transition(struct vdev_mlme_obj *m,unsigned dest) {
 native_lifecycle_transitions++;
 switch(dest) {
 case WLAN_VDEV_S_INIT:mlme_vdev_state_init_entry(m);break;
 case WLAN_VDEV_S_START:mlme_vdev_state_start_entry(m);break;
 case WLAN_VDEV_S_UP:mlme_vdev_state_up_entry(m);break;
 case WLAN_VDEV_S_SUSPEND:mlme_vdev_state_suspend_entry(m);break;
 case WLAN_VDEV_S_STOP:mlme_vdev_state_stop_entry(m);mlme_vdev_subst_stop_stop_progress_entry(m);break;
 case WLAN_VDEV_SS_START_START_PROGRESS:mlme_vdev_subst_start_start_progress_entry(m);break;
 case WLAN_VDEV_SS_START_CONN_PROGRESS:mlme_vdev_subst_start_conn_progress_entry(m);break;
 case WLAN_VDEV_SS_START_DISCONN_PROGRESS:mlme_vdev_subst_start_disconn_progress_entry(m);break;
 case WLAN_VDEV_SS_UP_ACTIVE:mlme_vdev_subst_up_active_entry(m);break;
 case WLAN_VDEV_SS_SUSPEND_SUSPEND_DOWN:mlme_vdev_subst_suspend_suspend_down_entry(m);break;
 case WLAN_VDEV_SS_STOP_STOP_PROGRESS:mlme_vdev_subst_stop_stop_progress_entry(m);break;
 case WLAN_VDEV_SS_STOP_DOWN_PROGRESS:mlme_vdev_subst_stop_down_progress_entry(m);break;
 default:assert(!"unsupported native transition");
 }
}
static QDF_STATUS native_full_deliver(struct vdev_mlme_obj *m,uint16_t e,uint16_t n,void *p) {
 bool handled=false;assert(sm_depth==1 && !lock_depth && m->vdev==last_vdev);native_lifecycle_events++;
 switch(radio_native_substate) {
 case WLAN_VDEV_SS_IDLE:break;
 case WLAN_VDEV_SS_START_START_PROGRESS:handled=mlme_vdev_subst_start_start_progress_event(m,e,n,p);break;
 case WLAN_VDEV_SS_START_CONN_PROGRESS:handled=mlme_vdev_subst_start_conn_progress_event(m,e,n,p);break;
 case WLAN_VDEV_SS_START_DISCONN_PROGRESS:handled=mlme_vdev_subst_start_disconn_progress_event(m,e,n,p);break;
 case WLAN_VDEV_SS_UP_ACTIVE:handled=mlme_vdev_subst_up_active_event(m,e,n,p);break;
 case WLAN_VDEV_SS_SUSPEND_SUSPEND_DOWN:handled=mlme_vdev_subst_suspend_suspend_down_event(m,e,n,p);break;
 case WLAN_VDEV_SS_STOP_STOP_PROGRESS:handled=mlme_vdev_subst_stop_stop_progress_event(m,e,n,p);break;
 case WLAN_VDEV_SS_STOP_DOWN_PROGRESS:handled=mlme_vdev_subst_stop_down_progress_event(m,e,n,p);break;
 default:assert(!"unsupported native substate");
 }
 if(!handled) switch(ch_state) {
 case WLAN_VDEV_S_INIT:native_init_calls++;handled=mlme_vdev_state_init_event(m,e,n,p);native_init_last_handled=handled;break;
 case WLAN_VDEV_S_START:handled=mlme_vdev_state_start_event(m,e,n,p);break;
 case WLAN_VDEV_S_UP:handled=mlme_vdev_state_up_event(m,e,n,p);break;
 case WLAN_VDEV_S_SUSPEND:handled=mlme_vdev_state_suspend_event(m,e,n,p);break;
 case WLAN_VDEV_S_STOP:handled=mlme_vdev_state_stop_event(m,e,n,p);break;
 default:assert(!"unsupported native state");
 }
 return handled?QDF_STATUS_SUCCESS:QDF_STATUS_E_FAILURE;
}
'''
HARNESS=r'''
static void native_cycle(unsigned freq,bool early) {
 reset_pe_test();native_full=true;struct mishare_runtime_owner *o=queued_start_owner(freq);
 unsigned events=native_lifecycle_events,transitions=native_lifecycle_transitions;
 radio_early_start=radio_early_stop=early;radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_START && ch_state==WLAN_VDEV_S_START && radio_native_substate==WLAN_VDEV_SS_START_START_PROGRESS && radio_starts==1 && radio_start_pm && radio_rt);
 if(!early) {assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);}
 radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_UP && ch_state==WLAN_VDEV_S_UP && radio_native_substate==WLAN_VDEV_SS_UP_ACTIVE && !radio_start_pm && !radio_rt);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS);radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_WAIT_STOP && ch_state==WLAN_VDEV_S_STOP && radio_native_substate==WLAN_VDEV_SS_STOP_STOP_PROGRESS && radio_stops==1 && !radio_downs && radio_stop_pm);
 if(!early) {assert(radio_reply_stop()==QDF_STATUS_SUCCESS);}
 radio_run(false);
 assert(state(o).radio.phase==MISHARE_RADIO_DOWN && ch_state==WLAN_VDEV_S_INIT && radio_native_substate==WLAN_VDEV_SS_IDLE && state(o).radio.down_accepted && radio_downs==1 && !radio_stop_pm && !radio_rt && !radio_timer && !sm_depth);
 assert(native_lifecycle_events>=events+18 && native_lifecycle_transitions>=transitions+10);
 assert(mishare_runtime_destroy(&o)==-EINPROGRESS && !o->radio && pe_pending.bodyptr && ctx_peer_present && objects_live && dp_objects && !dp_detaches);native_full=false;
}
static void native_substate_fault(bool stop) {
 reset_pe_test();native_full=true;struct mishare_runtime_owner *o=queued_start_owner(5240);
 if(!stop)native_bad_start_substate=true;
 radio_run(false);
 if(stop) {assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);radio_run(false);assert(state(o).radio.phase==MISHARE_RADIO_UP);assert(mishare_runtime_destroy(&o)==-EINPROGRESS);native_bad_stop_substate=true;radio_run(false);}
 assert((stop?!radio_stops:!radio_starts) && "EXPECTED_NATIVE_WIRE_SUBSTATE_GATE");
 assert(state(o).radio.phase==MISHARE_RADIO_BLOCKED && !state(o).radio.down_accepted && !pe_deletes && !dp_detaches && !sm_depth);
 assert(mishare_runtime_destroy(&o)==-EUCLEAN && o->radio);
}
int main(void) {
 assert(!init_rejection_regressions());
 for(unsigned band=0;band<2;band++)for(unsigned early=0;early<2;early++) {pid_t child=fork();assert(child>=0);if(!child) {native_cycle(band?5240:2437,early);_Exit(0);}int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));}
 for(unsigned fault=0;fault<2;fault++) {pid_t child=fork();assert(child>=0);if(!child) {native_substate_fault(fault);_Exit(0);}int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));}
 /* Native handled=true does not propagate generic START-send failure. Controller must still quarantine. */
 for(unsigned fault=0;fault<4;fault++) {
  reset_pe_test();pid_t child=fork();assert(child>=0);if(!child) {
   native_full=true;struct mishare_runtime_owner *o=queued_start_owner(5240);radio_start_fail=fault==0;radio_run(false);
   if(fault) {assert(radio_reply_start(0)==QDF_STATUS_SUCCESS);radio_apply_fail=fault==1;if(fault==2)nan_cap=false;radio_run(false);if(fault==3) {assert(mishare_runtime_destroy(&o)==-EINPROGRESS);radio_stop_fail=true;radio_run(false);}}
   assert(state(o).radio.phase==MISHARE_RADIO_BLOCKED && mishare_runtime_destroy(&o)==-EUCLEAN && o->radio && !pe_deletes && !dp_detaches && !sm_depth);_Exit(0);
  }int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 }
 puts("MISHARE_SELECTED_NATIVE_LIFECYCLE_FIXTURE_PASS_ONLY");return 0;
}
'''
NEGATIVE_HARNESS=r'''
int main(void) {native_substate_fault(NEGATIVE_STOP);_Exit(0);}
'''

def fixture(root):
    src=previous.fixture(root)
    handlers='\n'.join(function((root/SM).read_text(),n) for n in SELECTED)
    wrapped_handlers='#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored \"-Wunused-but-set-variable\"\n'+handlers+'\n#pragma GCC diagnostic pop\n'
    tokens=sorted(set(re.findall(r'\bWLAN_VDEV_(?:SM_EV|SS|S)_\w+',handlers)))
    defines='\n'.join('#define '+n+' '+str(500+i) for i,n in enumerate(tokens) if not re.search(r'\b'+n+r'\b',src))+'\n#ifndef START_REQ\n#define START_REQ 1\n#endif\n#pragma push_macro("QDF_BUG")\n#undef QDF_BUG\n#define QDF_BUG(x) assert(x)\n'
    head='static bool native_full,native_bad_start_substate,native_bad_stop_substate;\nstatic void native_full_transition(struct vdev_mlme_obj *,unsigned);\nstatic QDF_STATUS native_full_deliver(struct vdev_mlme_obj *,uint16_t,uint16_t,void *);\n'
    needle='static unsigned refused_prepare_calls,refused_sm_calls;';assert src.count(needle)==1;src=src.replace(needle,head+needle,1)
    needle='assert(m->vdev==last_vdev);ch_state=state;';assert src.count(needle)==1;src=src.replace(needle,'if(native_full) {native_full_transition(m,state);return;}'+needle,1)
    fn=function(src,'mlme_vdev_sm_deliver_event');needle='{';fnnew=fn.replace(needle,'{if(native_full)return native_full_deliver(m,e,n,p);',1);src=src.replace(fn,fnnew,1)
    dispatcher=function(src,'radio_sm_dispatch');new=dispatcher.replace('{','{if(native_full)return native_full_deliver(v->mlme,e,0,NULL);',1);assert new!=dispatcher;src=src.replace(dispatcher,defines+GLUE.replace('NATIVE_HANDLERS',wrapped_handlers)+'\n#pragma pop_macro("QDF_BUG")\n'+new,1)
    src=src.replace('int main(void) {','static int init_rejection_regressions(void) {',1).replace('puts("MISHARE_NATIVE_INIT_REJECTION_SSR_FIXTURE_PASS_ONLY");return 0;','return 0;',1)
    return src+HARNESS

def audit(root):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('C compilation is restricted to GitHub Actions')
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()!='36df473046706a5259942e1bf7222108dbbb860f':raise ValueError('Unexpected revision')
    source=fixture(root);production=ROOT/'kernel/popsicle-hdd'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'dispatcher/inc').mkdir(parents=True);(d/'core/src').mkdir(parents=True)
        (d/'linux/types.h').write_text('#pragma once\n#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n')
        for n in ['linux/etherdevice.h','linux/slab.h','linux/spinlock.h','linux/bug.h','wlan_objmgr_pdev_obj.h','wlan_objmgr_vdev_obj.h','wlan_vdev_mlme.h','wlan_vdev_mlme_api.h','wlan_vdev_mgr_tgt_if_rx_defs.h','wlan_osif_priv.h','qdf_status.h','scheduler_api.h','wmi_unified_param.h','core/src/vdev_mgr_ops.h']:(d/n).write_text('/* platform model */\n')
        c=d/'native.c';exe=d/'native';command=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-g','-fsanitize=address,undefined','-pthread','-I'+str(d),'-I'+str(production),'-I'+str(d/'dispatcher/inc'),str(c),'-o',str(exe)]
        env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
        c.write_text(source);subprocess.run(command,check=True);out=subprocess.check_output([exe],text=True,timeout=60,env=env)
        gate='wlan_vdev_mlme_get_substate(r->vdev) !=\n            (start ? WLAN_VDEV_SS_START_START_PROGRESS : WLAN_VDEV_SS_STOP_STOP_PROGRESS) ||'
        assert function(source,'radio_send').count(gate)==1
        for stop in [False,True]:
            target=source.replace(function(source,'main'),NEGATIVE_HARNESS.replace('NEGATIVE_STOP','true' if stop else 'false').strip(),1)
            c.write_text(target);subprocess.run(command,check=True);subprocess.run([exe],check=True,timeout=45,env=env)
            fn=function(target,'radio_send');c.write_text(target.replace(fn,fn.replace(gate,'/* negative: omit native wire substate gate */',1),1));subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,timeout=45,env=env);assert bad.returncode==-6 and 'EXPECTED_NATIVE_WIRE_SUBSTATE_GATE' in bad.stderr
    assert out.strip()=='MISHARE_SELECTED_NATIVE_LIFECYCLE_FIXTURE_PASS_ONLY'
    return {'status':out.strip(),'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),'production_sha256':{n:hashlib.sha256((production/n).read_bytes()).hexdigest() for n in ['wlan_hdd_mishare_runtime.c','wlan_hdd_mishare_runtime.h','wlan_hdd_mishare_ndi.h','wlan_hdd_mishare_radio.c','wlan_hdd_mishare_radio.h']},'native_SM_sha256':hashlib.sha256((root/SM).read_bytes()).hexdigest(),'native_handler_sha256':{n:hashlib.sha256(function((root/SM).read_text(),n).encode()).hexdigest() for n in SELECTED},'negative_control_missing_START_substate_gate_rejected':True,'negative_control_missing_STOP_substate_gate_rejected':True,'checks':['0080 regressions retained','2.4/5240 MHz normal and inline response complete native entry/event lifecycle with real production callbacks, native TX/RX and PM helpers','normal DOWN retires controller and queues PE deletion with PE/peer/VDEV/DP retained; reset-platform composite does not execute normal physical peer teardown','INIT/IDLE validation and exact START_START_PROGRESS/STOP_STOP_PROGRESS wire gates','native handled=true after failed callbacks still quarantines production controller','both missing wire-substate gate negative controls fail as expected'],'limitations':'Selected unchanged native entry/event bodies and 0080 INIT/API execute; hierarchy dispatch, transitions/default-child selection and QDF/locks remain modeled. PAS non-MLO ordinary START-UP-DOWN-STOP-INIT only; restart/STA/MLO/DFS helpers deliberately abort if reached. Native target-if/PM and production lifecycle run with modeled transport, generic engine, transitive WMA postprocessing, allocation, DP/peer physical lifecycle and parents. Normal physical peer/PE teardown after queued deletion is not executed in this composite; it retains parent resources in child cases. No new SSR recovery scope, automatic shutdown/parent coordination, backend activation, phone/firmware/RF or AirDrop certification.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=audit(a.wlan);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
