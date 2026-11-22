/**
 * @file fake_python.c
 * Test double of the bundled Python for launcher_test.py.
 *
 * Prints the arguments after its program name and PYMOL_APP_ROOT as one
 * JSON object in UTF-8, then exits with FAKE_EXIT_CODE (0 when unset).
 *
 * @copyright Copyright (c) 2026, Hannah Kullik.
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#endif

/** Prints a UTF-8 string as a JSON string literal. */
static void print_json_string(const char* text)
{
  putchar('"');
  for(const unsigned char* c = (const unsigned char*) text; *c; ++c) {
    if(*c == '"' || *c == '\\') {
      printf("\\%c", *c);
    } else if(*c < 0x20) {
      printf("\\u%04x", *c);
    } else {
      putchar(*c);
    }
  }
  putchar('"');
}

#ifdef _WIN32
/** Returns a UTF-8 copy of a UTF-16 string; the caller frees it. */
static char* to_utf8(const wchar_t* text)
{
  int size = WideCharToMultiByte(CP_UTF8, 0, text, -1, NULL, 0, NULL, NULL);
  char* utf8 = malloc(size);
  WideCharToMultiByte(CP_UTF8, 0, text, -1, utf8, size, NULL, NULL);
  return utf8;
}

int wmain(int argc, wchar_t** argv)
{
  const wchar_t* root = _wgetenv(L"PYMOL_APP_ROOT");
  const wchar_t* exit_code = _wgetenv(L"FAKE_EXIT_CODE");
  printf("{\"args\": [");
  for(int i = 1; i < argc; ++i) {
    char* arg = to_utf8(argv[i]);
    if(i > 1) {
      printf(", ");
    }
    print_json_string(arg);
    free(arg);
  }
  printf("], \"app_root\": ");
  if(root) {
    char* utf8_root = to_utf8(root);
    print_json_string(utf8_root);
    free(utf8_root);
  } else {
    printf("null");
  }
  printf("}\n");
  fflush(stdout);
  return exit_code ? _wtoi(exit_code) : 0;
}
#else
int main(int argc, char** argv)
{
  const char* root = getenv("PYMOL_APP_ROOT");
  const char* exit_code = getenv("FAKE_EXIT_CODE");
  printf("{\"args\": [");
  for(int i = 1; i < argc; ++i) {
    if(i > 1) {
      printf(", ");
    }
    print_json_string(argv[i]);
  }
  printf("], \"app_root\": ");
  if(root) {
    print_json_string(root);
  } else {
    printf("null");
  }
  printf("}\n");
  fflush(stdout);
  return exit_code ? atoi(exit_code) : 0;
}
#endif
