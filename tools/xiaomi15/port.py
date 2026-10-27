# SPDX-License-Identifier: GPL-3.0-only
"""MiShare session port derived from Leekin2/XAirDrop eb1fe215.

Build only in Actions. No radio startup, root helper launch or APK mounting.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/mishare'))
from ble_patch import PROFILE, verify_apk, patch_text, normalize_smali, digest, run
VENDOR=ROOT/'third-party/xairdrop15'
PKG='io/github/leekin2/xairdrop'
K0=Path('smali/a/k0.smali')
BLE=Path('smali/a/u0.smali')


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Upstream/source anchor drift: '+old[:90])
    return text.replace(old,new)


def java_method(text,name,replacement=''):
    pattern=r'^    (?:public|private)[^\n{]*\b'+name+r'\([^\n]*\)[^\n]*\{.*?^    \}'
    matches=list(re.finditer(pattern,text,re.S|re.M))
    if len(matches)!=1:raise ValueError('Java method not unique: '+name)
    m=matches[0];return text[:m.start()]+replacement+text[m.end():]


def adapt_bridge(text):
    text=java_method(text,'acquire');text=java_method(text,'release')
    text=once(text,'    private static Network network;\n    private static LocalSocket socket;', '    private static LocalSocket wifiSocket;')
    text=once(text,'    public static boolean leaveWifi(', '    public static synchronized boolean leaveWifi(')
    text=text.replace('c.getDeclaredField(', 'managerField(c, ').replace('manager.getClass().getDeclaredField(', 'managerField(manager.getClass(), ')

    text=once(text,'            Log.w(TAG, "WifiConflictManager fields unavailable", e);','            Log.w(TAG, "WifiConflictManager fields unavailable", e);\n            return false;')
    start=text.index('        String broker = command(NetworkBroker.WIFI_LEAVE);')
    end=text.index('\n    }',start)
    text=text[:start]+'''        String result = holdWifi();
        if (result != null && (result.startsWith("left") || result.startsWith("already left"))) {
            Log.i(TAG, "Wi-Fi held for MiShare: " + result);
            return true;
        }
        try { manager.getClass().getDeclaredField("e").setBoolean(manager, false); }
        catch (Exception ignored) { }
        return false;'''+text[end:]
    text=java_method(text,'restoreWifi','''    public static synchronized void restoreWifi() {
        LocalSocket held = wifiSocket;
        wifiSocket = null;
        if (held != null) try { held.close(); } catch (Exception ignored) { }
        String result = command(NetworkBroker.WIFI_RESTORE);
        if (result != null) Log.i(TAG, "Wi-Fi restore: " + result);
    }''')
    pos=text.index('    private static String command(')
    text=text[:pos]+'''    private static java.lang.reflect.Field managerField(Class<?> type, String name) throws Exception {
        java.lang.reflect.Field field = type.getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }

'''+text[pos:]
    pos=text.index('    private static String command(')
    text=text[:pos]+'''    private static String holdWifi() {
        if (wifiSocket != null) return "already left (held)";
        LocalSocket s = new LocalSocket();
        try {
            s.connect(new LocalSocketAddress(NetworkBroker.SOCKET));
            if (s.getPeerCredentials().getUid() != 0) throw new SecurityException("broker is not root");
            s.setSoTimeout(8000);
            DataOutputStream out = new DataOutputStream(s.getOutputStream());
            out.writeUTF(NetworkBroker.WIFI_HOLD);
            out.flush();
            String answer = new DataInputStream(s.getInputStream()).readUTF();
            if (!answer.startsWith("left") && !answer.startsWith("already left")) throw new IllegalStateException(answer);
            s.setSoTimeout(0);
            wifiSocket = s;
            return answer;
        } catch (Exception e) {
            try { s.close(); } catch (Exception ignored) { }
            Log.w(TAG, "Wi-Fi hold refused; native session remains unsuccessful", e);
            return null;
        }
    }

'''+text[pos:]
    return '// Xiaomi 17 adaptation: Wi-Fi-only broker; native NetworkAgent stays intact.\n'+text


def adapt_broker(text):
    text=once(text,'"xairdrop.xos0"','"xairdrop17.wifi-session"')
    text=once(text,'    static final String ACQUIRE = "ACQUIRE_XOS0";\n','')
    text=once(text,'    static final String WIFI_LEAVE = "WIFI_LEAVE";','    static final String WIFI_HOLD = "HOLD_WIFI";')
    text=once(text,'    private static Class<?> agentClass;\n    private static Object agent;\n','')
    text=once(text,'        agentClass = Class.forName("a.p0");\n','')
    start=text.index('            if (WIFI_LEAVE.equals(command) || WIFI_RESTORE.equals(command)) {')
    end=text.index('            // Held until Xiaomi Share closes the socket (or dies).',start)
    text=text[:start]+'''            if (WIFI_RESTORE.equals(command)) {
                String result = restoreNowIfIdle();
                out.writeUTF(result);
                out.flush();
                return;
            }
            if (!WIFI_HOLD.equals(command)) throw new IllegalArgumentException("Wi-Fi-only command required");
            String result = acquireWifiHold();
            if (!result.startsWith("left") && !result.startsWith("already left")) throw new IllegalStateException(result);
            holding = true;
            leaveSeen = WifiControl.generation();
            out.writeUTF(result);
            out.flush();
'''+text[end:]
    text=java_method(text,'acquire');text=java_method(text,'waitForXos0');text=java_method(text,'onMain')
    text=java_method(text,'release','''    private static synchronized Boolean release() {
        holders = Math.max(0, holders - 1);
        return Boolean.TRUE;
    }''')
    text=once(text,'try { onMain(NetworkBroker::release); }','try { release(); }')
    text=once(text,'if (holders == 0) System.out.println("Wi-Fi restore after release: " + WifiControl.restoreIfStill(seen));','System.out.println("Wi-Fi restore after release: " + restoreIfIdle(seen));')
    text=once(text,'        accept.start();\n','')
    text=once(text,'        System.out.println("startup Wi-Fi restore: " + WifiControl.restore());','        System.out.println("startup Wi-Fi restore: " + WifiControl.restore());\n        accept.start();')
    pos=text.rfind('\n}')
    text=text[:pos]+'''
    private static synchronized String acquireWifiHold() {
        if (holders > 0) { holders++; return "already left (session held)"; }
        String result = WifiControl.leave();
        if (result.startsWith("left") || result.startsWith("already left")) holders++;
        else WifiControl.restore();
        return result;
    }
    private static synchronized String restoreNowIfIdle() {
        return holders == 0 ? WifiControl.restore() : "session active";
    }
    private static synchronized String restoreIfIdle(int seen) {
        return holders == 0 ? WifiControl.restoreIfStill(seen) : "session active";
    }
'''+text[pos:]
    text=once(text,'            System.out.println("Wi-Fi restore: " + WifiControl.restore());\n            System.exit(0);','            String restored = WifiControl.restore();\n            System.out.println("Wi-Fi restore: " + restored);\n            System.exit(restored.startsWith("ERROR") ? 1 : 0);')
    if 'agentClass' in text or 'getNetworkHandle' in text or 'WIFI_LEAVE' in text:raise ValueError('Network broker behavior remains')
    return '// Xiaomi 17 adaptation: authenticated Wi-Fi hold/recovery only; no NetworkAgent.\n'+text


def adapt_wifi(text):
    text=once(text,'/data/adb/xairdrop/wifi-left','/data/adb/xairdrop17/wifi-left')
    text=once(text,'            if (STATE.exists()) return "already left (netId " + read() + ")";','''            if (STATE.exists()) {
                WifiInfo current = (WifiInfo) call("getConnectionInfo");
                if (current != null && current.getFrequency() > 0)
                    return "ERROR recovery pending while Wi-Fi is connected";
                return "already left (netId " + read() + ")";
            }''')

    text=once(text,'            return "left netId " + netId', '            if (!Boolean.TRUE.equals(disabled) || !Boolean.TRUE.equals(disconnected))\n                return "ERROR partial leave; recovery retained: disable=" + disabled + " disconnect=" + disconnected;\n            return "left netId " + netId')
    text=once(text,'            STATE.delete();','            if (!Boolean.TRUE.equals(enabled) || !Boolean.TRUE.equals(reconnected))\n                return "ERROR restore incomplete; recovery retained: enable=" + enabled + " reconnect=" + reconnected;\n            if (!STATE.delete()) return "ERROR restore state could not be removed";')
    return '// Xiaomi 17 adaptation: retain recovery state on partial Wi-Fi failures.\n'+text


def reference_inputs():
    p=json.loads((VENDOR/'provenance.json').read_text())
    for name,want in p['files'].items():
        if digest((VENDOR/name).read_bytes())!=want:raise ValueError('Vendored input changed: '+name)
    source=(VENDOR/'reference/action.sh.txt').read_text();start=source.index('run insmod "$K/qca_cld3_peach_v2.ko" \\')
    block=[]
    for line in source[start:].splitlines():
        block.append(line)
        if not line.rstrip().endswith('\\'):break
    args=shlex.split('\n'.join(block).replace('\\\n',' '));params=dict(x.split('=',1) for x in args[3:] if '=' in x)
    route=json.loads((Path(__file__).parent/'profile.json').read_text())
    if params!=route['reference_driver']['module_parameters'] or params['passthru_fwtype']!='7':raise ValueError('Reference radio profile drift')
    return p,route


def smali_method(text,header,body):
    if text.count(header+'\n')!=1:raise ValueError('Method not unique: '+header)
    start=text.index(header+'\n');end=text.index('.end method',start)+len('.end method')
    return text[:start]+header+'\n'+body+'\n.end method'+text[end:]


def patch_wifi(text):
    if not text.splitlines()[0].endswith(' La/k0;') or 'xairdrop17Reconnect' in text:raise ValueError('Unexpected Wi-Fi manager class')
    for field in ['a:Landroid/net/wifi/WifiManager;','b:I','c:I','d:Ljava/lang/String;','e:Z']:
        if len(re.findall(r'^\.field .*\b'+re.escape(field)+r'\s*$',text,re.M))!=1:raise ValueError('Wi-Fi field drift: '+field)
    wm='La/k0;->a:Landroid/net/wifi/WifiManager;';bridge='L'+PKG+'/Bridge;'
    text=smali_method(text,'.method public final b()Z',f'    .locals 1\n    iget-object v0, p0, {wm}\n    invoke-static {{v0}}, {bridge}->wifiConnected(Landroid/net/wifi/WifiManager;)Z\n    move-result v0\n    return v0')
    text=smali_method(text,'.method public final e()Z',f'    .locals 1\n    iget-object v0, p0, {wm}\n    invoke-static {{p0, v0}}, {bridge}->leaveWifi(Ljava/lang/Object;Landroid/net/wifi/WifiManager;)Z\n    move-result v0\n    return v0')
    text=once(text,'.method public final d()V\n','.method private final xairdrop17Reconnect()V\n')
    text+=f'''
.method public final d()V
    .locals 1
    :try_start_0
    invoke-direct {{p0}}, La/k0;->xairdrop17Reconnect()V
    :try_end_3
    .catchall {{:try_start_0 .. :try_end_3}} :catchall_7
    invoke-static {{}}, {bridge}->restoreWifi()V
    return-void
    :catchall_7
    move-exception v0
    invoke-static {{}}, {bridge}->restoreWifi()V
    throw v0
.end method
'''
    return text


def compile_helpers(sdk,work):
    src=work/'helpers-src';classes=work/'helpers-classes';classes.mkdir(parents=True)
    transforms={'Bridge':adapt_bridge,'NetworkBroker':adapt_broker,'WifiControl':adapt_wifi};hashes={}
    for name,transform in transforms.items():
        original=(VENDOR/'src'/PKG/(name+'.java')).read_text();adapted=transform(original)
        path=src/PKG/(name+'.java');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(adapted)
        hashes[name]={'upstream_sha256':digest(original.encode()),'adapted_sha256':digest(adapted.encode())}
    jar=sdk/'platforms/android-36/android.jar';d8=sdk/'build-tools/36.0.0/d8'
    run('javac','-source','17','-target','17','-cp',jar,'-d',classes,*sorted(src.rglob('*.java')))
    testclasses=work/'hold-fixture';testclasses.mkdir()
    run('javac','-source','17','-target','17','-cp',jar,'-d',testclasses,src/PKG/'NetworkBroker.java',
        ROOT/'tests/fixtures/xiaomi15/FakeWifiControl.java',ROOT/'tests/fixtures/xiaomi15/HoldFixture.java')
    result=subprocess.check_output(['java','-ea','-cp',str(testclasses)+os.pathsep+str(jar),
                                   'io.github.leekin2.xairdrop.HoldFixture'],text=True,timeout=15)
    if result.strip()!='WIFI_HOLD_STATE_LOGIC_PASS_ONLY':raise ValueError('Wi-Fi hold fixture failed')
    print(result.strip())
    outputs={}
    for name,prefixes in [('bridge',['Bridge']),('wifi-broker',['NetworkBroker','WifiControl'])]:
        target=work/name;target.mkdir()
        files=[p for p in (classes/PKG).glob('*.class') if p.name.split('$')[0].split('.')[0] in prefixes]
        run(d8,'--release','--min-api','35','--lib',jar,'--output',target,*sorted(files))
        outputs[name]=(target/'classes.dex').read_bytes()
    return outputs,hashes


def wifi_class_fingerprint(text):
    methods={}
    for m in re.finditer(r'^\.method [^\n]+\n.*?^\.end method',text,re.M|re.S):
        header=m[0].splitlines()[0]
        if header in methods:raise ValueError('Duplicate method')
        methods[header]=digest(normalize_smali(m[0]).encode())
    prefix=re.sub(r'^\.method [^\n]+\n.*?^\.end method','',text,flags=re.M|re.S)
    prefix='\n'.join(line for line in prefix.splitlines() if not line.startswith('#'))
    return {'class_and_fields':digest(normalize_smali(prefix).encode()),'methods':methods}


def class_map(decoded):
    result={}
    for p in decoded.rglob('*.smali'):
        name=str(p.relative_to(decoded));text=p.read_text()
        result[name]=wifi_class_fingerprint(text) if name==str(K0) else digest(normalize_smali(text).encode())
    return result


def build(reference,apktool,sdk,work,output):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Compilation runs only on GitHub Actions')
    provenance,route=reference_inputs();verify_apk(reference,PROFILE['public_reference_sha256'])
    if digest(apktool.read_bytes())!=PROFILE['apktool_sha256']:raise ValueError('Apktool hash mismatch')
    work.mkdir(parents=True,exist_ok=False);output.mkdir(parents=True,exist_ok=False)
    helper,helper_hashes=compile_helpers(sdk,work)
    decoded=work/'decoded';run('java','-jar',apktool,'d','--no-res','-o',decoded,reference)
    originals=class_map(decoded)
    (decoded/BLE).write_text(patch_text((decoded/BLE).read_text()))
    (decoded/K0).write_text(patch_wifi((decoded/K0).read_text()))
    expected=class_map(decoded);changed=sorted(p for p in expected if expected[p]!=originals[p])
    if changed!=sorted([str(BLE),str(K0)]):raise ValueError('Unexpected modified application classes')
    rebuilt=work/'rebuilt.apk';run('java','-jar',apktool,'b','-o',rebuilt,decoded)
    names={'smali':'classes.dex','smali_classes2':'classes2.dex'}
    changed_dex={names[Path(p).parts[0]] for p in changed}
    payload={}
    with zipfile.ZipFile(rebuilt) as z:
        for name in changed_dex:payload[name]=z.read(name)
    payload['classes3.dex']=helper['bridge']
    candidate=work/'candidate-for-validation.apk'
    with zipfile.ZipFile(reference) as src,zipfile.ZipFile(candidate,'x') as dst:
        if 'classes3.dex' in src.namelist():raise ValueError('Extra DEX slot already exists')
        for info in src.infolist():dst.writestr(info,payload.get(info.filename,src.read(info.filename)))
        dst.writestr('classes3.dex',payload['classes3.dex'])
    checked=work/'checked';run('java','-jar',apktool,'d','--no-res','-o',checked,candidate)
    actual=class_map(checked);extra={k:v for k,v in actual.items() if k.startswith('smali_classes3/')}
    if {k:v for k,v in actual.items() if not k.startswith('smali_classes3/')}!=expected:raise ValueError('Compiled application class drift')
    if list(extra)!=['smali_classes3/'+PKG+'/Bridge.smali']:raise ValueError('Unexpected extra application classes')
    bridge=(checked/next(iter(extra))).read_text()
    if 'L'+PKG+'/NetworkBroker;' in bridge or 'Landroid/net/Network;' in bridge:raise ValueError('Bridge still requires a root NetworkAgent')
    if 'xairdrop17.wifi-session' not in bridge or 'HOLD_WIFI' not in bridge:raise ValueError('Compiled Wi-Fi hold protocol missing')
    for name,data in payload.items():(output/name).write_bytes(data)
    (output/'xairdrop17-wifi-broker.dex').write_bytes(helper['wifi-broker'])
    report={'status':'BUILT_XIAOMI15_SESSION_PORT_NOT_RUNTIME_TESTED','profile':'optional-wifi-session-compat','provenance':provenance,'route':route,'apk_inputs':PROFILE,'helper_sources':helper_hashes,'changed_application_classes':changed,'added_application_classes':list(extra),'all_other_application_classes_compared':True,'wifi_comparison_scope':'Exact class/fields and per-method instructions/debug directives, independent of method ordering and class grouping comments; same static-default normalization as BLE build.','compiled_dex_sha256':{k:digest(v) for k,v in payload.items()},'wifi_broker_dex_sha256':digest(helper['wifi-broker']),'native_network_agent_unchanged':True,'region_and_availability_unchanged':True,'default_ble_workflow_unchanged':True,'host_wifi_hold_fixture':'WIFI_HOLD_STATE_LOGIC_PASS_ONLY','runtime_started':False,'firmware_backend_implemented_by_this_payload':False,'limitations':'DEX payload only; not signed/zip-aligned APK or installable module. No helper daemon or APK mounted on phone. Wi-Fi-only root broker and IWifiManager reflection need device validation, SELinux/lifetime integration and cleanup checks before enabling. Full-band pause is an optional compatibility profile, not proven necessary on popsicle. NDI/WMI RAW parameters describe the Xiaomi 15 reference, not verified target firmware support.'}
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['reference','apktool','sdk','work','output']:p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
