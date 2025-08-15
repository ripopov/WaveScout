use std::env;
use std::path::PathBuf;

fn main() {
    // Path to libfst source files
    let libfst_path = PathBuf::from("../libfst");
    
    // Build libfst C library
    let mut build = cc::Build::new();
    
    // Add include path for zlib on Windows
    #[cfg(target_os = "windows")]
    {
        if let Ok(vcpkg_root) = env::var("VCPKG_ROOT") {
            let vcpkg_installed = PathBuf::from(&vcpkg_root)
                .parent()
                .map(|p| p.join("vcpkg_installed").join("x64-windows").join("include"))
                .unwrap_or_else(|| PathBuf::from("vcpkg_installed/x64-windows/include"));
            
            if vcpkg_installed.exists() {
                build.include(&vcpkg_installed);
                println!("cargo:warning=Added vcpkg include path: {}", vcpkg_installed.display());
            }
        }
        // Also try project-relative path
        let project_vcpkg = PathBuf::from("../vcpkg_installed/x64-windows/include");
        if project_vcpkg.exists() {
            build.include(&project_vcpkg);
            println!("cargo:warning=Added project vcpkg include path: {}", project_vcpkg.display());
        }
    }
    
    build
        .file(libfst_path.join("fstapi.c"))
        .file(libfst_path.join("fastlz.c"))
        .file(libfst_path.join("lz4.c"))
        .include(&libfst_path)
        // Define FST_CONFIG_INCLUDE to avoid config.h dependency
        .define("FST_CONFIG_INCLUDE", "\"fst_config_stub.h\"");
        // .define("DEBUG_HIERARCHY", "1");  // Disable debug output
        
    // Platform-specific defines
    #[cfg(target_os = "windows")]
    {
        build
            .define("HAVE_LIBZ", "1")
            .define("HAVE_INTTYPES_H", "1")
            .define("HAVE_STDINT_H", "1")
            .define("HAVE_STDLIB_H", "1")
            .define("HAVE_STRING_H", "1")
            .define("HAVE_SYS_STAT_H", "1")
            .define("HAVE_SYS_TYPES_H", "1")
            .define("HAVE_MEMORY_H", "1")
            .define("STDC_HEADERS", "1")
            .define("_LARGEFILE_SOURCE", "1")
            .define("_FILE_OFFSET_BITS", "64");
    }
    
    #[cfg(not(target_os = "windows"))]
    {
        build
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
            .flag_if_supported("-Wno-implicit-function-declaration");
    }
    
    build.compile("fst");
    
    // Link against zlib for compression support
    #[cfg(target_os = "windows")]
    {
        // On Windows, try to find zlib through vcpkg or system paths
        if let Ok(vcpkg_root) = env::var("VCPKG_ROOT") {
            let vcpkg_installed = PathBuf::from(&vcpkg_root)
                .parent()
                .map(|p| p.join("vcpkg_installed").join("x64-windows").join("lib"))
                .unwrap_or_else(|| PathBuf::from("vcpkg_installed/x64-windows/lib"));
            
            if vcpkg_installed.exists() {
                println!("cargo:rustc-link-search={}", vcpkg_installed.display());
            }
        }
        // Also try project-relative path
        let project_vcpkg_lib = PathBuf::from("../vcpkg_installed/x64-windows/lib");
        if project_vcpkg_lib.exists() {
            println!("cargo:rustc-link-search={}", project_vcpkg_lib.display());
        }
        println!("cargo:rustc-link-lib=zlib");
    }
    
    #[cfg(not(target_os = "windows"))]
    {
        println!("cargo:rustc-link-lib=z");
    }
    
    // Re-run build if C sources change
    println!("cargo:rerun-if-changed=../libfst/fstapi.c");
    println!("cargo:rerun-if-changed=../libfst/fastlz.c");
    println!("cargo:rerun-if-changed=../libfst/lz4.c");
    println!("cargo:rerun-if-changed=../libfst/fstapi.h");
}