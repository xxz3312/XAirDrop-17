"""Actions-only host Java fixtures reject protocol drift and any non-metadata call."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('GITHUB_ACTIONS') == 'true', 'Java compilation runs on Actions')
class BinderMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        fixtures = {
            'IBinder.java': '''package android.os; public interface IBinder {
                String getInterfaceDescriptor(); boolean pingBinder();
                boolean transact(int code, Parcel in, Parcel out, int flags);
            }''',
            'Parcel.java': '''package android.os; public final class Parcel {
                public String token; private int number; private String text;
                public static Parcel obtain(){return new Parcel();}
                public void writeInterfaceToken(String s){token=s;}
                public void readException(){} public void recycle(){}
                public void writeInt(int n){number=n;} public int readInt(){return number;}
                public void writeString(String s){text=s;} public String readString(){return text;}
            }''',
            'ServiceManager.java': '''package android.os; public final class ServiceManager {
                public static IBinder checkService(String name) {
                    if ("absent".equals(System.getProperty("mode"))) return null;
                    if (!"com.domestic.xoscomm.IDomesticXOsComm/default".equals(name)) throw new AssertionError("wrong service");
                    return new IBinder() {
                        public String getInterfaceDescriptor(){ return "descriptor".equals(System.getProperty("mode")) ? "wrong" : "com.domestic.xoscomm.IDomesticXOsComm"; }
                        public boolean pingBinder(){return !"ping".equals(System.getProperty("mode"));}
                        public boolean transact(int code, Parcel in, Parcel out, int flags) {
                            if (flags!=0 || !"com.domestic.xoscomm.IDomesticXOsComm".equals(in.token)) throw new AssertionError("invalid envelope");
                            if ("unsupported".equals(System.getProperty("mode"))) return false;
                            if (code==16777215) out.writeInt("version".equals(System.getProperty("mode")) ? 2 : 1);
                            else if(code==16777214) out.writeString("hash".equals(System.getProperty("mode")) ? "wrong" : "5240962a28e277f0b9764b8f7d1986b35c106edb");
                            else throw new AssertionError("Non-metadata XOS call attempted");
                            return true;
                        }
                    };
                }
            }''',
        }
        for name,text in fixtures.items():(cls.root/name).write_text(text)
        subprocess.run(['javac','-d',str(cls.root),*[str(cls.root/name) for name in fixtures],
            str(ROOT/'native/xos/java/io/github/xairdrop17/XosBinderProbe.java')],check=True)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def run_client(self,mode):
        return subprocess.run(['java','-Dmode='+mode,'-cp',str(self.root),'io.github.xairdrop17.XosBinderProbe'],capture_output=True,text=True,timeout=6)

    def test_only_metadata_transactions_pass(self):
        result=self.run_client('ok');self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('PASS_ROOT_BINDER_METADATA_ONLY',result.stdout)

    def test_mismatch_unavailable_and_unsupported_are_failures(self):
        for mode in ['descriptor','ping','version','hash','unsupported','absent']:
            with self.subTest(mode=mode):
                result=self.run_client(mode)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('PASS_ROOT_BINDER_METADATA_ONLY',result.stdout)


if __name__ == '__main__':unittest.main()
