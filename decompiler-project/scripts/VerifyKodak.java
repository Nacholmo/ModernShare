// Check real program state: mapped bytes, ABI fixups, boundary repairs and high AUX address.
// @category Kodak
import java.nio.file.*;
import java.security.*;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.pcode.*;

public class VerifyKodak extends GhidraScript {
    private void require(boolean value,String message){if(!value)throw new IllegalStateException(message);}
    private String sha(byte[] bytes)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    @Override public void run() throws Exception{
        Path root=Path.of(getScriptArgs()[0]);JsonObject report=new JsonObject();JsonArray hashes=new JsonArray();
        require(currentProgram.getLanguageID().toString().equals("ARCompact:LE:32:kodak"),"Wrong language model");
        report.addProperty("language",currentProgram.getLanguageID().toString());
        JsonObject manifest=JsonParser.parseString(Files.readString(root.resolve("input/manifest.json"))).getAsJsonObject();
        for(JsonElement e:manifest.getAsJsonArray("sections")){
            JsonObject section=e.getAsJsonObject();if(!section.get("mapped").getAsBoolean())continue;
            byte[] expected=Files.readAllBytes(root.resolve(section.get("path").getAsString()));byte[] actual=new byte[expected.length];
            int n=currentProgram.getMemory().getBytes(toAddr(section.get("ram_address").getAsLong()),actual);
            require(n==expected.length&&Arrays.equals(actual,expected),"Mapped bytes changed: "+section.get("name"));
            JsonObject row=new JsonObject();row.addProperty("section",section.get("name").getAsString());row.addProperty("sha256",sha(actual));hashes.add(row);
        }report.add("mapped_section_hashes",hashes);
        require(currentProgram.getMemory().getBlock(toAddr(0x1f0000))==null,"Language flash image incorrectly mapped into RAM");
        require(currentProgram.getProgramContext().getValue(currentProgram.getRegister("gp"),toAddr(0xaf508),false).longValue()==0x172ef4,"GP context missing");
        JsonArray helpers=JsonParser.parseString(Files.readString(root.resolve("annotations/compiler_helpers.json"))).getAsJsonArray();
        for(JsonElement e:helpers){JsonObject h=e.getAsJsonObject();Function f=getFunctionAt(toAddr(Long.decode(h.get("address").getAsString())));
            require(f!=null&&h.get("name").getAsString().equals(f.getCallFixup()),"Compiler helper fixup missing: "+h.get("name"));}
        report.addProperty("verified_helper_fixups",helpers.size());
        JsonArray boundaries=JsonParser.parseString(Files.readString(root.resolve("annotations/boundary_corrections.json"))).getAsJsonArray();
        for(JsonElement e:boundaries){JsonObject row=e.getAsJsonObject();Address site=toAddr(Long.decode(row.get("site").getAsString()));
            Function owner=getFunctionContaining(site);Address entry=toAddr(Long.decode(row.get("entry").getAsString()));
            require(getFunctionAt(site)==null,"Interior site still treated as function: "+site);
            require(owner!=null&&owner.getEntryPoint().equals(entry),"Incorrect owner for interior site: "+site);}
        report.addProperty("verified_boundary_repairs",boundaries.size());
        String[] names={"CaptureMatrixQ16","CapturePipelineState","FirmwareImageRecord","FirmwareScreen","FirmwareImageWidget","CaptureRequestPrefix"};
        int[] sizes={48,72,20,16,28,24};JsonObject types=new JsonObject();
        for(int i=0;i<names.length;i++){
            DataType dt=currentProgram.getDataTypeManager().getDataType("/"+names[i]);
            require(dt!=null&&dt.getLength()==sizes[i],"Wrong type layout: "+names[i]);types.addProperty(names[i],dt.getLength());
        }report.add("verified_type_sizes",types);
        for(long at:new long[]{0x16bec8,0x16c4c8}){
            Data table=getDataAt(toAddr(at));require(table!=null&&table.getDataType() instanceof Array,"Missing inverse table array");
            Array array=(Array)table.getDataType();require(array.getNumElements()==256&&array.getDataType().getLength()==2,"Wrong inverse table layout");
        }
        report.addProperty("verified_inverse_table_layouts",true);
        String[][] fields={{"CapturePipelineState","illuminant_ccms","36"},{"CapturePipelineState","ymat_normal","56"},{"CapturePipelineState","ymat_bw","60"},{"CapturePipelineState","ymat_sepia","64"},{"FirmwareImageRecord","data","16"},{"FirmwareImageWidget","image_id","24"},{"CaptureRequestPrefix","color_mode","19"},{"CaptureRequestPrefix","illuminant","20"}};
        JsonArray fieldAudit=new JsonArray();
        for(String[] field:fields){
            Structure structure=(Structure)currentProgram.getDataTypeManager().getDataType("/"+field[0]);int offset=Integer.parseInt(field[2]);
            DataTypeComponent component=structure.getComponentAt(offset);
            require(component!=null&&component.getOffset()==offset&&field[1].equals(component.getFieldName()),"Wrong field offset: "+field[0]+"."+field[1]);
            fieldAudit.add(field[0]+"."+field[1]+" @ "+offset);
        }
        report.add("verified_field_offsets",fieldAudit);
        require(currentProgram.getAddressFactory().getAddressSpace("auxregs").getSize()==32,"AUX address space still truncates");
        Instruction instruction=getInstructionAt(toAddr(0x11e15e));boolean correct=false;JsonArray pcode=new JsonArray();
        Map<String,Long> constants=new HashMap<>();
        for(PcodeOp op:instruction.getPcode()){
            pcode.add(op.toString());
            if(op.getOpcode()==PcodeOp.INT_LEFT&&op.getInput(0).isConstant()&&op.getInput(1).isConstant())
                constants.put(op.getOutput().toString(),op.getInput(0).getOffset()<<op.getInput(1).getOffset());
            if(op.getOpcode()==PcodeOp.STORE){
                Varnode pointer=op.getInput(1);Long value=pointer.isConstant()?pointer.getOffset():constants.get(pointer.toString());
                if(value!=null&&value==0x43c80)correct=true;
            }
        }
        require(correct,"High AUX store did not preserve byte address 0x43c80");
        report.add("high_aux_store_pcode",pcode);report.addProperty("stock_sha256",manifest.get("sha256").getAsString());
        report.addProperty("function_count",currentProgram.getFunctionManager().getFunctionCount());report.addProperty("passed",true);
        Files.writeString(root.resolve("diagnostics/project_audit.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");
        println("PROJECT AUDIT PASSED: stock bytes, language model, 28 helpers, 4 boundary repairs, type sizes and high AUX address.");
    }
}
