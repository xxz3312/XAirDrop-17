// Host logic test; Android socket/Binder/Wi-Fi operations are not executed.
package io.github.leekin2.xairdrop;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicReference;
public final class HoldFixture {
    static Object invoke(String name) throws Exception {
        Method method = NetworkBroker.class.getDeclaredMethod(name);
        method.setAccessible(true);
        return method.invoke(null);
    }
    public static void main(String[] args) throws Exception {
        assert invoke("acquireWifiHold").toString().startsWith("left");
        assert invoke("acquireWifiHold").toString().startsWith("already left");
        assert WifiControl.leaves == 1;
        assert invoke("restoreNowIfIdle").equals("session active") && WifiControl.restores == 0;
        invoke("release");
        assert invoke("restoreNowIfIdle").equals("session active");
        invoke("release");
        assert invoke("restoreNowIfIdle").equals("restored") && WifiControl.restores == 1;
        WifiControl.answer = "ERROR partial leave";
        assert invoke("acquireWifiHold").toString().startsWith("ERROR");
        assert WifiControl.restores == 2;
        assert invoke("restoreNowIfIdle").equals("restored"); // no orphan holder on refusal
        WifiControl.answer = "left netId 7";
        int previousLeaves = WifiControl.leaves;
        AtomicReference<Throwable> error = new AtomicReference<>();
        Thread[] threads = new Thread[8];
        for (int i = 0; i < threads.length; i++) {
            threads[i] = new Thread(() -> { try { invoke("acquireWifiHold"); } catch (Throwable t) { error.set(t); } });
            threads[i].start();
        }
        for (Thread thread : threads) thread.join();
        assert error.get() == null && WifiControl.leaves == previousLeaves + 1;
        for (int i = 0; i < threads.length; i++) {
            threads[i] = new Thread(() -> { try { invoke("release"); } catch (Throwable t) { error.set(t); } });
            threads[i].start();
        }
        for (Thread thread : threads) thread.join();
        assert error.get() == null && invoke("restoreNowIfIdle").equals("restored");
        Method idle = NetworkBroker.class.getDeclaredMethod("restoreIfIdle", int.class);
        idle.setAccessible(true);
        assert idle.invoke(null, WifiControl.generation() - 1).equals("newer session active");
        System.out.println("WIFI_HOLD_STATE_LOGIC_PASS_ONLY");
    }
}
