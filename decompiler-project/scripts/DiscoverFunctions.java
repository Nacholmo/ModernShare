// Recover otherwise unreferenced functions with a verified compiler prologue.
// @category Kodak
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;

public class DiscoverFunctions extends GhidraScript {
    @Override public void run() throws Exception {
        Path root=Path.of(getScriptArgs()[0]);
        Set<Long> saves=new HashSet<>();
        for(JsonElement element:JsonParser.parseString(Files.readString(root.resolve("annotations/compiler_helpers.json"))).getAsJsonArray()){
            JsonObject helper=element.getAsJsonObject();if(helper.get("kind").getAsString().equals("save"))saves.add(Long.decode(helper.get("address").getAsString()));
        }
        byte[] code=Files.readAllBytes(root.resolve("input/code.bin"));
        PseudoDisassembler decoder=new PseudoDisassembler(currentProgram);
        JsonArray rows=new JsonArray();int created=0,existing=0,interior=0;
        for(int offset=0;offset<code.length-12;offset+=2){
            monitor.checkCancelled();
            if((code[offset]&255)!=0xf1 || (code[offset+1]&255)!=0xc0)continue;
            Address at=toAddr(0x30000L+offset);
            try{
                PseudoInstruction push=decoder.disassemble(at);
                PseudoInstruction call=decoder.disassemble(at.add(2));
                if(push==null||call==null||!push.getMnemonicString().equals("push_s")||!call.getFlowType().isCall())continue;
                boolean matches=false;for(Address flow:call.getFlows())if(saves.contains(flow.getOffset()))matches=true;
                if(!matches)continue;
                JsonObject row=new JsonObject();row.addProperty("address",String.format("0x%08x",at.getOffset()));
                row.addProperty("prologue",push.toString()+"; "+call.toString());
                Function containing=getFunctionContaining(at);
                if(containing!=null){
                    row.addProperty("status",containing.getEntryPoint().equals(at)?"existing_entry":"inside_existing_function");
                    if(containing.getEntryPoint().equals(at))existing++;else interior++;
                }else if(getDataContaining(at)!=null){row.addProperty("status","defined_data_preserved");}
                else{
                    disassemble(at);Function f=createFunction(at,null);
                    row.addProperty("status",f==null?"creation_failed":"created");
                    if(f!=null){created++;f.setComment("Discovered by push_s blink followed by a direct call to a verified MetaWare save helper. Prologue is strong evidence of an entry; complete function extent and semantics still require review.");
                        createBookmark(at,"Function discovery","Verified compiler prologue pattern; inferred function boundary.");}
                }
                rows.add(row);
            }catch(Exception ex){
                // Nonmatching byte patterns are not code evidence; keep scanning without modifying them.
                println("Prologue candidate "+at+": "+ex.getMessage());
            }
        }
        analyzeChanges(currentProgram);
        JsonObject report=new JsonObject();report.addProperty("method","16-bit aligned push_s blink followed by direct BL to a verified MetaWare save helper; never splits an existing function or disassembles known data.");
        report.addProperty("created",created);report.addProperty("existing_entries",existing);report.addProperty("interior_candidates",interior);
        report.add("candidates",rows);
        Files.writeString(root.resolve("diagnostics/function_discovery.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");
        println("PROLOGUE DISCOVERY: "+created+" new functions; "+existing+" existing; "+interior+" interior candidates preserved");
    }
}
