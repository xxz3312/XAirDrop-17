// SPDX-License-Identifier: GPL-2.0-only
#define ACTION_TX_TEST
#include "../native/wireless/action_tx.c"
#include <assert.h>
int main(void)
{
    /* Deliberately overlong interface fails before any socket/radio access.
     * Valid bounds must reach interface validation (1), not usage failure (2). */
    char *args[] = {"action-tx", "awdl-mgmt-listen", "--dev",
                   "invalid-interface-name-that-exceeds-IFNAMSIZ",
                   "--seconds", "60", "--max-frames", "1000"};
    assert(awdl_mgmt_main(8, args) == 1);
    args[7] = "10000";
    assert(awdl_mgmt_main(8, args) == 2);
    args[7] = "0";
    assert(awdl_mgmt_main(8, args) == 2);
    args[7] = "10";
    assert(awdl_mgmt_main(8, args) == 1);
    puts("MGMT_CLI_BOUNDARIES_PASS_NO_RADIO");
    return 0;
}
