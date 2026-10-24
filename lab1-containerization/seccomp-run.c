#include <errno.h>
#include <seccomp.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/prctl.h>
#include <unistd.h>

static void check(int result, const char *operation) {
    if (result < 0) {
        errno = -result;
        perror(operation);
        exit(EXIT_FAILURE);
    }
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s PROFILE PROGRAM [ARGS...]\n", argv[0]);
        return EXIT_FAILURE;
    }

    FILE *profile = fopen(argv[1], "r");
    if (!profile) {
        perror("open profile");
        return EXIT_FAILURE;
    }

    // Permit other calls; return EPERM for names listed in the profile.
    scmp_filter_ctx filter = seccomp_init(SCMP_ACT_ALLOW);
    if (!filter) {
        fprintf(stderr, "Cannot allocate seccomp filter\n");
        return EXIT_FAILURE;
    }

    char name[64];
    unsigned int rules = 0;
    while (fscanf(profile, "%63s", name) == 1) {
        int syscall_number = seccomp_syscall_resolve_name(name);
        if (syscall_number == __NR_SCMP_ERROR) {
            fprintf(stderr, "Unknown syscall: %s\n", name);
            return EXIT_FAILURE;
        }
        check(seccomp_rule_add(filter, SCMP_ACT_ERRNO(EPERM), syscall_number, 0),
              "add seccomp rule");
        rules++;
    }
    if (ferror(profile) || rules == 0) {
        fprintf(stderr, "Profile is unreadable or empty\n");
        return EXIT_FAILURE;
    }
    fclose(profile);

    // Prevent gaining privileges through subsequent exec calls.
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == -1) {
        perror("set no_new_privs");
        return EXIT_FAILURE;
    }
    check(seccomp_load(filter), "load seccomp filter");
    seccomp_release(filter);

    // exec preserves the installed filter and the current PID.
    execvp(argv[2], &argv[2]);
    perror("exec program");
    return EXIT_FAILURE;
}
