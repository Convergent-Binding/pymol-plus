// Fails unless C and C++ sources are compiled the way release wheels must be:
// optimised, with assert() compiled out. CMake's Release build type (what
// scikit-build-core used) defined NDEBUG; Bazel defines it only under
// --compilation_mode=opt, which .bazelrc sets for every build. Without it the
// extensions would ship unoptimised on Linux and Windows, with every assert()
// in layer*/ live and able to abort the interpreter.
#include <cstdio>

int main() {
#ifdef NDEBUG
  return 0;
#else
  std::fprintf(stderr, "NDEBUG is not defined: not a --compilation_mode=opt build\n");
  return 1;
#endif
}
