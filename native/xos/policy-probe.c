/* Query live SELinux policy. Never change credentials, rules or call XOS/Binder. */
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

typedef int (*check_fn)(const char *, const char *, const char *, const char *, void *);
typedef void *(*handle_fn)(void);
typedef int (*lookup_fn)(void *, char **, const char *, int);
typedef void (*free_fn)(char *);
typedef int (*int_fn)(void);

int main(int argc, char **argv) {
    const char *source = "u:r:platform_app_36:s0:c512,c768";
    const char *server = "u:r:ksu:s0";
    if (argc != 2 || strcmp(argv[1], source)) {
        fputs("Expected the captured MiShare context as the sole argument\n", stderr);
        return 2;
    }
    void *lib = dlopen("libselinux.so", RTLD_NOW | RTLD_LOCAL);
    if (!lib) { fprintf(stderr, "LIBSELINUX_LOAD_ERROR %s\n", dlerror()); return 2; }
    check_fn check = (check_fn)dlsym(lib, "selinux_check_access");
    handle_fn handle = (handle_fn)dlsym(lib, "selinux_android_service_context_handle");
    lookup_fn lookup = (lookup_fn)dlsym(lib, "selabel_lookup");
    free_fn free_context = (free_fn)dlsym(lib, "freecon");
    int_fn enabled = (int_fn)dlsym(lib, "is_selinux_enabled");
    int_fn enforce = (int_fn)dlsym(lib, "security_getenforce");
    if (!check || !handle || !lookup || !free_context || !enabled || !enforce) {
        fputs("LIBSELINUX_API_MISSING\n", stderr); return 2;
    }
    if (enabled() != 1 || enforce() != 1) {
        fputs("ERROR_SELINUX_NOT_ENFORCING\n", stderr); return 2;
    }
    void *labels = handle();
    char *service_context = NULL;
    if (!labels || lookup(labels, &service_context, "com.domestic.xoscomm.IDomesticXOsComm/default", 0) || !service_context) {
        fprintf(stderr, "SERVICE_CONTEXT_LOOKUP_ERROR errno=%d\n", errno); return 2;
    }
    printf("FRESH_SERVICE_CONTEXT=%s\n", service_context);
    struct query { const char *name, *source, *target, *class_name, *permission; } queries[] = {
        {"service_find", source, service_context, "service_manager", "find"},
        {"app_to_server_call", source, server, "binder", "call"},
        {"app_to_server_transfer", source, server, "binder", "transfer"},
        {"server_to_app_call", server, source, "binder", "call"},
        {"server_to_app_transfer", server, source, "binder", "transfer"},
        {"app_use_server_fd", source, server, "fd", "use"},
    };
    unsigned denied = 0, errors = 0;
    for (unsigned i = 0; i < sizeof(queries) / sizeof(queries[0]); ++i) {
        struct query *q = &queries[i];
        errno = 0;
        int rc = check(q->source, q->target, q->class_name, q->permission, NULL);
        int saved_errno = errno;
        const char *result = rc == 0 ? "ALLOW" : saved_errno == EACCES ? "DENY" : "ERROR";
        if (rc && saved_errno == EACCES) ++denied;
        else if (rc) ++errors;
        printf("CHECK %s result=%s rc=%d errno=%d source=%s target=%s class=%s permission=%s\n",
               q->name, result, rc, saved_errno, q->source, q->target, q->class_name, q->permission);
    }
    free_context(service_context);
    printf("SUMMARY denied=%u errors=%u\n", denied, errors);
    puts(errors ? "ERROR_POLICY_QUERY" : denied ? "POLICY_DENIALS_OBSERVED" : "POLICY_ALLOW_CANDIDATES_ONLY");
    /* No close of Android's process-global label handle. Process exit owns cleanup. */
    return errors ? 2 : denied ? 1 : 0;
}
