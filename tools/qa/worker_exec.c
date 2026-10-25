/*
 * Fixed WSL test helper: vst-runner (997:988) -> vst-worker (999:989).
 * It does not accept a UID, GID, executable path, environment or shell command.
 */
#define _GNU_SOURCE

#include <errno.h>
#include <grp.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef HELPER_BUILD_HEAD
#error "helper build must bind a committed source HEAD"
#endif
#ifndef HELPER_SOURCE_SHA256
#error "helper build must bind the source digest"
#endif

extern char **environ;

enum {
    RUNNER_UID = 997,
    RUNNER_GID = 988,
    WORKER_UID = 999,
    WORKER_GID = 989,
    MAX_ARGUMENTS = 64,
    MAX_ARGUMENT_BYTES = 131072,
};

static const char PYTHON[] = "/usr/bin/python3.12";

static int refuse(const char *message) {
    (void)dprintf(STDERR_FILENO, "vst-s4-worker-exec: %s\n", message);
    return 126;
}

static int valid_invocation(int argc, char *const argv[]) {
    size_t total = 0;

    if (argc < 4 || argc > MAX_ARGUMENTS || strcmp(argv[1], "-I") != 0 ||
        strcmp(argv[2], "-c") != 0 || argv[3][0] == '\0') {
        return 0;
    }
    for (int index = 1; index < argc; ++index) {
        size_t length = strnlen(argv[index], MAX_ARGUMENT_BYTES + 1U);
        if (length >= MAX_ARGUMENT_BYTES || total > MAX_ARGUMENT_BYTES - length - 1U) {
            return 0;
        }
        total += length + 1U;
    }
    return 1;
}

int main(int argc, char **argv) {
    uid_t real_uid = (uid_t)-1;
    uid_t effective_uid = (uid_t)-1;
    uid_t saved_uid = (uid_t)-1;
    gid_t real_gid = (gid_t)-1;
    gid_t effective_gid = (gid_t)-1;
    gid_t saved_gid = (gid_t)-1;
    gid_t supplementary[1];
    int supplementary_count;
    char **child_argv;

    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        (void)printf("schema=1 head=%s source_sha256=%s\n",
                     HELPER_BUILD_HEAD, HELPER_SOURCE_SHA256);
        return 0;
    }
    if (!valid_invocation(argc, argv)) {
        return refuse("usage is fixed: vst-s4-worker-exec -I -c SCRIPT [ARG ...]");
    }
    if (getresuid(&real_uid, &effective_uid, &saved_uid) != 0 ||
        getresgid(&real_gid, &effective_gid, &saved_gid) != 0 ||
        real_uid != RUNNER_UID || real_gid != RUNNER_GID ||
        effective_uid != 0 || saved_uid != 0 ||
        effective_gid != RUNNER_GID || saved_gid != RUNNER_GID) {
        return refuse("caller identity or installed setuid state does not match 997:988");
    }

    if (setgroups(0, NULL) != 0 ||
        setresgid(WORKER_GID, WORKER_GID, WORKER_GID) != 0 ||
        setresuid(WORKER_UID, WORKER_UID, WORKER_UID) != 0 ||
        prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        return refuse("could not irreversibly drop to the fixed worker identity");
    }
    supplementary_count = getgroups(1, supplementary);
    if (getresuid(&real_uid, &effective_uid, &saved_uid) != 0 ||
        getresgid(&real_gid, &effective_gid, &saved_gid) != 0 ||
        real_uid != WORKER_UID ||
        effective_uid != WORKER_UID || saved_uid != WORKER_UID ||
        real_gid != WORKER_GID || effective_gid != WORKER_GID ||
        saved_gid != WORKER_GID || supplementary_count != 0) {
        return refuse("post-drop identity verification failed");
    }
    if (close_range(STDERR_FILENO + 1U, UINT_MAX, 0U) != 0) {
        return refuse("could not close inherited file descriptors");
    }

    if (clearenv() != 0 || setenv("PATH", "/usr/bin:/bin", 1) != 0 ||
        setenv("HOME", "/nonexistent", 1) != 0 ||
        setenv("LANG", "C.UTF-8", 1) != 0 ||
        setenv("LC_ALL", "C.UTF-8", 1) != 0 ||
        setenv("PYTHONNOUSERSITE", "1", 1) != 0 ||
        setenv("PYTHONDONTWRITEBYTECODE", "1", 1) != 0 ||
        setenv("TMPDIR", "/tmp", 1) != 0) {
        return refuse("could not create the fixed child environment");
    }
    (void)umask(0077);

    child_argv = calloc((size_t)argc + 1U, sizeof(*child_argv));
    if (child_argv == NULL) {
        return refuse("could not allocate child arguments");
    }
    child_argv[0] = (char *)PYTHON;
    for (int index = 1; index < argc; ++index) {
        child_argv[index] = argv[index];
    }
    child_argv[argc] = NULL;
    execve(PYTHON, child_argv, environ);
    (void)dprintf(STDERR_FILENO, "vst-s4-worker-exec: execve failed: %s\n", strerror(errno));
    free(child_argv);
    return 127;
}
