#!/system/bin/sh
MODDIR=${0%/*}
exec /system/bin/sh "$MODDIR/stagectl.sh" check
