#!/system/bin/sh
# Explicit manager action only. No driver action runs during installation/boot.
MODDIR=${0%/*}
/system/bin/sh "$MODDIR/popsicle-stock-cnssctl.sh" apply
