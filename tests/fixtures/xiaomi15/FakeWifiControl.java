// Test boundary only. Never included in a production DEX.
package io.github.leekin2.xairdrop;
final class WifiControl {
    static int leaves, restores, epoch;
    static String answer = "left netId 7";
    static synchronized String leave() { leaves++; if (answer.startsWith("left")) epoch++; return answer; }
    static synchronized String restore() { restores++; return "restored"; }
    static synchronized int generation() { return epoch; }
    static synchronized String restoreIfStill(int seen) { return epoch == seen ? restore() : "newer session active"; }
}
