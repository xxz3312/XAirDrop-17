#!/usr/bin/env python3
"""Actions-only optional ICNSS checked unregister with provider/native remove."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from mishare_execution_fixture import COMMON, extract, assemble as execution_assemble
from mishare_icnss_origins import restore

ROOT = Path(__file__).resolve().parents[2]
NATIVE = 'platform/icnss2/main.c'
HARNESS = r'''
#include "execution.c"
struct osif_psoc_sync {int active;};
static struct osif_psoc_sync sync_state;
struct pld_driver_ops {void (*remove)(struct device *,int);};
struct pld_context {struct pld_driver_ops *ops;};
#define PLD_BUS_TYPE_SNOC 43
static struct device device={1},other_device={2};
static int transition_error,prepare_error,vendor_calls,sync_destroys,sync_unregisters,remove_calls;
static bool context_missing;
static void vendor_remove(struct device *d,int bus) {assert(d==&device && bus==43);vendor_calls++;}
static struct pld_driver_ops vendor_ops={.remove=vendor_remove};
static struct pld_context pld_context={.ops=&vendor_ops};
static struct pld_context *pld_get_global_context(void) {return context_missing?NULL:&pld_context;}
static void cds_set_driver_loaded(bool x) {(void)x;remove_calls++;}
static void cds_set_unload_in_progress(bool x) {(void)x;}
static int osif_psoc_sync_trans_start_wait(struct device *d,struct osif_psoc_sync **out) {assert(d==&device);*out=&sync_state;if(transition_error)return transition_error;sync_state.active=1;return 0;}
static void osif_psoc_sync_wait_for_ops(struct osif_psoc_sync *s) {assert(s==&sync_state && s->active);}
static int hdd_mishare_remove_prepare(struct device *d) {assert(d==&device);return prepare_error;}
static void osif_psoc_sync_unregister(struct device *d) {assert(d==&device && sync_state.active);sync_unregisters++;}
static void pld_del_dev(struct pld_context *c,struct device *d) {assert(c==&pld_context && d==&device);}
static void osif_psoc_sync_trans_stop(struct osif_psoc_sync *s) {assert(s==&sync_state);s->active=0;}
static void osif_psoc_sync_destroy(struct osif_psoc_sync *s) {assert(s==&sync_state && !s->active);sync_destroys++;}
NATIVE_REMOVE
NATIVE_STATE
struct icnss_driver_ops {void (*remove)(struct device *);};
struct platform_device {struct device dev;};
struct icnss_priv {unsigned long state;struct icnss_driver_ops *ops;struct platform_device *pdev;};
static struct platform_device pdev;
static struct icnss_driver_ops pld_ipci_ops={.remove=pld_ipci_remove},foreign_ops;
#define native_ops pld_ipci_ops
static struct icnss_priv platform;
static int posts,post_error,power_offs,blocks,unblocks;
static bool platform_missing,swap_before_worker;
static void set_bit(int bit,unsigned long *v) {*v|=1UL<<bit;}
static void clear_bit(int bit,unsigned long *v) {*v&=~(1UL<<bit);}
static bool test_bit(int bit,const unsigned long *v) {return (*v&(1UL<<bit))!=0;}
static void icnss_block_shutdown(bool block) {if(block){blocks++;set_bit(ICNSS_BLOCK_SHUTDOWN,&platform.state);}else{unblocks++;clear_bit(ICNSS_BLOCK_SHUTDOWN,&platform.state);}}
static void icnss_hw_power_off(struct icnss_priv *p) {assert(p==&platform);power_offs++;clear_bit(ICNSS_POWER_ON,&p->state);}
static struct icnss_priv *icnss_get_plat_priv(void) {return platform_missing?NULL:&platform;}
#define icnss_pr_info(...) ((void)0)
#define icnss_pr_err(...) ((void)0)
#define ICNSS_DRIVER_EVENT_UNREGISTER_DRIVER 17
#define ICNSS_EVENT_SYNC_UNINTERRUPTIBLE 3
NATIVE_HANDLER
struct event_args {struct icnss_priv *priv;void *data;int result;};
static void *event_worker(void *arg) {struct event_args *a=arg;if(swap_before_worker)a->priv->ops=&foreign_ops;a->result=icnss_driver_event_unregister_driver(a->priv,a->data);return NULL;}
static int icnss_driver_event_post(struct icnss_priv *priv,int type,unsigned flags,void *data) {
 assert(priv==&platform && type==17 && flags==3 && "EXPECTED_SYNC_EVENT_CONTRACT");posts++;
 if(post_error)return post_error;
 struct event_args args={.priv=priv,.data=data};pthread_t worker;
 assert(!pthread_create(&worker,NULL,event_worker,&args));assert(!pthread_join(worker,NULL));return args.result;
}
NATIVE_CHECKED_ENTRY

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
NATIVE_LEGACY_ENTRY
#pragma GCC diagnostic pop
#define CONFIG_MISHARE_CHECKED_ICNSS_UNREGISTER 1
NATIVE_PLD_CHECKED
static int dummy_reinit(struct device *d) {(void)d;return 0;}
static void dummy_shutdown(struct device *d) {(void)d;}
static const struct mishare_wlan_execution_ops execution_descriptor={.owner=THIS_MODULE,.reinit=dummy_reinit,.shutdown=dummy_shutdown,.idle_restart=dummy_reinit,.idle_shutdown=dummy_reinit};
static int status_calls;
static int receipt_status(struct device *d) {status_calls++;return opairshare_wlan_execution_remove_status(d);}
static void skipped_remove(struct device *d) {(void)d;}
static void pending_remove(struct device *d) {bool rec=false;assert(!opairshare_wlan_execution_remove_begin(THIS_MODULE,d,&rec) && rec);}
static void prepare_base(bool going) {
 assert(!execution_ops.owner && !unregister_scope && !atomic_load(&wlan_module.refs));
 atomic_store(&wlan_module.deny,going);expect_final_return=false;
 pdev.dev=device;platform=(struct icnss_priv){.ops=&native_ops,.pdev=&pdev};
 set_bit(ICNSS_DRIVER_PROBED,&platform.state);set_bit(ICNSS_POWER_ON,&platform.state);
 native_ops.remove=pld_ipci_remove;transition_error=prepare_error=vendor_calls=sync_destroys=sync_unregisters=remove_calls=0;
 posts=post_error=power_offs=blocks=unblocks=status_calls=0;context_missing=platform_missing=swap_before_worker=false;sync_state.active=0;
 assert(!opairshare_wlan_execution_register_v2(&execution_descriptor));
}
static void prepare(bool going) {
 prepare_base(going);
 assert(!opairshare_wlan_execution_unregister_begin(THIS_MODULE,going));
 assert(opairshare_wlan_execution_unregister_begin(&foreign_module,false)==-EBUSY);
}
/* Native remove receives the platform device; the fixture redirects identity
 * at assembly, preserving the production function body byte-for-byte.
 */
static void success_case(bool going) {
 prepare(going);int before_get=atomic_load(&execution_get_count);
 assert(opairshare_wlan_execution_remove_status(&pdev.dev)==-ENODATA && "EXPECTED_MISSING_RECEIPT");
 assert(!icnss_unregister_driver_checked_v1(&native_ops,receipt_status));
 assert(vendor_calls==1 && sync_unregisters==1 && sync_destroys==1 && status_calls==1 && power_offs==1 && !platform.ops && !test_bit(ICNSS_DRIVER_PROBED,&platform.state) && !test_bit(ICNSS_DRIVER_UNLOADING,&platform.state) && !test_bit(ICNSS_BLOCK_SHUTDOWN,&platform.state) && "EXPECTED_PLATFORM_SUCCESS");
 assert(atomic_load(&wlan_module.refs)==(going?0:1) && unregister_scope && "EXPECTED_SCOPE_NOT_RELEASED_BY_QUERY");
 assert(opairshare_wlan_execution_remove_status(&other_device)==-EXDEV && "EXPECTED_RECEIPT_DEVICE");
 assert(!opairshare_wlan_execution_unregister_end(THIS_MODULE,0));
 assert(!atomic_load(&wlan_module.refs) && !execution_ops.owner && atomic_load(&execution_get_count)==before_get);
}
static void failure_case(int kind,bool going) {
 prepare(going);int expected;
 switch(kind) {
 case 0:prepare_error=-EUCLEAN;expected=-EUCLEAN;break;
 case 1:prepare_error=-EINPROGRESS;expected=-EINPROGRESS;break;
 case 2:transition_error=-EBUSY;expected=-EBUSY;break;
 case 3:context_missing=true;expected=-ENODEV;break;
 case 4:native_ops.remove=skipped_remove;expected=-ENODATA;break;
 default:native_ops.remove=pending_remove;expected=-EINPROGRESS;break;
 }
 assert(icnss_unregister_driver_checked_v1(&native_ops,receipt_status)==expected && "EXPECTED_PLATFORM_REMOVE_ERROR");
 assert(!power_offs && !unblocks && blocks==1 && platform.ops==&native_ops && test_bit(ICNSS_DRIVER_PROBED,&platform.state) && test_bit(ICNSS_DRIVER_UNLOADING,&platform.state) && test_bit(ICNSS_BLOCK_SHUTDOWN,&platform.state) && test_bit(ICNSS_DRIVER_UNREGISTER_FAILED,&platform.state) && "EXPECTED_PLATFORM_RETAINED");
 int before=remove_calls,events=posts;
 assert(icnss_unregister_driver_checked_v1(&native_ops,receipt_status)==-ESHUTDOWN && posts==events && "EXPECTED_CHECKED_NO_REPLAY");
 assert(icnss_unregister_driver(&native_ops)==-ESHUTDOWN && remove_calls==before && !power_offs && "EXPECTED_LEGACY_NO_BYPASS");
 int finish=opairshare_wlan_execution_unregister_end(THIS_MODULE,expected);
 assert(finish==expected && execution_ops.owner && unregister_scope && atomic_load(&wlan_module.refs)==(going?0:1) && "EXPECTED_FAILURE_SCOPE_RETAINED");
}
static void admission_case(int kind) {
 prepare(false);int expected;
 switch(kind) {
 case 0:platform_missing=true;expected=-ENODEV;break;
 case 1:platform.pdev=NULL;expected=-ENODEV;break;
 case 2:platform.ops=NULL;expected=-ENOENT;break;
 case 3:platform.ops=&foreign_ops;expected=-ENOENT;break;
 case 4:post_error=-ENOMEM;expected=-ENOMEM;break;
 case 5:swap_before_worker=true;expected=-EINVAL;break;
 default:clear_bit(ICNSS_DRIVER_PROBED,&platform.state);expected=-ENODEV;break;
 }
 assert(icnss_unregister_driver_checked_v1(&native_ops,receipt_status)==expected && "EXPECTED_PLATFORM_ADMISSION");
 assert(!remove_calls && !power_offs && !blocks && !status_calls && "EXPECTED_ADMISSION_NO_SIDE_EFFECTS");
 assert(opairshare_wlan_execution_unregister_end(THIS_MODULE,expected)==expected && execution_ops.owner && atomic_load(&wlan_module.refs)==1);
}
static void consumer_case(bool going,bool fail) {
 prepare_base(going);if(fail)prepare_error=-EUCLEAN;
 int ret=pld_ipci_unregister_driver_checked();
 if(fail) {
  assert(ret==-EUCLEAN && !power_offs && platform.ops==&native_ops && unregister_scope && execution_ops.owner && atomic_load(&wlan_module.refs)==(going?0:1) && "EXPECTED_CONSUMER_GUARD");
 } else assert(!ret && power_offs==1 && !platform.ops && !unregister_scope && !execution_ops.owner && !atomic_load(&wlan_module.refs) && "EXPECTED_CONSUMER_GUARD");
}
int main(void) {

 /* Preserve existing numeric state values and fit the native state word. */
 assert(ICNSS_REBOOT_REGISTERED==28 && ICNSS_DRIVER_UNREGISTER_FAILED==29);
 assert(opairshare_wlan_execution_remove_status(NULL)==-EINVAL);
 assert(opairshare_wlan_execution_remove_status(&device)==-ENOENT);
 assert(icnss_unregister_driver_checked_v1(NULL,receipt_status)==-EINVAL);
 assert(icnss_unregister_driver_checked_v1(&native_ops,NULL)==-EINVAL);
 success_case(false);success_case(true);
 for(int going=0;going<2;going++)for(int kind=0;kind<6;kind++) {
  pid_t child=fork();assert(child>=0);if(!child){failure_case(kind,going);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) && "EXPECTED_FAILURE_CHILD");
 }
 for(int kind=0;kind<7;kind++) {
  pid_t child=fork();assert(child>=0);if(!child){admission_case(kind);_Exit(0);}
  int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status) && "EXPECTED_ADMISSION_CHILD");
 }
 /* Existing unguarded entry remains source-compatible and still lacks this
  * protection on its first call. Never claim this optional ABI is deployed.
  */
 pid_t child=fork();assert(child>=0);if(!child) {
  prepare(false);prepare_error=-EUCLEAN;assert(!icnss_unregister_driver(&native_ops));
  assert(power_offs==1 && !platform.ops && !status_calls && "EXPECTED_LEGACY_COMPATIBILITY_LIMIT");_Exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && !WEXITSTATUS(status));
 for(int going=0;going<2;going++) {
  consumer_case(going,false);
  pid_t c=fork();assert(c>=0);if(!c){consumer_case(going,true);_Exit(0);}
  int s;assert(waitpid(c,&s,0)==c && WIFEXITED(s) && !WEXITSTATUS(s) && "EXPECTED_CONSUMER_CHILD");
 }
 puts("MISHARE_ICNSS_CHECKED_UNREGISTER_FIXTURE_PASS_ONLY");return 0;
}
'''


def assemble(wlan):
    platform=(wlan/NATIVE).read_text()
    for path in [NATIVE,'platform/icnss2/main.h','platform/inc/icnss2.h','platform/icnss2/debug.c']:
        assert restore((wlan/path).read_text())==subprocess.check_output(['git','-C',str(wlan),'show','HEAD:'+path],text=True),path
    _,existing,_=execution_assemble(wlan)
    fragments={
        'NATIVE_REMOVE':existing['NATIVE_REMOVE'],
        'NATIVE_PLD_CHECKED':existing['NATIVE_CHECKED'],
        'NATIVE_STATE':extract((wlan/'platform/icnss2/main.h').read_text(),r'^enum icnss_driver_state\s*\{.*?^\};'),
        'NATIVE_HANDLER':extract(platform,r'^struct icnss_unregister_guard_v1\s*\{.*?^\};')+'\n'+extract(platform,r'^static int icnss_driver_event_unregister_driver\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_CHECKED_ENTRY':extract(platform,r'^int icnss_unregister_driver_checked_v1\([^;{]+?\)\s*\{.*?^\}'),
        'NATIVE_LEGACY_ENTRY':extract(platform,r'^int icnss_unregister_driver\([^;{]+?\)\s*\{.*?^\}'),
    }
    code=HARNESS
    for name,body in fragments.items():code=code.replace(name,body)
    # Model device identity globally, never alter any extracted native function.
    code=code.replace('d==&device','d==&pdev.dev')
    # pdev must be declared before the native remove dependency stubs.
    code=code.replace('struct platform_device {struct device dev;};\n','').replace('static struct platform_device pdev;\n','')
    code=code.replace('static struct device device={1},other_device={2};','static struct device device={1},other_device={2};\nstruct platform_device {struct device dev;};\nstatic struct platform_device pdev;')
    return COMMON+code,fragments,platform


def run(wlan,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Native compilation runs only on Actions')
    code,fragments,platform=assemble(wlan)
    provider=(ROOT/'kernel/provider/execution.c').read_text()
    mutations=[
        (provider,code.replace('if (ret) {\n\t\t\t/* Retain ops','if (false && ret) {\n\t\t\t/* Retain ops',1),'EXPECTED_PLATFORM_REMOVE_ERROR'),
        (provider,code.replace('\t\t\treturn ret;\n\t\t}\n\t}', '\t\t\ticnss_hw_power_off(priv);\n\t\t\treturn ret;\n\t\t}\n\t}',1),'EXPECTED_PLATFORM_RETAINED'),
        (provider,code.replace('if (test_bit(ICNSS_DRIVER_UNREGISTER_FAILED, &priv->state))','if (false && test_bit(ICNSS_DRIVER_UNREGISTER_FAILED, &priv->state))',1),'EXPECTED_LEGACY_NO_BYPASS'),
        (provider,code.replace('guard->ops != priv->ops','(false && guard->ops != priv->ops)',1),'EXPECTED_PLATFORM_ADMISSION'),
        (provider,code.replace('ICNSS_EVENT_SYNC_UNINTERRUPTIBLE, &guard','0, &guard',1),'EXPECTED_SYNC_EVENT_CONTRACT'),
        (provider.replace('else if (!unregister_completed_dev)','else if (false && !unregister_completed_dev)',1),code,'EXPECTED_MISSING_RECEIPT'),
        (provider.replace('else if (unregister_completed_dev != dev)','else if (false && unregister_completed_dev != dev)',1),code,'EXPECTED_RECEIPT_DEVICE'),
        (provider.replace('ret = unregister_error;\n    else if (unregister_remove_dev','ret = 0;\n    else if (unregister_remove_dev',1),code,'EXPECTED_PLATFORM_REMOVE_ERROR'),
    ]
    mutations.append((provider,code.replace('ret = icnss_unregister_driver_checked_v1(&pld_ipci_ops,\n\t\t\t\t      opairshare_wlan_execution_remove_status);','ret = icnss_unregister_driver(&pld_ipci_ops);',1),'EXPECTED_CONSUMER_GUARD'))
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'linux').mkdir()
        for name in ['module.h','mutex.h','string.h']:(d/'linux'/name).write_text('/* modeled */\n')
        (d/'mishare_wlan_execution.h').write_text((ROOT/'kernel/provider/mishare_wlan_execution.h').read_text())
        source=d/'test.c';exe=d/'test'
        command=['cc','-std=c11','-Wall','-Wextra','-Werror','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(d),str(source),'-o',str(exe)]
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        (d/'execution.c').write_text(provider);source.write_text(code);subprocess.run(command,check=True)
        out=subprocess.check_output([exe],text=True,env=env,timeout=30)
        for changed,changed_code,marker in mutations:
            assert changed!=provider or changed_code!=code,marker
            (d/'execution.c').write_text(changed);source.write_text(changed_code);subprocess.run(command,check=True)
            bad=subprocess.run([exe],capture_output=True,text=True,env=env,timeout=30)
            assert bad.returncode==-6 and marker in bad.stderr,(marker,bad.returncode,bad.stderr[:2000])
    report={'status':'MISHARE_ICNSS_CHECKED_UNREGISTER_FIXTURE_PASS_ONLY','source_commit':subprocess.check_output(['git','-C',str(wlan),'rev-parse','HEAD'],text=True).strip(),'fixture_sha256':hashlib.sha256(code.encode()).hexdigest(),'provider_sha256':hashlib.sha256(provider.encode()).hexdigest(),'execution_header_sha256':hashlib.sha256((ROOT/'kernel/provider/mishare_wlan_execution.h').read_bytes()).hexdigest(),'native_platform_sha256':hashlib.sha256(platform.encode()).hexdigest(),'native_fragments_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in fragments.items()},'consumer_success_cases':2,'consumer_failure_cases':2,'success_cases':2,'isolated_remove_failure_cases':12,'isolated_admission_cases':7,'legacy_compatibility_limit_cases':1,'negative_controls_rejected':len(mutations),'event_handler_thread':'real pthread created/joined by modeled synchronous event_post','sanitizers':['address','undefined','leak detection'],'optional_platform_binary_built':False,'native_WLAN_consumer_uses_optional_entry':True,'phone_executed':False,'limitations':'Production provider, complete native PLD remove, actual ICNSS unregister handler/new checked entry/legacy entry execute against modeled module API, event post, synchronization, vendor removal, shutdown block and power-off. Native event scheduler, completion primitive, real platform binary/ABI/firmware/loader are not executed. A failure retains flags and shutdown block permanently without a recovery API. No-probe checked cleanup refuses. Existing unguarded entry remains legacy on first use; default WLAN consumer is unchanged; opt-in native consumer executes here. This optional platform contract is not yet target-linked/deployed and does not protect phone unregister. Other shutdown/recovery paths remain uncoordinated; module-exit cannot veto loader removal.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(out,end='')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wlan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wlan,a.output)
