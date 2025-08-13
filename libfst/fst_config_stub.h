/* Stub configuration header for FST library */
#ifndef FST_CONFIG_STUB_H
#define FST_CONFIG_STUB_H

/* Always available */
#define HAVE_LIBZ 1
#define HAVE_INTTYPES_H 1
#define HAVE_STDINT_H 1
#define HAVE_STDLIB_H 1
#define HAVE_STRING_H 1
#define STDC_HEADERS 1

/* Platform-specific defines */
#ifdef _WIN32
    /* Windows-specific headers */
    #define HAVE_SYS_STAT_H 1
    #define HAVE_SYS_TYPES_H 1
    /* Do NOT define HAVE_ALLOCA_H on Windows - use malloc.h instead */
    /* Do NOT define HAVE_UNISTD_H on Windows - use fst_win_unistd.h instead */
    /* Do NOT define HAVE_DLFCN_H on Windows */
    /* Do NOT define HAVE_FSEEKO on Windows - use _fseeki64/_ftelli64 instead */
#else
    /* Unix/Linux headers */
    #define HAVE_ALLOCA_H 1
    #define HAVE_SYS_STAT_H 1
    #define HAVE_SYS_TYPES_H 1
    #define HAVE_UNISTD_H 1
    #define HAVE_DLFCN_H 1
    #define HAVE_MEMORY_H 1
    #define HAVE_FSEEKO 1
    #define _LARGEFILE_SOURCE 1
    #define _FILE_OFFSET_BITS 64
#endif

/* Package information */
#define PACKAGE_VERSION "1.0.0"
#define PACKAGE_NAME "libfst"

#endif /* FST_CONFIG_STUB_H */