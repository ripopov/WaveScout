#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <vector>
#include <string>
#include <map>
#include <iostream>

extern "C" {
#include "fstapi.h"
}

struct TestContext {
    std::map<fstHandle, std::string> signals;
    std::vector<std::string> scopes;
    int value_change_count = 0;
    uint64_t last_time = 0;
    bool test_passed = true;
};

void value_change_callback(void* user_data, uint64_t time, fstHandle facidx, const unsigned char* value) {
    TestContext* ctx = static_cast<TestContext*>(user_data);
    ctx->value_change_count++;
    ctx->last_time = time;
    
    if (ctx->signals.find(facidx) != ctx->signals.end()) {
        printf("  Time=%llu Signal='%s' Value='%s'\n", 
               (unsigned long long)time, 
               ctx->signals[facidx].c_str(), 
               value ? (const char*)value : "NULL");
    }
}

bool test_fst_reader(const char* filename) {
    printf("Testing FST Reader with file: %s\n", filename);
    printf("=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "\n");
    
    TestContext test_ctx;
    
    // Open FST file
    void* ctx = fstReaderOpen(filename);
    if (!ctx) {
        fprintf(stderr, "ERROR: Failed to open FST file: %s\n", filename);
        return false;
    }
    
    // Test basic metadata reading
    printf("\n1. File Metadata:\n");
    printf("  Version: %s\n", fstReaderGetVersionString(ctx));
    printf("  Date: %s\n", fstReaderGetDateString(ctx));
    printf("  Timescale: 10^%d\n", fstReaderGetTimescale(ctx));
    printf("  Start Time: %llu\n", (unsigned long long)fstReaderGetStartTime(ctx));
    printf("  End Time: %llu\n", (unsigned long long)fstReaderGetEndTime(ctx));
    printf("  Var Count: %llu\n", (unsigned long long)fstReaderGetVarCount(ctx));
    printf("  Scope Count: %llu\n", (unsigned long long)fstReaderGetScopeCount(ctx));
    printf("  Max Handle: %u\n", fstReaderGetMaxHandle(ctx));
    
    // Test hierarchy iteration
    printf("\n2. Hierarchy Traversal:\n");
    struct fstHier* hier;
    int var_count = 0;
    int scope_count = 0;
    
    while ((hier = fstReaderIterateHier(ctx))) {
        switch (hier->htyp) {
            case FST_HT_SCOPE:
                scope_count++;
                test_ctx.scopes.push_back(hier->u.scope.name);
                printf("  SCOPE: %s (type=%d)\n", hier->u.scope.name, hier->u.scope.typ);
                break;
                
            case FST_HT_VAR:
                var_count++;
                test_ctx.signals[hier->u.var.handle] = hier->u.var.name;
                printf("  VAR: %s [handle=%u, type=%d, dir=%d, len=%u]\n",
                       hier->u.var.name,
                       hier->u.var.handle,
                       hier->u.var.typ,
                       hier->u.var.direction,
                       hier->u.var.length);
                break;
                
            case FST_HT_UPSCOPE:
                printf("  UPSCOPE\n");
                break;
                
            default:
                break;
        }
    }
    
    printf("  Total Scopes: %d\n", scope_count);
    printf("  Total Variables: %d\n", var_count);
    
    // Test value change iteration (first 10 changes)
    printf("\n3. Value Changes (first 10):\n");
    fstReaderSetFacProcessMaskAll(ctx);
    fstReaderIterBlocks(ctx, value_change_callback, &test_ctx, nullptr);
    
    printf("  Total Value Changes: %d\n", test_ctx.value_change_count);
    printf("  Last Time: %llu\n", (unsigned long long)test_ctx.last_time);
    
    // Verify results
    printf("\n4. Test Verification:\n");
    bool passed = true;
    
    if (var_count == 0) {
        fprintf(stderr, "  FAIL: No variables found\n");
        passed = false;
    } else {
        printf("  PASS: Variables found (%d)\n", var_count);
    }
    
    if (test_ctx.value_change_count == 0) {
        fprintf(stderr, "  FAIL: No value changes found\n");
        passed = false;
    } else {
        printf("  PASS: Value changes found (%d)\n", test_ctx.value_change_count);
    }
    
    uint64_t start_time = fstReaderGetStartTime(ctx);
    uint64_t end_time = fstReaderGetEndTime(ctx);
    if (end_time <= start_time) {
        fprintf(stderr, "  FAIL: Invalid time range\n");
        passed = false;
    } else {
        printf("  PASS: Valid time range (%llu to %llu)\n", 
               (unsigned long long)start_time, 
               (unsigned long long)end_time);
    }
    
    // Clean up
    fstReaderClose(ctx);
    
    printf("\n5. Test Result: %s\n", passed ? "PASSED" : "FAILED");
    printf("=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "\n");
    
    return passed;
}

int main(int argc, char* argv[]) {
    const char* test_file = "test/vcd_extensions.fst";
    
    if (argc > 1) {
        test_file = argv[1];
    }
    
    printf("FST Reader API Test\n");
    printf("==================\n");
    
    bool result = test_fst_reader(test_file);
    
    return result ? 0 : 1;
}