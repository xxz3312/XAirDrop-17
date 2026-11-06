#!/usr/bin/env python3
"""Actions-only complete native HDD unload; teardown/resource APIs are models."""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from mishare_execution_fixture import COMMON,extract
from mishare_cnss_fixture import native_function
from mishare_ssr_stop_origins import remove_ssr_stop_additions
ROOT=Path(__file__).resolve().parents[2]
BODY=r'''
#define CONFIG_MISHARE_CHECKED_CNSS2_UNREGISTER 1
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define module_param_named(...)
#define MODULE_PARM_DESC(...)
#define hdd_err(...) ((void)0)
#define hdd_debug(...) ((void)0)
#define hdd_debug_rl(...) ((void)0)
#define pr_info(...) ((void)0)
#define QDF_IS_STATUS_SUCCESS(x) ((x)==QDF_STATUS_SUCCESS)
#define QDF_IS_STATUS_ERROR(x) ((x)!=QDF_STATUS_SUCCESS)
#define QDF_BUG(x) assert((x) && "EXPECTED_NO_CHECKED_BUG")
#define QDF_MODULE_ID_HIF 1
#define QDF_MODULE_ID_HDD 2
NATIVE_QDF_ENUM
NATIVE_QDF_CONVERT
static int completion_error,admission_error,unregister_error,transition_calls;
static int admitted,globals_set,unregistered,components,shared_cleanup,ctrl_cleanup,waits,done;
static bool g_soft_unload,link_failure,no_hif,no_hdd;
static QDF_STATUS first_error,late_error;
static void hdd_start_complete(int e){completion_error=e;}
NATIVE_QUARANTINE
struct osif_driver_sync {int alive;};static struct osif_driver_sync sync;
struct hdd_context {void *psoc;};static struct hdd_context hdd;
static bool hdd_get_wlan_driver_status(void){return g_soft_unload;}
static void hdd_place_marker(void *a,const char *b,void *c){if(!strcmp(b,"UNLOAD DONE"))done++;}
static bool cds_is_pcie_link_resume_fail(void){return link_failure;}
static QDF_STATUS osif_driver_sync_trans_start_wait(struct osif_driver_sync **s){*s=&sync;return ++transition_calls==1?first_error:late_error;}
static void osif_driver_sync_wait_for_ops(struct osif_driver_sync *s){assert(s==&sync);waits++;}
static int hdd_mishare_unload_ready(void){admitted++;return admission_error;}
static void osif_driver_sync_trans_stop(struct osif_driver_sync *s){assert(s==&sync);}
static void *cds_get_context(int id){return id==QDF_MODULE_ID_HIF?(no_hif?NULL:(void *)&sync):(no_hdd?NULL:(void *)&hdd);}
static void qdf_rtpm_sync_resume(void){}
static void cds_set_driver_loaded(bool b){assert(!b);globals_set++;}
static void cds_set_unload_in_progress(bool b){assert(b);globals_set++;}
static void hdd_psoc_idle_timer_stop(struct hdd_context *h){assert(h==&hdd);}
static void ucfg_dp_bus_bw_compute_timer_stop(void *p){(void)p;}
static void hdd_distroy_wifi_root_obj_sysfs_files(void){ctrl_cleanup++;}
static void wlan_hdd_tx_power_boost_dev_destroy(void){ctrl_cleanup++;}
static void wlan_hdd_state_ctrl_param_destroy(void){ctrl_cleanup++;}
static int wlan_hdd_unregister_driver_checked(void){unregistered++;return unregister_error;}
static void osif_driver_sync_unregister(void){shared_cleanup++;}
static void hdd_driver_mode_change_unregister(void){shared_cleanup++;}
static void pld_deinit(void){assert(!unregister_error);shared_cleanup++;}
static void hdd_set_conparam(int x){assert(!x);}
static int wlan_wake_lock;
static void qdf_wake_lock_destroy(int *p){assert(p==&wlan_wake_lock);shared_cleanup++;}
static void hdd_component_deinit(void){components++;}
static void hdd_component_cb_deinit(void){components++;}
static void hdd_deinit(void){shared_cleanup++;}
static void osif_driver_sync_destroy(struct osif_driver_sync *p){assert(p==&sync);shared_cleanup++;}
static void osif_sync_deinit(void){shared_cleanup++;}
static void hdd_qdf_deinit(void){shared_cleanup++;}
static void qdf_mem_check_prealloc_leaks(void){}
NATIVE_UNLOAD
NATIVE_ENTRY
NATIVE_WRAPPER
NATIVE_SOFT
static void scenario(int kind){
 assert(try_module_get(THIS_MODULE)); /* existing 0128 persistent load pin */
 if(kind>=1 && kind<=3)first_error=kind==1?QDF_STATUS_E_BUSY:kind==2?QDF_STATUS_E_AGAIN:QDF_STATUS_E_NOMEM;
 if(kind>=4 && kind<=6)admission_error=kind==4?-EBUSY:kind==5?-EINPROGRESS:-EUCLEAN;
 if(kind>=7 && kind<=9)unregister_error=kind==7?-EINPROGRESS:kind==8?-EIO:-EBUSY;
 if(kind==10)late_error=QDF_STATUS_E_BUSY;
 if(kind==11)mishare_load_error=-EUCLEAN;
 if(kind==12)g_soft_unload=true;
 if(kind==13)no_hif=no_hdd=true;
 if(kind==14){link_failure=true;unregister_error=-EBUSY;}
 if(kind==15){first_error=QDF_STATUS_E_BUSY;hdd_wlan_soft_driver_unload();assert(!g_soft_unload && !globals_set && "EXPECTED_SOFT_FIRST_REFUSAL");return;}
 if(kind==16){unregister_error=-EIO;hdd_wlan_soft_driver_unload();assert(!g_soft_unload && mishare_load_error==-EIO && !components && "EXPECTED_SOFT_LATE_QUARANTINE");return;}
 if(kind==17){hdd_driver_unload();assert(done==1 && components==2 && atomic_load(&wlan_module.refs)==1 && "EXPECTED_LEGACY_WRAPPER_PIN");return;}
 int ret=hdd_mishare_driver_unload_checked();
 if(kind>=1 && kind<=3){assert(ret==qdf_status_to_os_return(first_error) && !admitted && !globals_set && !components && !mishare_load_error && "EXPECTED_FIRST_RESULT");}
 else if(kind>=4 && kind<=6){assert(ret==admission_error && !globals_set && !unregistered && !components && waits==1 && "EXPECTED_ADMISSION_RESULT");}
 else if((kind>=7 && kind<=9)||kind==14){assert(ret==unregister_error && unregistered==1 && !components && !shared_cleanup && mishare_load_error==ret && !done && "EXPECTED_UNREGISTER_RESULT");}
 else if(kind==10){assert(ret==-EBUSY && unregistered==1 && !components && !shared_cleanup && mishare_load_error==ret && !done && "EXPECTED_LATE_TRANSITION_RESULT");}
 else if(kind==11){assert(ret==-EUCLEAN && !transition_calls && !globals_set && "EXPECTED_QUARANTINE_ADMISSION");}
 else if(kind==12){assert(ret==-EBUSY && !transition_calls && !globals_set && "EXPECTED_SOFT_ADMISSION");}
 else assert(!ret && done==1 && components==2 && shared_cleanup==8 && ctrl_cleanup==3 && "EXPECTED_FULL_TAIL_SUCCESS");
 assert(atomic_load(&wlan_module.refs)>=1 && "EXPECTED_NO_FINAL_RELEASE");
 if((kind>=7 && kind<=10) || kind==14){assert(atomic_load(&wlan_module.refs)==2 && completion_error==ret && "EXPECTED_FAILURE_PIN");int before=transition_calls;assert(hdd_mishare_driver_unload_checked()==ret && transition_calls==before && "EXPECTED_NO_QUARANTINE_REPLAY");}
}
int main(void){
 (void)foreign_module;(void)module_is_live;(void)module_put;
 for(int n=0;n<18;n++){pid_t p=fork();assert(p>=0);if(!p){scenario(n);_Exit(0);}int s;assert(waitpid(p,&s,0)==p && WIFEXITED(s) && !WEXITSTATUS(s) && "EXPECTED_UNLOAD_CHILD");}
 puts("MISHARE_UNLOAD_RESULT_FIXTURE_PASS_ONLY");return 0;
}
'''
def assemble(wlan):
    main=(wlan/'qcacld-3.0/core/hdd/src/wlan_hdd_main.c').read_text()
    original=subprocess.check_output(['git','-C',str(wlan),'show','HEAD:qcacld-3.0/core/hdd/src/wlan_hdd_main.c'],text=True)
    native=native_function(main,'hdd_driver_unload_internal');assert remove_ssr_stop_additions(native) in original
    qdf=(wlan/'qca-wifi-host-cmn/qdf/linux/src/qdf_status.c').read_text()
    converter=native_function(qdf[qdf.index('#else'):],'qdf_status_to_os_return')
    assert converter in subprocess.check_output(['git','-C',str(wlan),'show','HEAD:qca-wifi-host-cmn/qdf/linux/src/qdf_status.c'],text=True)
    f={'NATIVE_QDF_ENUM':extract((wlan/'qca-wifi-host-cmn/qdf/inc/qdf_status.h').read_text(),r'typedef enum\s*\{[^}]+\}\s*QDF_STATUS;'),
       'NATIVE_QDF_CONVERT':converter,
       'NATIVE_QUARANTINE':extract(main,r'/\* MISHARE_SSR_STOP_BEGIN:reg_hdd_state \*/.*?/\* MISHARE_SSR_STOP_END:reg_hdd_state \*/'),
       'NATIVE_UNLOAD':native,'NATIVE_ENTRY':native_function(main,'hdd_mishare_driver_unload_checked'),
       'NATIVE_WRAPPER':native_function(main,'hdd_driver_unload'),
       'NATIVE_SOFT':native_function(main,'hdd_wlan_soft_driver_unload')}
    code=BODY
    for k,v in f.items():code=code.replace(k,v)
    return COMMON+code,f

def run(wlan,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    code,f=assemble(wlan)
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir();(d/'linux/types.h').write_text('#include <stdbool.h>\n');(d/'mishare_wlan_execution.h').write_bytes((ROOT/'kernel/provider/mishare_wlan_execution.h').read_bytes())
        cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(d),str(d/'test.c'),'-o',str(d/'test')]
        def execute(c):
            (d/'test.c').write_text(c);subprocess.run(cmd,check=True)
            return subprocess.run([d/'test'],capture_output=True,text=True,timeout=30,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1'))
        good=execute(code)
        if good.returncode:raise ValueError(good.stderr)
        mutations=[('*private_result = mishare_ret;','*private_result = 0;','EXPECTED_ADMISSION_RESULT'),
                   ('*private_result = qdf_status_to_os_return(status);','*private_result = 0;','EXPECTED_FIRST_RESULT'),
                   ('hdd_mishare_quarantine_load(mishare_ret);','/* wrongly allow partial teardown replay */','EXPECTED_UNREGISTER_RESULT'),
                   ('hdd_mishare_quarantine_load(qdf_status_to_os_return(status));','/* wrongly allow late-transition replay */','EXPECTED_LATE_TRANSITION_RESULT'),
                   ('*private_result = 0;','*private_result = -EINPROGRESS;','EXPECTED_FULL_TAIL_SUCCESS')]
        for old,new,marker in mutations:
            assert old in f['NATIVE_UNLOAD'];changed=code.replace(f['NATIVE_UNLOAD'],f['NATIVE_UNLOAD'].replace(old,new),1);bad=execute(changed)
            if bad.returncode!=-6 or marker not in bad.stderr:raise ValueError((marker,bad.returncode,bad.stderr[:2000]))
    report={'status':'MISHARE_UNLOAD_RESULT_FIXTURE_PASS_ONLY','fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'native_fragments_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in f.items()},'cases':18,'negative_controls_rejected':len(mutations),'phone_executed':False,'final_module_reference_release_installed':False,'limitations':'Complete native HDD unload body, typed entry, legacy/soft wrappers, 0128 quarantine and native QDF conversion. Parent transitions, component teardown, provider/CNSS2 unregister and module references are models. Caller must serialize load/mode/unload and retain module execution. No external controller, final-reference handoff, normal rmmod, deployed rollback, loader or radio certification.'}
    output.write_text(json.dumps(report,indent=2)+'\n');print(good.stdout,end='')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
