/* Load/link checks only. Never call XOS entry points or Binder APIs. */
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc != 2 || argv[1][0] != '/' || strstr(argv[1], "/../")) {
        fputs("Usage: xos-loader-probe /absolute/reference/directory\n", stderr);
        return 2;
    }
    const char *libraries[] = {"com.domestic.xoscomm-V1-ndk.so", "libxos.so"};
    void *handles[2] = {NULL, NULL};
    int result = 0;
    for (unsigned i = 0; i < 2; ++i) {
        char path[4096];
        int length = snprintf(path, sizeof(path), "%s/%s", argv[1], libraries[i]);
        if (length < 0 || (size_t)length >= sizeof(path)) return 2;
        dlerror();
        handles[i] = dlopen(path, RTLD_NOW | RTLD_LOCAL);
        if (!handles[i]) {
            fprintf(stderr, "DLOPEN_FAIL %s: %s\n", libraries[i], dlerror());
            result = 1;
            break;
        }
        printf("DLOPEN_OK %s\n", libraries[i]);
        fflush(stdout);
    }
    const char *symbols[] = {"domestic_xos_start", "domestic_xoscomm_stop",
                            "domestic_xoscomm_get_status", "domestic_xoscomm_set_aggregation_config"};
    if (!result) {
        for (unsigned i = 0; i < sizeof(symbols) / sizeof(symbols[0]); ++i) {
            dlerror();
            void *address = dlsym(handles[1], symbols[i]);
            const char *error = dlerror();
            if (error || !address) {
                fprintf(stderr, "DLSYM_FAIL %s: %s\n", symbols[i], error ? error : "null address");
                result = 1;
            } else {
                printf("DLSYM_OK %s (not called)\n", symbols[i]);
            }
        }
    }
    for (int i = 1; i >= 0; --i) {
        if (handles[i] && dlclose(handles[i])) {
            fprintf(stderr, "DLCLOSE_FAIL %s: %s\n", libraries[i], dlerror());
            result = 1;
        }
    }
    if (!result) puts("PASS_DLOPEN_DLSYM_ONLY_NO_SERVICE_OR_RADIO_CALLS");
    return result;
}
