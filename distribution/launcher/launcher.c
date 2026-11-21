/*
 * PyMOL-Open-Source: the app's launcher.
 *
 * The app is a folder holding this launcher and a python-build-standalone
 * runtime (see //distribution/bundle):
 *
 *   <root>/PyMOL-Open-Source[.exe]
 *   <root>/runtime/pythonw.exe       (Windows)
 *   <root>/runtime/bin/python3       (Linux, macOS)
 *
 * The launcher sets PYMOL_APP_ROOT to <root> and runs the runtime as
 *
 *   python -I -m pymol.startup_wrapper <its own arguments, unchanged>
 *
 * -I isolates the app from PYTHONPATH, PYTHONHOME and the user's
 * site-packages. It exits with Python's exit code. Without the runtime it
 * prints "PyMOL-Open-Source: runtime not found: <path>" to stderr and exits
 * 127.
 *
 * On Linux and macOS it replaces itself with Python (execv). On Windows it is
 * a GUI program, so no console window opens; it starts pythonw.exe with the
 * rest of its own command line verbatim (no re-quoting), hands on its
 * standard handles, so `-cq` output still reaches a pipe, and waits.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RUNTIME_NOT_FOUND 127

#ifdef _WIN32

#include <windows.h>

/* Writes a UTF-16 message to the inherited stderr, as UTF-8. */
static void print_error(const wchar_t *prefix, const wchar_t *path) {
  HANDLE err = GetStdHandle(STD_ERROR_HANDLE);
  if (err == NULL || err == INVALID_HANDLE_VALUE) return;
  size_t length = wcslen(prefix) + wcslen(path) + 2;
  wchar_t *message = malloc(length * sizeof(wchar_t));
  if (message == NULL) return;
  swprintf(message, length, L"%ls%ls\n", prefix, path);
  int size = WideCharToMultiByte(CP_UTF8, 0, message, -1, NULL, 0, NULL, NULL);
  char *utf8 = malloc(size);
  if (utf8 != NULL) {
    WideCharToMultiByte(CP_UTF8, 0, message, -1, utf8, size, NULL, NULL);
    DWORD written;
    WriteFile(err, utf8, (DWORD)strlen(utf8), &written, NULL);
    free(utf8);
  }
  free(message);
}

/* Returns the command line after the program name, without leading blanks. */
static const wchar_t *arguments_tail(const wchar_t *command_line) {
  const wchar_t *c = command_line;
  if (*c == L'"') {
    ++c;
    while (*c && *c != L'"') ++c;
    if (*c == L'"') ++c;
  } else {
    while (*c && *c != L' ' && *c != L'\t') ++c;
  }
  while (*c == L' ' || *c == L'\t') ++c;
  return c;
}

int wmain(void) {
  wchar_t root[32768];
  DWORD length = GetModuleFileNameW(NULL, root, sizeof(root) / sizeof(root[0]));
  if (length == 0 || length >= sizeof(root) / sizeof(root[0])) return RUNTIME_NOT_FOUND;
  wchar_t *separator = wcsrchr(root, L'\\');
  if (separator != NULL) *separator = L'\0';

  wchar_t python[32800];
  swprintf(python, sizeof(python) / sizeof(python[0]), L"%ls\\runtime\\pythonw.exe", root);
  if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES) {
    print_error(L"PyMOL-Open-Source: runtime not found: ", python);
    return RUNTIME_NOT_FOUND;
  }
  SetEnvironmentVariableW(L"PYMOL_APP_ROOT", root);

  const wchar_t *tail = arguments_tail(GetCommandLineW());
  size_t size = wcslen(python) + wcslen(tail) + 64;
  wchar_t *command = malloc(size * sizeof(wchar_t));
  if (command == NULL) return RUNTIME_NOT_FOUND;
  swprintf(command, size, L"\"%ls\" -I -m pymol.startup_wrapper %ls", python, tail);

  STARTUPINFOW startup = {sizeof(startup)};
  startup.dwFlags = STARTF_USESTDHANDLES;
  startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
  startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
  startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
  PROCESS_INFORMATION process;
  if (!CreateProcessW(python, command, NULL, NULL, TRUE, 0, NULL, NULL, &startup, &process)) {
    print_error(L"PyMOL-Open-Source: cannot start ", python);
    free(command);
    return RUNTIME_NOT_FOUND;
  }
  free(command);
  WaitForSingleObject(process.hProcess, INFINITE);
  DWORD exit_code = RUNTIME_NOT_FOUND;
  GetExitCodeProcess(process.hProcess, &exit_code);
  CloseHandle(process.hThread);
  CloseHandle(process.hProcess);
  return (int)exit_code;
}

#else /* Linux and macOS */

#include <limits.h>
#include <unistd.h>

#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

/* Writes the launcher's real directory into root; returns 0 on success. */
static int find_root(char root[PATH_MAX]) {
  char path[PATH_MAX];
#ifdef __APPLE__
  uint32_t size = sizeof(path);
  if (_NSGetExecutablePath(path, &size) != 0) return -1;
#else
  ssize_t length = readlink("/proc/self/exe", path, sizeof(path) - 1);
  if (length < 0) return -1;
  path[length] = '\0';
#endif
  if (realpath(path, root) == NULL) return -1;
  char *separator = strrchr(root, '/');
  if (separator == NULL) return -1;
  *separator = '\0';
  return 0;
}

int main(int argc, char **argv) {
  char root[PATH_MAX];
  if (find_root(root) != 0) {
    fprintf(stderr, "PyMOL-Open-Source: runtime not found: cannot locate the launcher\n");
    return RUNTIME_NOT_FOUND;
  }
  char python[PATH_MAX + 32];
  snprintf(python, sizeof(python), "%s/runtime/bin/python3", root);
  if (access(python, X_OK) != 0) {
    fprintf(stderr, "PyMOL-Open-Source: runtime not found: %s\n", python);
    return RUNTIME_NOT_FOUND;
  }
  setenv("PYMOL_APP_ROOT", root, 1);

  char **arguments = calloc((size_t)argc + 4, sizeof(char *));
  if (arguments == NULL) return RUNTIME_NOT_FOUND;
  arguments[0] = python;
  arguments[1] = "-I";
  arguments[2] = "-m";
  arguments[3] = "pymol.startup_wrapper";
  for (int i = 1; i < argc; ++i) arguments[i + 3] = argv[i];
  execv(python, arguments);
  fprintf(stderr, "PyMOL-Open-Source: cannot start %s\n", python);
  return RUNTIME_NOT_FOUND;
}

#endif
