/*
 * Fixed WSL test helper: vst-runner (997:988) -> vst-worker (999:989).
 * It does not accept a UID, GID, executable path, environment or shell command.
 */
#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <limits.h>
#include <linux/capability.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/syscall.h>
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
    char *end = NULL;
    long env_fd;
    long gate_fd;

    if (argc < 7 || argc > MAX_ARGUMENTS || strcmp(argv[1], "-I") != 0 ||
        strcmp(argv[2], "-c") != 0 || argv[3][0] == '\0') {
        return 0;
    }
    errno = 0;
    env_fd = strtol(argv[4], &end, 10);
    if (errno != 0 || end == argv[4] || *end != '\0' || env_fd < 3 || env_fd > INT_MAX) {
        return 0;
    }
    errno = 0;
    gate_fd = strtol(argv[5], &end, 10);
    if (errno != 0 || end == argv[5] || *end != '\0' || gate_fd < 3 || gate_fd > INT_MAX ||
        gate_fd == env_fd) {
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

static int clear_capability_sets(void) {
    struct __user_cap_header_struct header = {
        .version = _LINUX_CAPABILITY_VERSION_3,
        .pid = 0,
    };
    struct __user_cap_data_struct capabilities[_LINUX_CAPABILITY_U32S_3] = {{0}};

    if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0) != 0 ||
        syscall(SYS_capset, &header, capabilities) != 0) {
        return 0;
    }
    memset(capabilities, 0, sizeof(capabilities));
    if (syscall(SYS_capget, &header, capabilities) != 0) {
        return 0;
    }
    for (size_t index = 0; index < (size_t)_LINUX_CAPABILITY_U32S_3; ++index) {
        if (capabilities[index].effective != 0 ||
            capabilities[index].permitted != 0 ||
            capabilities[index].inheritable != 0) {
            return 0;
        }
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
    int env_source;
    int gate_source;
    int env_copy;
    int gate_copy;
    struct stat env_stat;
    struct stat gate_stat;

    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        (void)printf("schema=1 head=%s source_sha256=%s\n",
                     HELPER_BUILD_HEAD, HELPER_SOURCE_SHA256);
        return 0;
    }
    if (!valid_invocation(argc, argv)) {
        return refuse("usage is fixed: vst-s4-worker-exec -I -c SCRIPT ENV_FD GATE_FD ARG...");
    }
    env_source = (int)strtol(argv[4], NULL, 10);
    gate_source = (int)strtol(argv[5], NULL, 10);
    if (fstat(env_source, &env_stat) != 0 || fstat(gate_source, &gate_stat) != 0 ||
        !S_ISFIFO(env_stat.st_mode) || !S_ISFIFO(gate_stat.st_mode) ||
        env_stat.st_ino == gate_stat.st_ino) {
        return refuse("environment and release descriptors must be distinct pipes");
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
        !clear_capability_sets() ||
        prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        return refuse("could not irreversibly drop to the fixed worker identity and capabilities");
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
    env_copy = fcntl(env_source, F_DUPFD_CLOEXEC, 5);
    gate_copy = fcntl(gate_source, F_DUPFD_CLOEXEC, 5);
    if (env_copy < 0 || gate_copy < 0 || dup2(env_copy, 3) < 0 || dup2(gate_copy, 4) < 0 ||
        close_range(5U, UINT_MAX, 0U) != 0) {
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
    child_argv[1] = argv[1];
    child_argv[2] = argv[2];
    child_argv[3] = argv[3];
    child_argv[4] = "3";
    child_argv[5] = "4";
    for (int index = 6; index < argc; ++index) {
        child_argv[index] = argv[index];
    }
    child_argv[argc] = NULL;
    execve(PYTHON, child_argv, environ);
    (void)dprintf(STDERR_FILENO, "vst-s4-worker-exec: execve failed: %s\n", strerror(errno));
    free(child_argv);
    return 127;
}
