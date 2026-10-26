// SPDX-License-Identifier: GPL-2.0-only
/* START/STOP transaction accounting only; no runtime/MLME/WMI bridge yet. */
#include <linux/errno.h>
#include "wlan_hdd_mishare_txn.h"

void mishare_vdev_txn_init(struct mishare_vdev_txn *txn, u8 vdev_id)
{
    *txn = (struct mishare_vdev_txn) {
        .state = MISHARE_TXN_COLD,
        .vdev_id = vdev_id,
    };
}

static int mishare_txn_quarantine(struct mishare_vdev_txn *txn, int error)
{
    txn->state = MISHARE_TXN_QUARANTINED;
    txn->pending = MISHARE_TXN_NONE;
    return error;
}

static int mishare_txn_match(struct mishare_vdev_txn *txn, u64 ticket)
{
    if (!txn || !ticket)
        return -EINVAL;
    if (txn->state == MISHARE_TXN_QUARANTINED)
        return -EUCLEAN;
    if (ticket != txn->serial)
        return -ESTALE;
    if (txn->pending == MISHARE_TXN_NONE)
        return -EALREADY;
    return 0;
}

static void mishare_txn_complete(struct mishare_vdev_txn *txn)
{
    txn->state = txn->pending == MISHARE_TXN_START ?
                 MISHARE_TXN_STARTED : MISHARE_TXN_STOPPED;
    txn->pending = MISHARE_TXN_NONE;
}

int mishare_vdev_txn_begin(struct mishare_vdev_txn *txn,
                          enum mishare_txn_command command, u64 *ticket)
{
    if (!ticket)
        return -EINVAL;
    *ticket = 0;
    if (!txn || (command != MISHARE_TXN_START && command != MISHARE_TXN_STOP))
        return -EINVAL;
    if (txn->state == MISHARE_TXN_QUARANTINED)
        return -EUCLEAN;
    if (txn->pending != MISHARE_TXN_NONE)
        return -EBUSY;
    if (txn->state == MISHARE_TXN_STOPPED)
        return -ESHUTDOWN;
    if ((command == MISHARE_TXN_START && txn->state != MISHARE_TXN_COLD) ||
        (command == MISHARE_TXN_STOP && txn->state != MISHARE_TXN_STARTED))
        return -EALREADY;
    if (txn->serial == ~(u64)0)
        return mishare_txn_quarantine(txn, -EOVERFLOW);
    txn->pending = command;
    txn->submitted = false;
    txn->replied = false;
    *ticket = ++txn->serial;
    return 0;
}

int mishare_vdev_txn_submitted(struct mishare_vdev_txn *txn, u64 ticket,
                              enum mishare_txn_delivery delivery)
{
    int ret = mishare_txn_match(txn, ticket);

    if (ret)
        return ret;
    if (delivery != MISHARE_TXN_NOT_SENT && delivery != MISHARE_TXN_ACCEPTED &&
        delivery != MISHARE_TXN_UNKNOWN)
        return -EINVAL;
    if (txn->submitted)
        return -EALREADY;
    if (delivery == MISHARE_TXN_UNKNOWN)
        return mishare_txn_quarantine(txn, -EIO);
    if (delivery == MISHARE_TXN_NOT_SENT) {
        if (txn->replied)
            return mishare_txn_quarantine(txn, -EPROTO);
        txn->pending = MISHARE_TXN_NONE;
        return 0;
    }
    txn->submitted = true;
    if (txn->replied)
        mishare_txn_complete(txn);
    return 0;
}

int mishare_vdev_txn_response(struct mishare_vdev_txn *txn, u8 vdev_id,
                             enum mishare_txn_command command, bool success)
{
    if (!txn || (command != MISHARE_TXN_START && command != MISHARE_TXN_STOP))
        return -EINVAL;
    if (txn->vdev_id != vdev_id)
        return -ENOENT;
    if (txn->state == MISHARE_TXN_QUARANTINED)
        return -EUCLEAN;
    if (txn->pending == MISHARE_TXN_NONE)
        return -EALREADY;
    if (txn->pending != command)
        return -ENOENT;
    if (txn->replied) {
        if (!success)
            return mishare_txn_quarantine(txn, -EPROTO);
        return -EALREADY;
    }
    if (!success)
        return mishare_txn_quarantine(txn, -EREMOTEIO);
    txn->replied = true;
    if (txn->submitted)
        mishare_txn_complete(txn);
    return 0;
}

int mishare_vdev_txn_timeout(struct mishare_vdev_txn *txn, u64 ticket)
{
    int ret = mishare_txn_match(txn, ticket);

    if (ret)
        return ret;
    return mishare_txn_quarantine(txn, -ETIMEDOUT);
}
