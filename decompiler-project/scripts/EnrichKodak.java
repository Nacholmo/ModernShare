// Define reviewed data layouts, capture signatures and named auxiliary registers.
// @category Kodak
import java.nio.file.*;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.SourceType;

public class EnrichKodak extends GhidraScript {
    private final DataType u8=UnsignedCharDataType.dataType,u16=UnsignedShortDataType.dataType,u32=UnsignedIntegerDataType.dataType;
    private void data(Address at,DataType dt) throws Exception{
        clearListing(at,at.add(dt.getLength()-1));createData(at,dt);
    }
    private void signature(long address,DataType result,String[] names,DataType... types) throws Exception{
        Function f=getFunctionAt(toAddr(address));if(f==null)throw new IllegalStateException("Missing reviewed function "+Long.toHexString(address));
        f.setReturnType(result,SourceType.USER_DEFINED);List<Parameter> params=new ArrayList<>();
        for(int i=0;i<types.length;i++)params.add(new ParameterImpl(names[i],types[i],currentProgram));
        f.replaceParameters(params,Function.FunctionUpdateType.DYNAMIC_STORAGE_ALL_PARAMS,true,SourceType.USER_DEFINED);
    }
    @Override public void run() throws Exception{
        DataType matrix=currentProgram.getDataTypeManager().getDataType("/CaptureMatrixQ16");
        DataType pipeline=currentProgram.getDataTypeManager().getDataType("/CapturePipelineState");
        ((Structure)pipeline).getComponentAt(4).setComment("Inverse curve-B lookup, 256 uint16 entries");
        ((Structure)pipeline).getComponentAt(12).setComment("Second inverse curve-B lookup, identical in stock");
        ((Structure)pipeline).getComponentAt(16).setComment("Curve C used by software photo converters");
        DataType image=currentProgram.getDataTypeManager().getDataType("/FirmwareImageRecord");
        DataType pointer=new PointerDataType(VoidDataType.dataType,4);
        StructureDataType request=new StructureDataType("CaptureRequestPrefix",0x18);
        request.replaceAtOffset(0x13,u8,1,"color_mode","3 B&W, 4 sepia, other values normal");
        request.replaceAtOffset(0x14,u8,1,"illuminant","CCM selector, normally 0..2");
        request.setDescription("Reviewed prefix only; the complete request struct extends beyond this layout.");
        DataType requestType=currentProgram.getDataTypeManager().addDataType(request,DataTypeConflictHandler.DEFAULT_HANDLER);
        signature(0x11e124,u32,new String[]{"request"},new PointerDataType(requestType,4));
        signature(0x11e0b8,VoidDataType.dataType,new String[]{"packed_words","matrix"},new PointerDataType(u32,4),new PointerDataType(matrix,4));
        signature(0xaf4c4,u32,new String[]{"state"},new PointerDataType(pipeline,4));
        signature(0x67dec,u32,new String[]{"image_id","out_record"},u32,new PointerDataType(new PointerDataType(image,4),4));
        signature(0x3bd7c,u8,new String[]{});
        signature(0x3c5ec,u32,new String[]{"scene_index"},u32);
        signature(0xf2664,u32,new String[]{});
        StructureDataType screen=new StructureDataType("FirmwareScreen",0);
        screen.add(u32,"kind","0x402 for static screens");screen.add(u16,"screen_id",null);screen.add(u16,"widget_count",null);
        screen.add(pointer,"widgets",null);screen.add(pointer,"handler",null);data(toAddr(0x15eedc),screen);
        StructureDataType widget=new StructureDataType("FirmwareImageWidget",0);
        widget.add(u32,"type","7 for image widgets");widget.add(u32,"widget_id",null);widget.add(pointer,"parent","Populated at runtime");
        for(String field:new String[]{"x","y","width","height"})widget.add(u16,field,null);
        widget.add(u32,"align",null);widget.add(u16,"image_id",null);widget.add(u16,"alternate_id",null);
        currentProgram.getDataTypeManager().addDataType(widget,DataTypeConflictHandler.DEFAULT_HANDLER);
        // All stock image records get their correct 20-byte layout.
        for(int i=1;i<246;i++){
            long address=Integer.toUnsignedLong(getInt(toAddr(0x1ccf50+i*4)));
            if(address>=0x1a0000&&address+20<=0x1efc00)data(toAddr(address),image);
        }
        data(toAddr(0x16bec8),new ArrayDataType(u16,256,2));
        data(toAddr(0x16c4c8),new ArrayDataType(u16,256,2));
        data(toAddr(0x16c6c8),new ArrayDataType(u8,1024,1));
        for(long at:new long[]{0x13358c,0x133184,0x133185,0x135235})data(toAddr(at),u8);
        data(toAddr(0x141c00),new ArrayDataType(u32,256,4));
        data(toAddr(0x175420),new ArrayDataType(u32,256,4));
        data(toAddr(0x1320dc),new ArrayDataType(u32,6,4));createLabel(toAddr(0x1320dc),"packed_capture_ccm",true);
        data(toAddr(0x1320f4),new ArrayDataType(u32,6,4));createLabel(toAddr(0x1320f4),"packed_capture_ycbcr",true);
        AddressSpace aux=currentProgram.getAddressFactory().getAddressSpace("auxregs");
        Address first=aux.getAddress(0x43c80);
        if(currentProgram.getMemory().getBlock(first)==null){
            MemoryBlock block=currentProgram.getMemory().createUninitializedBlock("capture_auxiliary_registers",first,0x58,false);
            block.setRead(true);block.setWrite(true);block.setVolatile(true);block.setExecute(false);
        }
        for(int i=0;i<6;i++){
            Address a=aux.getAddress(0x43c80+i*4);data(a,u32);createLabel(a,"isp_capture_ccm_word"+i,true);
            a=aux.getAddress(0x43c98+i*4);data(a,u32);createLabel(a,"isp_capture_ycbcr_word"+i,true);
        }
        analyzeChanges(currentProgram);
        println("Enriched capture signatures, 245 image records, screen/widget types and high auxiliary registers.");
    }
}
