/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAN_HDD_MISHARE_TXN_H
#define WLAN_HDD_MISHARE_TXN_H

#include <linux/types.h>

/* One START/STOP pair for one newly created, exclusively owned vdev.
 * Caller serializes every call and all field access with its owner lock.
 * No internal locks, timers, allocation, firmware calls or object ownership.
 * init is for fresh storage after vdev creation, NEVER timeout recovery/reset.
 * A new instance/reused vdev ID needs the real event stream drained first.
 */
enum mishare_txn_state {
    MISHARE_TXN_COLD,
    MISHARE_TXN_STARTED, /* START response only, not VDEV_UP or radio ready. */
    MISHARE_TXN_STOPPED, /* Terminal STOP response, not DOWN/delete/free proof. */
    MISHARE_TXN_QUARANTINED,
};

enum mishare_txn_command {
    MISHARE_TXN_NONE,
    MISHARE_TXN_START,
    MISHARE_TXN_STOP,
};

enum mishare_txn_delivery {
    MISHARE_TXN_NOT_SENT, /* Proven pre-send failure; never a generic QDF error. */
    MISHARE_TXN_ACCEPTED, /* Transport accepted, not firmware completion. */
    MISHARE_TXN_UNKNOWN, /* Command might have escaped: quarantine. */
};

struct mishare_vdev_txn {
    enum mishare_txn_state state;
    enum mishare_txn_command pending;
    u64 serial;
    u8 vdev_id;
    bool submitted;
    bool replied;
};

void mishare_vdev_txn_init(struct mishare_vdev_txn *txn, u8 vdev_id);
int mishare_vdev_txn_begin(struct mishare_vdev_txn *txn,
                          enum mishare_txn_command command, u64 *ticket);
int mishare_vdev_txn_submitted(struct mishare_vdev_txn *txn, u64 ticket,
                              enum mishare_txn_delivery delivery);
/* Firmware has no local ticket: match actual vdev ID and response kind only.
 * An early response is buffered until submission returns. No same-command reuse
 * after accepted submission, including after STOP; timeout never permits retry.
 */
int mishare_vdev_txn_response(struct mishare_vdev_txn *txn, u8 vdev_id,
                             enum mishare_txn_command command, bool success);
int mishare_vdev_txn_timeout(struct mishare_vdev_txn *txn, u64 ticket);

#endif
