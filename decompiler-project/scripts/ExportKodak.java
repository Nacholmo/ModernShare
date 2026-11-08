// Export a reviewable first pass, including diagnostics and assembly.
// @category Kodak
import java.io.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class ExportKodak extends GhidraScript {
    @Override public void run() throws Exception {
        Path root=Path.of(getScriptArgs()[0]).toAbsolutePath();
        Path out=root.resolve("exports"); Files.createDirectories(out.resolve("functions"));
        JsonObject seeds=JsonParser.parseString(Files.readString(root.resolve("annotations/known_symbols.json"))).getAsJsonObject();
        DecompInterface dc=new DecompInterface();
        dc.setOptions(new DecompileOptions()); dc.toggleCCode(true); dc.toggleSyntaxTree(true);
        if(!dc.openProgram(currentProgram)) throw new IOException(dc.getLastMessage());
        JsonArray functions=new JsonArray(),edges=new JsonArray(),blocks=new JsonArray();
        int success=0;
        for(JsonElement e:seeds.getAsJsonArray("functions")) {
            monitor.checkCancelled(); JsonObject seed=e.getAsJsonObject();
            long offset=Long.decode(seed.get("address").getAsString()); Address at=toAddr(offset);
            JsonObject row=new JsonObject();
            row.addProperty("seed_address",at.toString()); row.addProperty("seed_name",seed.get("name").getAsString());
            Function f=getFunctionContaining(at);
            if(f==null){row.addProperty("status","no_function");functions.add(row);continue;}
            row.addProperty("entry",f.getEntryPoint().toString()); row.addProperty("function",f.getName());
            row.addProperty("seed_is_entry",at.equals(f.getEntryPoint()));
            row.addProperty("body_bytes",f.getBody().getNumAddresses());
            DecompileResults result=dc.decompileFunction(f,45,monitor);
            boolean ok=result.decompileCompleted() && result.getDecompiledFunction()!=null;
            row.addProperty("status",ok?"decompiled":"failed");
            row.addProperty("diagnostic",result.getErrorMessage());
            String stem=String.format("%08x",offset)+"_"+seed.get("name").getAsString();
            row.addProperty("export_stem",stem);
            String header="/* Generated pseudocode, NOT recovered source.\n * Stock C713 1.30; ARCompact processor module from upstream PR 3006.\n * Seed: "+seed.get("name").getAsString()+" at "+at+"; actual function entry: "+f.getEntryPoint()+"\n * "+seed.get("comment").getAsString()+"\n * Review assembly, inferred ABI and diagnostics before relying on this output.\n */\n";
            if(ok){Files.writeString(out.resolve("functions/"+stem+".c"),header+result.getDecompiledFunction().getC());success++;}
            StringBuilder assembly=new StringBuilder(header);
            InstructionIterator it=currentProgram.getListing().getInstructions(f.getBody(),true);
            while(it.hasNext()){
                Instruction ins=it.next();
                assembly.append(ins.getAddress()).append("  ");
                for(byte b:ins.getBytes())assembly.append(String.format("%02x",b&255));
                assembly.append("  ").append(ins).append('\n');
            }
            Files.writeString(out.resolve("functions/"+stem+".asm"),assembly);
            JsonArray callers=new JsonArray(),callees=new JsonArray();
            for(Function caller:f.getCallingFunctions(monitor))callers.add(caller.getEntryPoint()+" "+caller.getName());
            for(Function callee:f.getCalledFunctions(monitor)){
                callees.add(callee.getEntryPoint()+" "+callee.getName());
                JsonObject edge=new JsonObject();edge.addProperty("from",f.getEntryPoint().toString());
                edge.addProperty("to",callee.getEntryPoint().toString());edge.addProperty("name",callee.getName());edges.add(edge);
            }
            row.add("callers",callers);row.add("callees",callees);functions.add(row);
        }
        dc.dispose();
        for(MemoryBlock b:currentProgram.getMemory().getBlocks()){
            JsonObject o=new JsonObject();o.addProperty("name",b.getName());o.addProperty("start",b.getStart().toString());
            o.addProperty("end",b.getEnd().toString());o.addProperty("initialized",b.isInitialized());
            o.addProperty("read",b.isRead());o.addProperty("write",b.isWrite());o.addProperty("execute",b.isExecute());blocks.add(o);
        }
        JsonObject summary=new JsonObject();summary.addProperty("language",currentProgram.getLanguageID().toString());
        summary.addProperty("compiler_spec",currentProgram.getCompilerSpec().getCompilerSpecID().toString());
        summary.addProperty("function_count",currentProgram.getFunctionManager().getFunctionCount());
        summary.addProperty("seeded_functions_decompiled",success);summary.add("seeded_functions",functions);
        summary.add("memory_blocks",blocks);summary.add("call_edges",edges);
        JsonArray audit=new JsonArray(); int missingLabels=0,missingComments=0;
        for(String category:new String[]{"labels","functions"}){
            for(JsonElement element:seeds.getAsJsonArray(category)){
                JsonObject seed=element.getAsJsonObject();
                Address at=toAddr(Long.decode(seed.get("address").getAsString()));
                String wanted=seed.get("name").getAsString();boolean found=false;
                for(Symbol symbol:currentProgram.getSymbolTable().getSymbols(at))if(symbol.getName().equals(wanted))found=true;
                String comment=currentProgram.getListing().getComment(CodeUnit.PLATE_COMMENT,at);
                boolean commented=comment!=null && comment.contains(seed.get("comment").getAsString());
                JsonObject row=new JsonObject();row.addProperty("address",at.toString());row.addProperty("name",wanted);
                row.addProperty("label_present",found);row.addProperty("plate_comment_present",commented);audit.add(row);
                if(!found)missingLabels++;if(!commented)missingComments++;
            }
        }
        summary.add("annotation_audit",audit);summary.addProperty("missing_seed_labels",missingLabels);
        summary.addProperty("missing_seed_plate_comments",missingComments);
        if(missingLabels!=0 || missingComments!=0)throw new IOException("Annotation audit failed: labels="+missingLabels+" comments="+missingComments);
        Gson gson=new GsonBuilder().setPrettyPrinting().create();
        Files.writeString(out.resolve("analysis_summary.json"),gson.toJson(summary)+"\n");
        StringBuilder index=new StringBuilder("# First-pass decompilation\n\nGenerated pseudocode needs review against the accompanying assembly. Seed names come from the project notes; they are not original symbols.\n\n| Seed | Address | Result | Seed matches Ghidra entry |\n|---|---|---|---|\n");
        for(JsonElement e:functions){JsonObject o=e.getAsJsonObject();String stem=o.has("export_stem")?o.get("export_stem").getAsString():"";
            index.append("| ").append(o.get("seed_name").getAsString()).append(" | ").append(o.get("seed_address").getAsString()).append(" | ");
            if(o.get("status").getAsString().equals("decompiled"))index.append("[pseudocode](functions/").append(stem).append(".c), [assembly](functions/").append(stem).append(".asm)");
            else index.append(o.get("status").getAsString());
            index.append(" | ").append(o.has("seed_is_entry")?o.get("seed_is_entry"):"unknown").append(" |\n");
        }
        Files.writeString(out.resolve("INDEX.md"),index.toString());
        println("EXPORTED "+success+"/"+functions.size()+" seeded function decompilations; total functions="+currentProgram.getFunctionManager().getFunctionCount());
    }
}
