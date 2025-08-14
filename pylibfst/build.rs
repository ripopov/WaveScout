use std::env;
use std::path::PathBuf;

fn main() {
    // Path to libfst source files
    let libfst_path = PathBuf::from("../libfst");
    
    // Build libfst C library
    cc::Build::new()
        .file(libfst_path.join("fstapi.c"))
        .file(libfst_path.join("fastlz.c"))
        .file(libfst_path.join("lz4.c"))
        .include(&libfst_path)
        // Define FST_CONFIG_INCLUDE to avoid config.h dependency
        .define("FST_CONFIG_INCLUDE", "\"fst_config_stub.h\"")
        // Define macros that would normally be in config.h
        .define("HAVE_LIBZ", "1")
        .define("HAVE_ALLOCA_H", "1")
        .define("HAVE_INTTYPES_H", "1")
        .define("HAVE_STDINT_H", "1")
        .define("HAVE_STDLIB_H", "1")
        .define("HAVE_STRING_H", "1")
        .define("HAVE_SYS_STAT_H", "1")
        .define("HAVE_SYS_TYPES_H", "1")
        .define("HAVE_UNISTD_H", "1")
        .define("HAVE_DLFCN_H", "1")
        .define("HAVE_MEMORY_H", "1")
        .define("STDC_HEADERS", "1")
        .define("_LARGEFILE_SOURCE", "1")
        .define("_FILE_OFFSET_BITS", "64")
        .flag_if_supported("-Wno-unused-parameter")
        .flag_if_supported("-Wno-unused-variable")
        .flag_if_supported("-Wno-unused-function")
        .flag_if_supported("-Wno-sign-compare")
        .flag_if_supported("-Wno-implicit-function-declaration")
        .compile("fst");
    
    // Link against zlib for compression support
    println!("cargo:rustc-link-lib=z");
    
    // Re-run build if C sources change
    println!("cargo:rerun-if-changed=../libfst/fstapi.c");
    println!("cargo:rerun-if-changed=../libfst/fastlz.c");
    println!("cargo:rerun-if-changed=../libfst/lz4.c");
    println!("cargo:rerun-if-changed=../libfst/fstapi.h");
}