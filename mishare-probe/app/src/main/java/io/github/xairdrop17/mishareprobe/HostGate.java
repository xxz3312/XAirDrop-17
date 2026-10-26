package io.github.xairdrop17.mishareprobe;

public final class HostGate {
    public static final String HOST = "com.miui.mishare.connectivity";
    public static boolean accepts(String pkg, String process, int uid, long version, String context, String sha) {
        return HOST.equals(pkg) && (HOST.equals(process) || (HOST + ":ui").equals(process)) &&
                uid == 10132 && version == 50402 && "u:r:platform_app_36:s0:c512,c768".equals(context) &&
                "3ca8032f3c55d53e1912a44e42a17334ff739a064cf603e6cb9afb09d810905d".equals(sha);
    }
}
