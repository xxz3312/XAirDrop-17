"""Actions-only native fixture checks distinguish denials from query failures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('GITHUB_ACTIONS') == 'true', 'native compilation runs on Actions')
class PolicyQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.work=Path(cls.tmp.name)
        fixture=cls.work/'selinux.c'
        fixture.write_text('''#include <stdlib.h>
#include <string.h>
#include <errno.h>
int is_selinux_enabled(void){return 1;}
int security_getenforce(void){return getenv("TEST_POLICY_MODE") && !strcmp(getenv("TEST_POLICY_MODE"),"permissive") ? 0 : 1;}
void *selinux_android_service_context_handle(void){return (void*)1;}
int selabel_lookup(void *h,char **context,const char *name,int kind){
 (void)h;(void)kind;
 if(strcmp(name,"com.domestic.xoscomm.IDomesticXOsComm/default")){errno=EINVAL;return -1;}
 *context=strdup("u:object_r:test_xos_service:s0");return 0;
}
void freecon(char *context){free(context);}
int selinux_check_access(const char *s,const char *t,const char *c,const char *p,void *a){
 (void)s;(void)t;(void)c;(void)a;
 const char *m=getenv("TEST_POLICY_MODE");
 if(m && !strcmp(m,"error")){errno=EINVAL;return -1;}
 if(m && !strcmp(m,"deny") && !strcmp(p,"find")){errno=EACCES;return -1;}
 return 0;
}
''')
        subprocess.run(['cc','-shared','-fPIC',str(fixture),'-o',str(cls.work/'libselinux.so')],check=True)
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(ROOT/'native/xos/policy-probe.c'),'-ldl','-o',str(cls.work/'probe')],check=True)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def run_probe(self,mode,context='u:r:platform_app_36:s0:c512,c768'):
        env=dict(os.environ,LD_LIBRARY_PATH=str(self.work),TEST_POLICY_MODE=mode)
        return subprocess.run([str(self.work/'probe'),context],env=env,text=True,capture_output=True,timeout=3)

    def test_allowed_is_only_a_policy_candidate_pass(self):
        r=self.run_probe('allow');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(r.stdout.count('CHECK '),6)
        self.assertIn('POLICY_ALLOW_CANDIDATES_ONLY',r.stdout)
        self.assertIn('FRESH_SERVICE_CONTEXT=u:object_r:test_xos_service:s0',r.stdout)

    def test_denial_separate_from_internal_query_error(self):
        r=self.run_probe('deny');self.assertEqual(r.returncode,1)
        self.assertIn('SUMMARY denied=1 errors=0',r.stdout)
        r=self.run_probe('error');self.assertEqual(r.returncode,2)
        self.assertIn('ERROR_POLICY_QUERY',r.stdout)
        self.assertNotIn('POLICY_DENIALS_OBSERVED',r.stdout)

    def test_permissive_and_wrong_caller_not_accepted(self):
        for mode,context in [('permissive','u:r:platform_app_36:s0:c512,c768'),('allow','u:r:untrusted_app:s0')]:
            r=self.run_probe(mode,context);self.assertEqual(r.returncode,2)
            self.assertNotIn('POLICY_ALLOW_CANDIDATES_ONLY',r.stdout)


if __name__=='__main__':unittest.main()
