/* Reviewed 32-bit wire/address layouts for analysis, not camera SDK headers.
 * Pointer fields are represented by uint32_t so host pointer width cannot alter offsets.
 * Unknown fields remain reserved. CaptureRequestPrefix is not the complete request.
 */
#ifndef KODAK_ANALYSIS_LAYOUTS_H
#define KODAK_ANALYSIS_LAYOUTS_H
#include <stddef.h>
#include <stdint.h>

typedef struct { int32_t coefficients[12]; } CaptureMatrixQ16;
typedef struct {
    uint32_t curve_A, curve_A_companion, curve_B, curve_B_companion, curve_C;
    uint8_t reserved_14[0x10];
    uint32_t illuminant_ccms[3];
    uint8_t reserved_30[8];
    uint32_t ymat_normal, ymat_bw, ymat_sepia;
    uint8_t reserved_44[4];
} CapturePipelineState;
typedef struct {
    uint16_t width, height, stride, bpp;
    uint32_t flags, palette, data;
} FirmwareImageRecord;
typedef struct {
    uint32_t kind;
    uint16_t screen_id, widget_count;
    uint32_t widgets, handler;
} FirmwareScreen;
typedef struct {
    uint32_t type, widget_id, parent;
    uint16_t x, y, width, height;
    uint32_t align;
    uint16_t image_id, alternate_id;
} FirmwareImageWidget;
typedef struct {
    uint8_t reserved_00[0x13];
    uint8_t color_mode, illuminant;
    uint8_t reserved_15[3];
} CaptureRequestPrefix;

_Static_assert(sizeof(CaptureMatrixQ16)==48,"matrix size");
_Static_assert(sizeof(CapturePipelineState)==0x48,"pipeline size");
_Static_assert(offsetof(CapturePipelineState,illuminant_ccms)==0x24,"CCM pointers");
_Static_assert(offsetof(CapturePipelineState,ymat_normal)==0x38,"normal Ymat");
_Static_assert(sizeof(FirmwareImageRecord)==20,"image record size");
_Static_assert(sizeof(FirmwareScreen)==16,"screen size");
_Static_assert(sizeof(FirmwareImageWidget)==0x1c,"widget size");
_Static_assert(offsetof(FirmwareImageWidget,image_id)==0x18,"image widget ID");
_Static_assert(sizeof(CaptureRequestPrefix)==0x18,"request prefix size");
_Static_assert(offsetof(CaptureRequestPrefix,color_mode)==0x13,"color mode offset");
_Static_assert(offsetof(CaptureRequestPrefix,illuminant)==0x14,"illuminant offset");
#endif
