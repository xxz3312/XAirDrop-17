package io.github.xairdrop17;

import android.os.IBinder;
import android.os.Parcel;
import java.lang.reflect.Method;

/** Root-side protocol metadata only. Never invoke XOS start/stop/status/config. */
public final class XosBinderProbe {
    private static final String DESCRIPTOR = "com.domestic.xoscomm.IDomesticXOsComm";
    private static final String HASH = "5240962a28e277f0b9764b8f7d1986b35c106edb";
    private static final int VERSION_TRANSACTION = 16777215;
    private static final int HASH_TRANSACTION = 16777214;

    private static Object metadata(IBinder binder, int transaction) throws Exception {
        Parcel request = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        try {
            request.writeInterfaceToken(DESCRIPTOR);
            if (!binder.transact(transaction, request, reply, 0)) {
                throw new IllegalStateException("Metadata transaction unsupported: " + transaction);
            }
            reply.readException();
            return transaction == VERSION_TRANSACTION ? reply.readInt() : reply.readString();
        } finally {
            reply.recycle();
            request.recycle();
        }
    }

    public static void main(String[] args) {
        try {
            Method check = Class.forName("android.os.ServiceManager").getDeclaredMethod("checkService", String.class);
            IBinder binder = null;
            for (int i = 0; i < 30 && binder == null; ++i) {
                binder = (IBinder) check.invoke(null, DESCRIPTOR + "/default");
                if (binder == null) Thread.sleep(100);
            }
            if (binder == null) throw new IllegalStateException("Service not found within 3 seconds");
            String descriptor = binder.getInterfaceDescriptor();
            System.out.println("DESCRIPTOR=" + descriptor);
            if (!DESCRIPTOR.equals(descriptor)) throw new IllegalStateException("Descriptor mismatch");
            if (!binder.pingBinder()) throw new IllegalStateException("Binder ping failed");
            System.out.println("PING_OK");
            Object version = metadata(binder, VERSION_TRANSACTION);
            Object hash = metadata(binder, HASH_TRANSACTION);
            System.out.println("VERSION=" + version);
            System.out.println("HASH=" + hash);
            if (!Integer.valueOf(1).equals(version) || !HASH.equals(hash)) {
                throw new IllegalStateException("Pinned native AIDL metadata mismatch");
            }
            System.out.println("PASS_ROOT_BINDER_METADATA_ONLY");
        } catch (Throwable error) {
            error.printStackTrace(System.err);
            System.exit(1);
        }
    }
}
