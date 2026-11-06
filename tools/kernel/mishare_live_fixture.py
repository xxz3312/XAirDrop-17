#!/usr/bin/env python3
"""Actions-only provider controller + actual HDD lifecycle wrappers/full unload."""
import argparse,hashlib,json,os,subprocess,tempfile,re
from pathlib import Path
from mishare_execution_fixture import COMMON,extract
from mishare_unload_result_fixture import BODY as UNLOAD_BODY,assemble as unload_assemble
from mishare_cnss_fixture import native_function
ROOT=Path(__file__).resolve().parents[2]
EXTRA=r'''
struct kernel_param {int dummy;};
static int load_calls,mode_calls,clean_release_error,prepare_calls;
static int cb_reinit(struct pci_dev *p,const struct pci_device_id *id){return 0;}
static void cb_shutdown(struct pci_dev *p){}
static int cb_idle(struct pci_dev *p){return 0;}
static const struct mishare_wlan_pcie_execution_ops descriptor={THIS_MODULE,cb_reinit,cb_shutdown,cb_reinit,cb_idle};
static int hdd_driver_load_internal(void){load_calls++;assert(try_module_get(THIS_MODULE));return opairshare_wlan_execution_register_pcie_v3(&descriptor);}
static int con_mode_handler_internal(const char *s,const struct kernel_param *p){mode_calls++;return 0;}
static int pld_registration_release_clean(void){
 if(clean_release_error)return clean_release_error;
 assert(!execution_ops.owner && !unregister_scope && "EXPECTED_CLEAN_SCOPE");
 module_put(THIS_MODULE);return 0;
}
NATIVE_LIVE_LOAD
NATIVE_LIVE_MODE
NATIVE_LIVE_CONTROLLER
NATIVE_MODULE_INIT
static int instrumented_prepare(void){
 in_wlan=true;prepare_calls++;int ret=hdd_mishare_driver_unload_checked();
 in_wlan=false;callback_returned=true;return ret;
}
static int false_success(void){prepare_calls++;callback_returned=true;return 0;}
static void initialize(void){
 atomic_store(&wlan_module.coming,true);
 assert(!con_mode_handler("0",NULL) && mode_calls==1);
 assert(!hdd_module_init());
 assert(live_unload_state==LIVE_ARMED && live_unload_prepare==hdd_mishare_driver_unload_checked && atomic_load(&wlan_module.refs)==2 && "EXPECTED_TWO_INDEPENDENT_PINS");
 /* Add an instrumented WLAN return frame around the actual stored callback;
  * production registration above is checked before this fixture-only hook.
  */
 live_unload_prepare=instrumented_prepare;expect_final_return=true;callback_returned=false;
}
static void scenario(int kind){
 initialize();
 assert(opairshare_wlan_live_unload_request_v1()==-EAGAIN && !prepare_calls && !execution_closing && "EXPECTED_COMING_REJECTION");
 atomic_store(&wlan_module.coming,false);
 if(kind==1)admission_error=-EINPROGRESS;
 if(kind==2)unregister_error=-EIO;
 if(kind==3)late_error=QDF_STATUS_E_BUSY;
 if(kind==4)clean_release_error=-EBUSY;
 if(kind==5)live_unload_prepare=false_success;
 if(kind==6){execution_active=1;assert(opairshare_wlan_live_unload_request_v1()==-EBUSY && !prepare_calls && !execution_closing && "EXPECTED_ACTIVE_REJECTION");execution_active=0;}
 if(kind==7){execution_closing=true;assert(opairshare_wlan_live_unload_request_v1()==-EBUSY && !prepare_calls && atomic_load(&wlan_module.refs)==2 && "EXPECTED_CLOSING_REJECTION");return;}
 if(kind==8){assert(opairshare_wlan_live_unload_arm_v1(THIS_MODULE,instrumented_prepare)==-EALREADY && atomic_load(&wlan_module.refs)==2 && "EXPECTED_NO_REARM");}
 assert(hdd_driver_load()==-ESHUTDOWN && load_calls==1 && "EXPECTED_NO_LOAD_REENTRY");
 assert(con_mode_handler("1",NULL)==-ESHUTDOWN && mode_calls==1 && "EXPECTED_MODE_CLOSED");
 assert(hdd_wlan_soft_driver_load()==-EOPNOTSUPP);hdd_wlan_soft_driver_unload();assert(!globals_set && "EXPECTED_SOFT_CLOSED");
 int ret=opairshare_wlan_live_unload_request_v1();
 if(kind>=1 && kind<=5){
  int expected=kind==1?-EINPROGRESS:kind==2?-EIO:kind==5?-EUCLEAN:-EBUSY;
  assert(ret==expected && live_unload_state==LIVE_FAILED && atomic_load(&wlan_module.refs)>=2 && "EXPECTED_FAILED_LEASE_RETAINED");
  int calls=prepare_calls,comps=components;assert(opairshare_wlan_live_unload_request_v1()==expected && calls==prepare_calls && "EXPECTED_NO_FAILURE_REPLAY");
  hdd_driver_unload();assert(components==comps && "EXPECTED_NO_LEGACY_BYPASS");
 }else{
  assert(!ret && done==1 && components==2 && mishare_live_done && !execution_ops.owner && live_unload_state==LIVE_COMPLETE && !atomic_load(&wlan_module.refs) && "EXPECTED_EXTERNAL_COMPLETE");
  assert(!live_unload_owner && !live_unload_prepare && "EXPECTED_NO_STALE_CALLBACK");
  assert(opairshare_wlan_live_unload_request_v1()==-EALREADY && hdd_mishare_driver_unload_checked()==-ESHUTDOWN && prepare_calls==1 && "EXPECTED_NO_SUCCESS_REPLAY");
  hdd_driver_unload();assert(done==1 && components==2 && unregistered==1 && transition_calls==2 && "EXPECTED_EXIT_NO_DOUBLE_TEARDOWN");
 }
}
static pthread_mutex_t block_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t block_cond=PTHREAD_COND_INITIALIZER;
static bool blocked,release_prepare;
static int blocking_prepare(void){
 assert(!pthread_mutex_lock(&block_lock));blocked=true;pthread_cond_broadcast(&block_cond);
 while(!release_prepare)assert(!pthread_cond_wait(&block_cond,&block_lock));
 assert(!pthread_mutex_unlock(&block_lock));return instrumented_prepare();
}
static void *request_thread(void *p){expect_final_return=true;callback_returned=false;assert(!opairshare_wlan_live_unload_request_v1());return NULL;}
static void concurrent(void){
 initialize();atomic_store(&wlan_module.coming,false);live_unload_prepare=blocking_prepare;
 pthread_t thread;assert(!pthread_create(&thread,NULL,request_thread,NULL));
 assert(!pthread_mutex_lock(&block_lock));while(!blocked)assert(!pthread_cond_wait(&block_cond,&block_lock));assert(!pthread_mutex_unlock(&block_lock));
 assert(opairshare_wlan_live_unload_request_v1()==-EBUSY && !prepare_calls && atomic_load(&wlan_module.refs)==2 && "EXPECTED_SINGLE_REQUEST");
 assert(!pthread_mutex_lock(&block_lock));release_prepare=true;pthread_cond_broadcast(&block_cond);assert(!pthread_mutex_unlock(&block_lock));assert(!pthread_join(thread,NULL));
 assert(prepare_calls==1 && !atomic_load(&wlan_module.refs) && "EXPECTED_CONCURRENT_COMPLETE");
}
int main(void){
 (void)foreign_module;
 for(int n=0;n<10;n++){pid_t p=fork();assert(p>=0);if(!p){if(n==9)concurrent();else scenario(n);_Exit(0);}int s;assert(waitpid(p,&s,0)==p && WIFEXITED(s) && !WEXITSTATUS(s) && "EXPECTED_LIVE_CHILD");}
 puts("MISHARE_LIVE_UNLOAD_FIXTURE_PASS_ONLY");return 0;
}
'''

def assemble(wlan):
    main=(wlan/'qcacld-3.0/core/hdd/src/wlan_hdd_main.c').read_text()
    _,previous=unload_assemble(wlan)
    def tag(n):return extract(main,r'/\* MISHARE_SSR_STOP_BEGIN:live_'+n+r' \*/.*?/\* MISHARE_SSR_STOP_END:live_'+n+r' \*/')
    f=dict(previous)
    f.update({'NATIVE_LIVE_STATE':tag('state'),'NATIVE_LIVE_LOAD':tag('load_wrapper'),'NATIVE_LIVE_MODE':tag('mode_wrapper'),'NATIVE_LIVE_CONTROLLER':tag('controller'),
              'NATIVE_MODULE_INIT':extract(main,r'/\* MISHARE_SSR_STOP_BEGIN:reg_hdd_module_init \*/.*?/\* MISHARE_SSR_STOP_END:reg_hdd_module_init \*/'),
              'NATIVE_ENTRY':native_function(main,'hdd_mishare_driver_unload_checked_internal'),
              'NATIVE_WRAPPER':native_function(main,'hdd_driver_unload'),
              'NATIVE_SOFT':native_function(main,'hdd_wlan_soft_driver_unload'),
              'NATIVE_SOFT_LOAD':native_function(main,'hdd_wlan_soft_driver_load')})
    code=UNLOAD_BODY[:UNLOAD_BODY.index('static void scenario(')]
    code=code.replace('NATIVE_ENTRY','NATIVE_ENTRY\nNATIVE_SOFT_LOAD')
    # Checked platform completion is modeled; its native body is covered by
    # the independent CNSS2 fixture. This model uses the real provider scope.
    old='static int wlan_hdd_unregister_driver_checked(void){unregistered++;return unregister_error;}'
    new='''static int wlan_hdd_unregister_driver_checked(void){
 unregistered++;if(unregister_error)return unregister_error;
 int ret=opairshare_wlan_execution_unregister_begin(THIS_MODULE,false);
 return ret?ret:opairshare_wlan_execution_unregister_end(THIS_MODULE,0);
}'''
    assert old in code;code=code.replace(old,new)
    code=code.replace('NATIVE_QUARANTINE','NATIVE_QUARANTINE\nNATIVE_LIVE_STATE')
    code+=EXTRA
    # Disabled legacy soft-load gate precedes these names; supply their
    # declarations so its original unreachable tail still compiles.
    code=code.replace('NATIVE_SOFT_LOAD','static bool cds_is_driver_loaded(void){return true;}\nstatic void pld_wlan_hw_enable(void){}\nint hdd_driver_load(void);\nNATIVE_SOFT_LOAD',1)
    for key in sorted(f,key=len,reverse=True):code=code.replace(key,f[key])
    return COMMON+'\n#define MODULE 1\nstruct pci_dev {struct device dev;};struct pci_device_id {int vendor,device;};\n#include "execution.c"\n'+code,f

def run(wlan,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    code,f=assemble(wlan);provider=(ROOT/'kernel/provider/execution.c').read_text()
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for n in ['module.h','mutex.h','string.h']:(d/'linux'/n).write_text('/* fixture declarations */\n')
        (d/'mishare_wlan_execution.h').write_bytes((ROOT/'kernel/provider/mishare_wlan_execution.h').read_bytes())
        cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(d),str(d/'test.c'),'-o',str(d/'test')]
        def execute(c,p):
            (d/'test.c').write_text(c);(d/'execution.c').write_text(p);subprocess.run(cmd,check=True)
            return subprocess.run([d/'test'],capture_output=True,text=True,timeout=40,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1'))
        good=execute(code,provider)
        if good.returncode:raise ValueError(good.stderr)
        mutations=[(code,provider.replace('ret = prepare();','module_put(owner);\n    ret = prepare();',1),'EXPECTED_EXTERNAL_RETURN'),
                   (code,provider.replace('if (!ret && (execution_ops.owner || execution_active || unregister_scope))','if (false && !ret && (execution_ops.owner || execution_active || unregister_scope))',1),'EXPECTED_FAILED_LEASE_RETAINED'),
                   (code,provider.replace('if (module_is_coming(owner) || !module_is_live(owner))','if (false && (module_is_coming(owner) || !module_is_live(owner)))',1),'EXPECTED_COMING_REJECTION'),
                   (code.replace('if (mishare_live_load_started)\n\t\tret = -ESHUTDOWN;','if (false && mishare_live_load_started)\n\t\tret = -ESHUTDOWN;',1),provider,'EXPECTED_NO_LOAD_REENTRY'),
                   (code.replace('ret = mishare_live_load_started ? -ESHUTDOWN :','ret = false ? -ESHUTDOWN :',1),provider,'EXPECTED_MODE_CLOSED'),
                   (code.replace('if (READ_ONCE(mishare_live_load_started))','if (false && READ_ONCE(mishare_live_load_started))',1),provider,'EXPECTED_EXIT_NO_DOUBLE_TEARDOWN')]
        for c,p,marker in mutations:
            assert c!=code or p!=provider;bad=execute(c,p)
            if bad.returncode!=-6 or marker not in bad.stderr:raise ValueError((marker,bad.returncode,bad.stderr[:2500]))
    report={'status':'MISHARE_LIVE_UNLOAD_FIXTURE_PASS_ONLY','fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'provider_sha256':hashlib.sha256(provider.encode()).hexdigest(),'native_fragments_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in f.items()},'isolated_cases':9,'concurrent_request_cases':1,'negative_controls_rejected':len(mutations),'phone_executed':False,'limitations':'Real external provider controller, native lifecycle wrappers/module-init arm and complete native HDD unload. Added instrumented WLAN return frame verifies final put after return. Native load/driver synchronization/platform unregister/component destruction are models; independent fixtures cover their core bodies. No kernel sysfs/loader execution, real file-operation drain, power/recovery coordinator, force-unload, RF or Apple interoperability certification.'}
    output.write_text(json.dumps(report,indent=2)+'\n');print(good.stdout,end='')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
