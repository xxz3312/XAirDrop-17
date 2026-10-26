package io.github.xairdrop17.mishareprobe;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.os.IBinder;
import android.os.Parcel;
import android.os.Process;
import android.util.Log;
import java.io.FileInputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.libxposed.api.XposedModule;
import io.github.libxposed.api.XposedModuleInterface;

/** Diagnostic hook only: no availability override, XOS start, Wi-Fi or file transfer. */
public final class Entry extends XposedModule {
    private static final String TAG = "XAirDrop17Probe";
    private final AtomicBoolean scheduled = new AtomicBoolean();
    private String processName = "unknown";

    @Override public void onModuleLoaded(XposedModuleInterface.ModuleLoadedParam param) {
        processName = param.getProcessName();
    }
    @Override public void onPackageLoaded(XposedModuleInterface.PackageLoadedParam param) {
        if (!param.isFirstPackage() || !HostGate.HOST.equals(param.getPackageName())) return;
        try {
            hook(Application.class.getDeclaredMethod("attach", Context.class)).intercept(chain -> {
                Object value = chain.proceed();
                safeSchedule((Context) chain.getArg(0));
                return value;
            });
            hook(Activity.class.getDeclaredMethod("onResume")).intercept(chain -> {
                Object value = chain.proceed();
                safeSchedule((Context) chain.getThisObject());
                return value;
            });
            Log.i(TAG, "HOOK_INSTALLED process=" + processName);
        } catch (Throwable error) { Log.e(TAG, "HOOK_INSTALL_FAILED", error); }
    }
    private void safeSchedule(Context context) {
        try { schedule(context); } catch (Throwable error) { Log.e(TAG, "HOOK_SCHEDULE_FAILED", error); }
    }
    private void schedule(Context context) {
        if (!HostGate.HOST.equals(context.getPackageName()) || !scheduled.compareAndSet(false, true)) return;
        Thread thread = new Thread(() -> diagnose(context), "XAirDrop-Metadata");
        thread.setDaemon(true);
        thread.start();
    }
    private static String readContext() throws Exception {
        try (FileInputStream stream = new FileInputStream("/proc/self/attr/current")) {
            return new String(stream.readAllBytes(), StandardCharsets.UTF_8).replace("\u0000", "").trim();
        }
    }
    private static String digest(String path) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (FileInputStream stream = new FileInputStream(path)) {
            byte[] buffer = new byte[65536];
            int n;
            while ((n = stream.read(buffer)) != -1) hash.update(buffer, 0, n);
        }
        StringBuilder value = new StringBuilder();
        for (byte b : hash.digest()) value.append(String.format("%02x", b & 255));
        return value.toString();
    }
    private void diagnose(Context context) {
        try {
            int uid = Process.myUid();
            String domain = readContext();
            long version = context.getPackageManager().getPackageInfo(HostGate.HOST, 0).getLongVersionCode();
            String sha = digest(context.getApplicationInfo().sourceDir);
            Log.i(TAG, "IDENTITY uid=" + uid + " pid=" + Process.myPid() + " process=" + processName + " context=" + domain + " apk=" + sha);
            if (!HostGate.accepts(context.getPackageName(), processName, uid, version, domain, sha)) {
                Log.e(TAG, "UNSUPPORTED_HOST_NO_BINDER_CALLS"); return;
            }
            String descriptor = "com.domestic.xoscomm.IDomesticXOsComm";
            java.lang.reflect.Method check = Class.forName("android.os.ServiceManager").getDeclaredMethod("checkService", String.class);
            IBinder binder = null;
            for (int i = 0; i < 30 && binder == null; ++i) {
                binder = (IBinder) check.invoke(null, descriptor + "/default");
                if (binder == null) Thread.sleep(100);
            }
            if (binder == null) throw new IllegalStateException("Service unavailable to MiShare within 3 seconds");
            if (!descriptor.equals(binder.getInterfaceDescriptor()) || !binder.pingBinder()) throw new IllegalStateException("Descriptor or ping mismatch");
            Object versionReply = metadata(binder, descriptor, 16777215);
            Object hashReply = metadata(binder, descriptor, 16777214);
            Log.i(TAG, "METADATA version=" + versionReply + " hash=" + hashReply);
            if (!Integer.valueOf(1).equals(versionReply) || !"5240962a28e277f0b9764b8f7d1986b35c106edb".equals(hashReply)) throw new IllegalStateException("Metadata mismatch");
            Log.i(TAG, "PASS_MISHARE_BINDER_METADATA_ONLY uid=" + uid + " context=" + domain);
        } catch (Throwable error) { Log.e(TAG, "MISHARE_BINDER_DIAGNOSTIC_FAILED", error); }
    }
    private static Object metadata(IBinder binder, String descriptor, int code) throws Exception {
        Parcel request = Parcel.obtain(), reply = Parcel.obtain();
        try {
            request.writeInterfaceToken(descriptor);
            if (!binder.transact(code, request, reply, 0)) throw new IllegalStateException("Metadata transaction unsupported: " + code);
            reply.readException();
            return code == 16777215 ? reply.readInt() : reply.readString();
        } finally { reply.recycle(); request.recycle(); }
    }
}
