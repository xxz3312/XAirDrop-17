"""Actions-only Java test: the diagnostic cannot accept another app or changed APK."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('GITHUB_ACTIONS')=='true','Java compilation runs on Actions')
class HostGateTests(unittest.TestCase):
    def test_exact_host_and_each_identity_boundary(self):
        source='''import io.github.xairdrop17.mishareprobe.HostGate;
public class TestGate {
 public static void main(String[] args) {
  String pkg="com.miui.mishare.connectivity",ctx="u:r:platform_app_36:s0:c512,c768",sha="3ca8032f3c55d53e1912a44e42a17334ff739a064cf603e6cb9afb09d810905d";
  if(!HostGate.accepts(pkg,pkg,10132,50402,ctx,sha) || !HostGate.accepts(pkg,pkg+":ui",10132,50402,ctx,sha)) throw new AssertionError("valid host rejected");
  if(HostGate.accepts("other",pkg,10132,50402,ctx,sha) || HostGate.accepts(pkg,"other",10132,50402,ctx,sha) ||
     HostGate.accepts(pkg,pkg,0,50402,ctx,sha) || HostGate.accepts(pkg,pkg,10132,50403,ctx,sha) ||
     HostGate.accepts(pkg,pkg,10132,50402,"u:r:ksu:s0",sha) || HostGate.accepts(pkg,pkg,10132,50402,ctx,"wrong")) throw new AssertionError("identity mismatch accepted");
 }
}'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'TestGate.java').write_text(source)
            subprocess.run(['javac','-d',tmp,str(ROOT/'mishare-probe/app/src/main/java/io/github/xairdrop17/mishareprobe/HostGate.java'),str(p/'TestGate.java')],check=True)
            subprocess.run(['java','-cp',tmp,'TestGate'],check=True,timeout=5)
