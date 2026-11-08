// Seed stock C713 firmware memory and annotations from the isolated project.
// @category Kodak
import java.io.*;
import java.math.BigInteger;
import java.nio.file.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class ApplyAnnotations extends GhidraScript {
    private Path root;
    private JsonObject json(String path) throws Exception {
        return JsonParser.parseString(Files.readString(root.resolve(path))).getAsJsonObject();
    }
    private Address addr(JsonObject o) { return toAddr(Long.decode(o.get("address").getAsString())); }
    private void type(long at, DataType dt) throws Exception {
        clearListing(toAddr(at), toAddr(at + dt.getLength() - 1));
        createData(toAddr(at), dt);
    }
    @Override public void run() throws Exception {
        root = Path.of(getScriptArgs()[0]).toAbsolutePath();
        JsonObject symbols = json("annotations/known_symbols.json");
        for (String category : new String[]{"labels","functions"}) {
            for (JsonElement element : symbols.getAsJsonArray(category)) {
                JsonObject s = element.getAsJsonObject(); Address at=addr(s);
                createLabel(at,s.get("name").getAsString(),true);
                setPlateComment(at,s.get("comment").getAsString()+"\nSOURCE: "+s.get("source").getAsString()+
                    "\nSTATUS: "+s.get("status").getAsString());
                if (category.equals("functions")) {
                    // Notes mix proven entry points and call sites. Never split an existing function.
                    Function containing = getFunctionContaining(at);
                    if (containing == null) {
                        disassemble(at);
                        Function f=createFunction(at,s.get("name").getAsString());
                        if (f==null) println("UNRESOLVED FUNCTION SEED "+at);
                        else f.setComment(s.get("comment").getAsString()+"\nSeeded from notes; ABI and function boundary require review.");
                    } else if (containing.getEntryPoint().equals(at)) {
                        containing.setName(s.get("name").getAsString(),SourceType.USER_DEFINED);
                        containing.setComment(s.get("comment").getAsString()+"\nSeeded from notes; ABI and function boundary require review.");
                    } else println("INTERIOR SEED "+at+" belongs to "+containing.getName());
                }
            }
        }
        for (JsonElement e : symbols.getAsJsonArray("comments")) {
            JsonObject s=e.getAsJsonObject(); setPreComment(addr(s),s.get("comment").getAsString());
        }
        DataType u8=UnsignedCharDataType.dataType, u16=UnsignedShortDataType.dataType;
        DataType u32=UnsignedIntegerDataType.dataType, i32=IntegerDataType.dataType;
        DataType p32=new PointerDataType(VoidDataType.dataType,4);
        StructureDataType ccm=new StructureDataType("CaptureMatrixQ16",0);
        ccm.add(new ArrayDataType(i32,12,4),"coefficients","3 rows x (3 coefficients + offset); int32 Q16");
        currentProgram.getDataTypeManager().addDataType(ccm,DataTypeConflictHandler.DEFAULT_HANDLER);
        for(long at:new long[]{0x16cac8,0x16caf8,0x16cb28,0x16cb58,0x16cb88,0x16cbb8}) type(at,ccm);
        type(0x16bac8,new ArrayDataType(u8,1024,1)); type(0x16c0c8,new ArrayDataType(u8,1024,1));
        type(0x1328ff,u8); type(0x132901,u8); type(0x132928,new ArrayDataType(u8,11,1));
        StructureDataType pipeline=new StructureDataType("CapturePipelineState",0x48);
        pipeline.replaceAtOffset(0,p32,4,"curve_A",null);
        pipeline.replaceAtOffset(4,p32,4,"curve_A_companion", "Inverse curve-B table, 256 uint16 entries");
        pipeline.replaceAtOffset(8,p32,4,"curve_B",null);
        pipeline.replaceAtOffset(12,p32,4,"curve_B_companion","Inverse curve-B table, 256 uint16 entries");
        pipeline.replaceAtOffset(16,p32,4,"curve_C","Third curve used by software photo converters");
        pipeline.replaceAtOffset(0x24,new ArrayDataType(new PointerDataType(ccm,4),3,4),12,"illuminant_ccms",null);
        pipeline.replaceAtOffset(0x38,new PointerDataType(ccm,4),4,"ymat_normal",null);
        pipeline.replaceAtOffset(0x3c,new PointerDataType(ccm,4),4,"ymat_bw",null);
        pipeline.replaceAtOffset(0x40,new PointerDataType(ccm,4),4,"ymat_sepia",null);
        type(0x197844,pipeline);
        StructureDataType image=new StructureDataType("FirmwareImageRecord",0);
        for (String field:new String[]{"width","height","stride","bpp"}) image.add(u16,field,null);
        image.add(u32,"flags",null); image.add(p32,"palette",null); image.add(p32,"data",null);
        type(0x1cc35c,image);
        type(0x1ccf50,new ArrayDataType(new PointerDataType(image,4),246,4));
        type(0x1cb83c,new ArrayDataType(u32,256,4));
        println("Applied current Kodak annotations and types.");
    }
}
