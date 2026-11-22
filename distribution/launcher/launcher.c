/**
 * @file launcher.c
 * PyMOL-Open-Source: the app's launcher.
 *
 * The app is a folder holding this launcher and a python-build-standalone
 * runtime (see //distribution/bundle):
 *
 *   <root>/PyMOL-Open-Source[.exe]
 *   <root>/runtime/pythonw.exe       (Windows)
 *   <root>/runtime/bin/python3       (Linux, macOS)
 *
 * Inside a macOS app bundle the launcher is Contents/MacOS/PyMOL-Open-Source
 * and <root> is Contents/Resources.
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
 * On Linux it replaces itself with Python (execv), with bytecode in the
 * user's cache (-X pycache_prefix), as the packages install into /opt,
 * which users cannot write. On Windows it is a GUI
 * program, so no console window opens; it starts pythonw.exe with the rest
 * of its own command line verbatim (no re-quoting), hands on its standard
 * handles, so `-cq` output still reaches a pipe, and waits. On macOS it loads
 * <root>/runtime/lib/libpython3.X.dylib and runs PyMOL in its own process,
 * with the same isolation: macOS shows a process as an app only while its
 * executable is the bundle's own, for the Dock icon and the app menu.
 *
 * @copyright Copyright (c) 2026, Hannah Kullik.
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/** The exit code when the runtime cannot be started. */
#define RUNTIME_NOT_FOUND 127

#ifdef _WIN32

#include <windows.h>

/** Writes a UTF-16 message to the inherited stderr, as UTF-8. */
static void print_error(const wchar_t* prefix, const wchar_t* path)
{
  HANDLE err = GetStdHandle(STD_ERROR_HANDLE);
  if(err == NULL || err == INVALID_HANDLE_VALUE) {
    return;
  }
  size_t length = wcslen(prefix) + wcslen(path) + 2;
  wchar_t* message = malloc(length * sizeof(wchar_t));
  if(message == NULL) {
    return;
  }
  swprintf(message, length, L"%ls%ls\n", prefix, path);
  int size = WideCharToMultiByte(CP_UTF8, 0, message, -1, NULL, 0, NULL, NULL);
  char* utf8 = malloc(size);
  if(utf8 != NULL) {
    WideCharToMultiByte(CP_UTF8, 0, message, -1, utf8, size, NULL, NULL);
    DWORD written;
    WriteFile(err, utf8, (DWORD) strlen(utf8), &written, NULL);
    free(utf8);
  }
  free(message);
}

/** Returns the command line after the program name, without leading blanks. */
static const wchar_t* arguments_tail(const wchar_t* command_line)
{
  const wchar_t* c = command_line;
  if(*c == L'"') {
    ++c;
    while(*c && *c != L'"') {
      ++c;
    }
    if(*c == L'"') {
      ++c;
    }
  } else {
    while(*c && *c != L' ' && *c != L'\t') {
      ++c;
    }
  }
  while(*c == L' ' || *c == L'\t') {
    ++c;
  }
  return c;
}

int wmain(void)
{
  wchar_t root[32768];
  DWORD length = GetModuleFileNameW(NULL, root, sizeof(root) / sizeof(root[0]));
  if(length == 0 || length >= sizeof(root) / sizeof(root[0])) {
    return RUNTIME_NOT_FOUND;
  }
  wchar_t* separator = wcsrchr(root, L'\\');
  if(separator != NULL) {
    *separator = L'\0';
  }

  wchar_t python[32800];
  swprintf(python, sizeof(python) / sizeof(python[0]),
           L"%ls\\runtime\\pythonw.exe", root);
  if(GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES) {
    print_error(L"PyMOL-Open-Source: runtime not found: ", python);
    return RUNTIME_NOT_FOUND;
  }
  SetEnvironmentVariableW(L"PYMOL_APP_ROOT", root);

  const wchar_t* tail = arguments_tail(GetCommandLineW());
  size_t size = wcslen(python) + wcslen(tail) + 64;
  wchar_t* command = malloc(size * sizeof(wchar_t));
  if(command == NULL) {
    return RUNTIME_NOT_FOUND;
  }
  swprintf(command, size, L"\"%ls\" -I -m pymol.startup_wrapper %ls", python,
           tail);

  STARTUPINFOW startup = {sizeof(startup)};
  startup.dwFlags = STARTF_USESTDHANDLES;
  startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
  startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
  startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
  PROCESS_INFORMATION process;
  if(!CreateProcessW(python, command, NULL, NULL, TRUE, 0, NULL, NULL, &startup,
                     &process)) {
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
  return (int) exit_code;
}

#else

/** The Linux and macOS launcher follows. */

#include <limits.h>
#include <unistd.h>

#ifdef __APPLE__
#include <Python.h>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <sys/stat.h>
#endif

/** Writes the launcher's real directory into folder; returns 0 on success. */
static int find_launcher_folder(char folder[PATH_MAX])
{
  char path[PATH_MAX];
#ifdef __APPLE__
  uint32_t size = sizeof(path);
  if(_NSGetExecutablePath(path, &size) != 0) {
    return -1;
  }
#else
  ssize_t length = readlink("/proc/self/exe", path, sizeof(path) - 1);
  if(length < 0) {
    return -1;
  }
  path[length] = '\0';
#endif
  if(realpath(path, folder) == NULL) {
    return -1;
  }
  char* separator = strrchr(folder, '/');
  if(separator == NULL) {
    return -1;
  }
  *separator = '\0';
  return 0;
}

#ifdef __APPLE__

/** The CPython functions the macOS launcher looks up in libpython. */
typedef struct {
  void (*init_isolated_pre_config)(PyPreConfig*);
  PyStatus (*pre_initialize)(const PyPreConfig*);
  void (*init_isolated_config)(PyConfig*);
  PyStatus (*set_string)(PyConfig*, wchar_t**, const wchar_t*);
  PyStatus (*set_bytes_argv)(PyConfig*, Py_ssize_t, char* const*);
  PyStatus (*initialize_from_config)(const PyConfig*);
  int (*status_exception)(PyStatus);
  void (*exit_status_exception)(PyStatus);
  void (*config_clear)(PyConfig*);
  int (*run_main)(void);
  wchar_t* (*decode_locale)(const char*, size_t*);
} python_api;

/**
 * Finds the app root: Contents/Resources when the launcher sits in an app
 * bundle's Contents/MacOS, else the launcher's own folder.
 *
 * @param folder The launcher's real folder.
 * @param root Receives the app root.
 * @return 0 on success.
 */
static int find_root(const char* folder, char root[PATH_MAX])
{
  char resources[PATH_MAX + 32];
  snprintf(resources, sizeof(resources), "%s/../Resources/runtime", folder);
  struct stat info;
  if(stat(resources, &info) == 0 && S_ISDIR(info.st_mode)) {
    snprintf(resources, sizeof(resources), "%s/../Resources", folder);
    return realpath(resources, root) == NULL ? -1 : 0;
  }
  snprintf(root, PATH_MAX, "%s", folder);
  return 0;
}

/**
 * Looks up the CPython functions the launcher calls.
 *
 * @param library The loaded libpython.
 * @param api Receives the functions.
 * @return 0 when every function was found.
 */
static int load_python_api(void* library, python_api* api)
{
  api->init_isolated_pre_config =
      dlsym(library, "PyPreConfig_InitIsolatedConfig");
  api->pre_initialize = dlsym(library, "Py_PreInitialize");
  api->init_isolated_config = dlsym(library, "PyConfig_InitIsolatedConfig");
  api->set_string = dlsym(library, "PyConfig_SetString");
  api->set_bytes_argv = dlsym(library, "PyConfig_SetBytesArgv");
  api->initialize_from_config = dlsym(library, "Py_InitializeFromConfig");
  api->status_exception = dlsym(library, "PyStatus_Exception");
  api->exit_status_exception = dlsym(library, "Py_ExitStatusException");
  api->config_clear = dlsym(library, "PyConfig_Clear");
  api->run_main = dlsym(library, "Py_RunMain");
  api->decode_locale = dlsym(library, "Py_DecodeLocale");
  return api->init_isolated_pre_config && api->pre_initialize &&
                 api->init_isolated_config && api->set_string &&
                 api->set_bytes_argv && api->initialize_from_config &&
                 api->status_exception && api->exit_status_exception &&
                 api->config_clear && api->run_main && api->decode_locale
             ? 0
             : -1;
}

/**
 * Runs PyMOL in this process with the runtime under root.
 *
 * Like `python -I`: isolated from PYTHON* variables and the user's
 * site-packages, in UTF-8 mode, which an isolated pre-configuration leaves
 * off; an app started from the Finder has no LANG and would read files as
 * ASCII without it. Bytecode goes to ~/Library/Caches/PyMOL-Open-Source, as
 * writing into the signed app would break its signature.
 *
 * @param api The CPython functions.
 * @param root The app root.
 * @param argc The launcher's argument count.
 * @param argv The launcher's arguments, which become sys.argv.
 * @return Python's exit code.
 */
static int run_python(const python_api* api, const char* root, int argc,
                      char** argv)
{
  PyPreConfig pre_config;
  api->init_isolated_pre_config(&pre_config);
  pre_config.utf8_mode = 1;
  PyStatus status = api->pre_initialize(&pre_config);
  if(api->status_exception(status)) {
    api->exit_status_exception(status);
  }
  char home[PATH_MAX + 16];
  snprintf(home, sizeof(home), "%s/runtime", root);
  const char* user_home = getenv("HOME");
  char cache[PATH_MAX + 64];
  snprintf(cache, sizeof(cache), "%s/Library/Caches/PyMOL-Open-Source/pycache",
           user_home ? user_home : "/tmp");

  wchar_t* wide_home = api->decode_locale(home, NULL);
  wchar_t* wide_cache = api->decode_locale(cache, NULL);
  if(wide_home == NULL || wide_cache == NULL) {
    fprintf(stderr, "PyMOL-Open-Source: cannot decode %s or %s\n", home, cache);
    return RUNTIME_NOT_FOUND;
  }
  PyConfig config;
  api->init_isolated_config(&config);
  /** Like the python command: Ctrl+C and the C streams behave as usual. */
  config.install_signal_handlers = 1;
  config.configure_c_stdio = 1;
  config.parse_argv = 0;
  status = api->set_string(&config, &config.home, wide_home);
  if(!api->status_exception(status)) {
    status = api->set_string(&config, &config.pycache_prefix, wide_cache);
  }
  if(!api->status_exception(status)) {
    status =
        api->set_string(&config, &config.run_module, L"pymol.startup_wrapper");
  }
  if(!api->status_exception(status)) {
    status = api->set_bytes_argv(&config, argc, argv);
  }
  if(!api->status_exception(status)) {
    status = api->initialize_from_config(&config);
  }
  api->config_clear(&config);
  if(api->status_exception(status)) {
    api->exit_status_exception(status);
  }
  return api->run_main();
}

int main(int argc, char** argv)
{
  char folder[PATH_MAX];
  char root[PATH_MAX];
  if(find_launcher_folder(folder) != 0 || find_root(folder, root) != 0) {
    fprintf(
        stderr,
        "PyMOL-Open-Source: runtime not found: cannot locate the launcher\n");
    return RUNTIME_NOT_FOUND;
  }
  char library_path[PATH_MAX + 64];
  snprintf(library_path, sizeof(library_path),
           "%s/runtime/lib/libpython%d.%d.dylib", root, PY_MAJOR_VERSION,
           PY_MINOR_VERSION);
  /** RTLD_GLOBAL: extension modules find CPython's symbols in this image. */
  void* library = dlopen(library_path, RTLD_NOW | RTLD_GLOBAL);
  python_api api;
  if(library == NULL || load_python_api(library, &api) != 0) {
    fprintf(stderr, "PyMOL-Open-Source: runtime not found: %s\n", library_path);
    return RUNTIME_NOT_FOUND;
  }
  setenv("PYMOL_APP_ROOT", root, 1);
  return run_python(&api, root, argc, argv);
}

#else

int main(int argc, char** argv)
{
  char root[PATH_MAX];
  if(find_launcher_folder(root) != 0) {
    fprintf(
        stderr,
        "PyMOL-Open-Source: runtime not found: cannot locate the launcher\n");
    return RUNTIME_NOT_FOUND;
  }
  char python[PATH_MAX + 32];
  snprintf(python, sizeof(python), "%s/runtime/bin/python3", root);
  if(access(python, X_OK) != 0) {
    fprintf(stderr, "PyMOL-Open-Source: runtime not found: %s\n", python);
    return RUNTIME_NOT_FOUND;
  }
  setenv("PYMOL_APP_ROOT", root, 1);

  const char* cache_home = getenv("XDG_CACHE_HOME");
  const char* user_home = getenv("HOME");
  char pycache[PATH_MAX + 64];
  if(cache_home != NULL && cache_home[0] == '/') {
    snprintf(pycache, sizeof(pycache),
             "pycache_prefix=%s/PyMOL-Open-Source/pycache", cache_home);
  } else {
    snprintf(pycache, sizeof(pycache),
             "pycache_prefix=%s/.cache/PyMOL-Open-Source/pycache",
             user_home != NULL ? user_home : "/tmp");
  }

  char** arguments = calloc((size_t) argc + 6, sizeof(char*));
  if(arguments == NULL) {
    return RUNTIME_NOT_FOUND;
  }
  arguments[0] = python;
  arguments[1] = "-I";
  arguments[2] = "-X";
  arguments[3] = pycache;
  arguments[4] = "-m";
  arguments[5] = "pymol.startup_wrapper";
  for(int i = 1; i < argc; ++i) {
    arguments[i + 5] = argv[i];
  }
  execv(python, arguments);
  fprintf(stderr, "PyMOL-Open-Source: cannot start %s\n", python);
  return RUNTIME_NOT_FOUND;
}

#endif

#endif
