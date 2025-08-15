/* Stub configuration header for FST API */
#ifndef FST_CONFIG_STUB_H
#define FST_CONFIG_STUB_H

/* Define necessary macros for FST API compilation */
#define HAVE_LIBZ 1
#define HAVE_INTTYPES_H 1
#define HAVE_STDINT_H 1
#define HAVE_STDLIB_H 1
#define HAVE_STRING_H 1
#define HAVE_SYS_STAT_H 1
#define HAVE_SYS_TYPES_H 1
#define HAVE_MEMORY_H 1
#define STDC_HEADERS 1
#define _LARGEFILE_SOURCE 1
#define _FILE_OFFSET_BITS 64

#ifdef _WIN32
#define HAVE_FCNTL_H 1
#define HAVE_IO_H 1
#define HAVE_PROCESS_H 1
#else
#define HAVE_UNISTD_H 1
#define HAVE_ALLOCA_H 1
#define HAVE_DLFCN_H 1
#endif

#endif /* FST_CONFIG_STUB_H */