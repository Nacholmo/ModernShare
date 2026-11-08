// Complete, read-only export of the current Ghidra analysis database.
// @category Kodak
import java.io.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.pcode.PcodeOp;

public class ExportWorkspace extends GhidraScript {
    private final Gson gson = new GsonBuilder().serializeNulls().setPrettyPrinting().create();
    private String hex(Address a) { return a==null?null:String.format("0x%08x",a.getOffset()); }
    private void write(Path path,Object object) throws IOException {
        Files.writeString(path,gson.toJson(object)+"\n");
    }
    @Override public void run() throws Exception {
        Path root=Path.of(getScriptArgs()[0]).toAbsolutePath();
        Path out=root.resolve("exports"); Path funcs=out.resolve("functions"); Files.createDirectories(funcs);
        // Marker is written last; consumers can distinguish an incomplete export.
        Files.deleteIfExists(out.resolve("workspace_complete.json"));
        JsonObject seeds=JsonParser.parseString(Files.readString(root.resolve("annotations/known_symbols.json"))).getAsJsonObject();
        Map<String,JsonObject> seeded=new HashMap<>();
        for(JsonElement e:seeds.getAsJsonArray("functions")){
            JsonObject seed=e.getAsJsonObject();seeded.put(String.format("0x%08x",Long.decode(seed.get("address").getAsString())),seed);
        }
        DecompInterface dc=new DecompInterface(); dc.setOptions(new DecompileOptions()); dc.toggleCCode(true);
        dc.toggleSyntaxTree(true); if(!dc.openProgram(currentProgram))throw new IOException(dc.getLastMessage());
        JsonArray rows=new JsonArray(),edges=new JsonArray();
        AddressSet functionBytes=new AddressSet(); int success=0,failed=0,diagnostics=0,index=0;
        try{
            FunctionIterator iterator=currentProgram.getFunctionManager().getFunctions(true);
            while(iterator.hasNext()){
                monitor.checkCancelled(); Function f=iterator.next();
                Address at=f.getEntryPoint();String address=hex(at);functionBytes.add(f.getBody());
                String safe=f.getName().replaceAll("[^A-Za-z0-9_]","_");
                String stem=String.format("%08x",at.getOffset())+"_"+safe;
                JsonObject row=new JsonObject();row.addProperty("address",address);row.addProperty("name",f.getName());
                row.addProperty("export_stem",stem);row.addProperty("signature",f.getPrototypeString(false,false));
                row.addProperty("name_source",f.getSymbol().getSource().toString());
                row.addProperty("body_bytes",f.getBody().getNumAddresses());row.addProperty("thunk",f.isThunk());
                row.addProperty("no_return",f.hasNoReturn());row.addProperty("comment",f.getComment());
                row.addProperty("call_fixup",f.getCallFixup());
                JsonArray ranges=new JsonArray();
                for(AddressRange r:f.getBody().getAddressRanges()){
                    JsonObject o=new JsonObject();o.addProperty("start",hex(r.getMinAddress()));
                    o.addProperty("end",hex(r.getMaxAddress()));ranges.add(o);
                }row.add("body_ranges",ranges);
                JsonObject seed=seeded.get(address);row.addProperty("seeded",seed!=null);
                if(seed!=null)row.add("seed",seed.deepCopy());
                DecompileResults result=dc.decompileFunction(f,30,monitor);
                boolean ok=result.decompileCompleted()&&result.getDecompiledFunction()!=null;
                row.addProperty("status",ok?"decompiled":"failed");
                String diagnostic=result.getErrorMessage();row.addProperty("diagnostic",diagnostic);
                if(diagnostic!=null&&!diagnostic.isBlank())diagnostics++;
                String header="/* Generated pseudocode / disassembly, not original source.\n * Stock C713 1.30 | "+address+" | "+f.getName()+"\n * Names and signatures are analysis annotations; verify assembly and hardware behaviour.\n */\n";
                Path cfile=funcs.resolve(stem+".c");
                if(ok){Files.writeString(cfile,header+result.getDecompiledFunction().getC());success++;}
                else{Files.deleteIfExists(cfile);failed++;}
                StringBuilder assembly=new StringBuilder(header);
                JsonArray calls=new JsonArray(),dataRefs=new JsonArray(),indirect=new JsonArray(),opaque=new JsonArray();
                Set<String> dataSeen=new HashSet<>();int instructionCount=0;
                InstructionIterator ins=currentProgram.getListing().getInstructions(f.getBody(),true);
                while(ins.hasNext()){
                    Instruction instruction=ins.next();instructionCount++;
                    assembly.append(hex(instruction.getAddress())).append("  ");
                    for(byte b:instruction.getBytes())assembly.append(String.format("%02x",b&255));
                    assembly.append("  ").append(instruction).append('\n');
                    if(instruction.getFlowType().isComputed()&&(instruction.getFlowType().isCall()||instruction.getFlowType().isJump())){
                        JsonObject o=new JsonObject();o.addProperty("site",hex(instruction.getAddress()));
                        o.addProperty("instruction",instruction.toString());o.addProperty("call",instruction.getFlowType().isCall());indirect.add(o);
                    }
                    for(PcodeOp op:instruction.getPcode()){
                        if(op.getOpcode()==PcodeOp.CALLOTHER){
                            String name=currentProgram.getLanguage().getUserDefinedOpName((int)op.getInput(0).getOffset());
                            JsonObject o=new JsonObject();o.addProperty("site",hex(instruction.getAddress()));
                            o.addProperty("operation",name);opaque.add(o);
                        }
                    }
                    for(Reference ref:instruction.getReferencesFrom()){
                        if(ref.getReferenceType().isCall()){
                            JsonObject edge=new JsonObject();edge.addProperty("from",address);
                            edge.addProperty("site",hex(instruction.getAddress()));edge.addProperty("to",hex(ref.getToAddress()));
                            edge.addProperty("space",ref.getToAddress().getAddressSpace().getName());
                            Function target=getFunctionAt(ref.getToAddress());
                            edge.addProperty("target_name",target==null?null:target.getName());
                            edge.addProperty("type",ref.getReferenceType().toString());calls.add(edge);edges.add(edge.deepCopy());
                        }else if(ref.getReferenceType().isData()&&ref.getToAddress().isMemoryAddress()){
                            String key=ref.getToAddress().toString();
                            if(dataSeen.add(key)){
                                JsonObject o=new JsonObject();o.addProperty("address",hex(ref.getToAddress()));o.addProperty("space",ref.getToAddress().getAddressSpace().getName());
                                Symbol symbol=currentProgram.getSymbolTable().getPrimarySymbol(ref.getToAddress());
                                o.addProperty("name",symbol==null?null:symbol.getName());
                                Data data=getDataContaining(ref.getToAddress());
                                o.addProperty("type",data==null?null:data.getDataType().getDisplayName());
                                if(data!=null&&data.hasStringValue())o.addProperty("string",String.valueOf(data.getValue()));
                                dataRefs.add(o);
                            }
                        }
                    }
                }
                Files.writeString(funcs.resolve(stem+".asm"),assembly);
                row.addProperty("instruction_count",instructionCount);row.add("calls",calls);
                row.add("data_references",dataRefs);row.add("computed_flows",indirect);row.add("opaque_operations",opaque);
                JsonArray warnings=new JsonArray(),modelNotes=new JsonArray();
                if(ok){
                    java.util.regex.Matcher matcher=java.util.regex.Pattern.compile("/\\* WARNING:(.*?)\\*/",java.util.regex.Pattern.DOTALL).matcher(result.getDecompiledFunction().getC());
                    while(matcher.find()){
                        String warning=matcher.group(1).trim().replaceAll("\\s+"," ");
                        if(warning.contains("replaced with injection: kodak_"))modelNotes.add(warning);else warnings.add(warning);
                    }
                }
                row.add("warnings",warnings);row.add("model_notes",modelNotes);row.addProperty("needs_review",!ok||warnings.size()>0||opaque.size()>0||indirect.size()>0||f.getCallFixup()!=null);
                rows.add(row);
                index++;if(index%250==0)println("EXPORT PROGRESS "+index+" functions; "+failed+" failures");
            }
        }finally{dc.dispose();}
        write(out.resolve("function_index.json"),rows);write(out.resolve("call_graph.json"),edges);
        // Audit annotation persistence and export direct references for every named seed.
        JsonArray annotations=new JsonArray();int missing=0;
        for(String category:new String[]{"labels","functions","comments"}){
            for(JsonElement e:seeds.getAsJsonArray(category)){
                JsonObject seed=e.getAsJsonObject();Address at=toAddr(Long.decode(seed.get("address").getAsString()));
                JsonObject row=seed.deepCopy();row.addProperty("category",category);
                String comment=currentProgram.getListing().getComment(category.equals("comments")?CodeUnit.PRE_COMMENT:CodeUnit.PLATE_COMMENT,at);
                boolean commentOk=comment!=null&&comment.contains(seed.get("comment").getAsString());
                boolean labelOk=category.equals("comments");
                if(!labelOk)for(Symbol symbol:currentProgram.getSymbolTable().getSymbols(at)){
                    if(symbol.getName().equals(seed.get("name").getAsString()))labelOk=true;
                }
                row.addProperty("comment_present",commentOk);row.addProperty("label_present",labelOk);
                Function containing=getFunctionContaining(at);row.addProperty("containing_function",containing==null?null:hex(containing.getEntryPoint()));
                row.addProperty("seed_is_entry",containing!=null&&containing.getEntryPoint().equals(at));
                Data data=getDataAt(at);row.addProperty("data_type",data==null?null:data.getDataType().getDisplayName());
                JsonArray refs=new JsonArray();ReferenceIterator refsIt=currentProgram.getReferenceManager().getReferencesTo(at);
                while(refsIt.hasNext()){
                    Reference ref=refsIt.next();JsonObject r=new JsonObject();r.addProperty("from",hex(ref.getFromAddress()));
                    r.addProperty("type",ref.getReferenceType().toString());Function owner=getFunctionContaining(ref.getFromAddress());
                    r.addProperty("function",owner==null?null:hex(owner.getEntryPoint()));refs.add(r);
                }row.add("references_to",refs);annotations.add(row);if(!commentOk||!labelOk)missing++;
            }
        }write(out.resolve("annotations.json"),annotations);
        // Export all defined strings and all user-defined labels, not just the seeded subset.
        JsonArray strings=new JsonArray(),labels=new JsonArray(),types=new JsonArray();
        DataIterator dataIt=currentProgram.getListing().getDefinedData(true);
        while(dataIt.hasNext()){
            Data data=dataIt.next();if(!data.hasStringValue())continue;
            JsonObject row=new JsonObject();row.addProperty("address",hex(data.getAddress()));row.addProperty("size",data.getLength());
            row.addProperty("value",String.valueOf(data.getValue()));strings.add(row);
        }write(out.resolve("strings.json"),strings);
        SymbolIterator symbols=currentProgram.getSymbolTable().getAllSymbols(true);
        while(symbols.hasNext()){
            Symbol symbol=symbols.next();if(symbol.getSource()!=SourceType.USER_DEFINED)continue;
            JsonObject row=new JsonObject();row.addProperty("address",hex(symbol.getAddress()));row.addProperty("space",symbol.getAddress().getAddressSpace().getName());row.addProperty("name",symbol.getName());
            row.addProperty("kind",symbol.getSymbolType().toString());labels.add(row);
        }write(out.resolve("user_symbols.json"),labels);
        Iterator<DataType> typeIt=currentProgram.getDataTypeManager().getAllDataTypes();
        while(typeIt.hasNext()){
            DataType dt=typeIt.next();if(!(dt instanceof Structure)&&!(dt instanceof ghidra.program.model.data.Enum))continue;
            JsonObject row=new JsonObject();row.addProperty("name",dt.getPathName());row.addProperty("size",dt.getLength());
            row.addProperty("definition",dt.toString());types.add(row);
        }write(out.resolve("data_types.json"),types);
        // Coverage describes classification of a mixed code/literal section, not recovered-source completeness.
        AddressSet codeRange=new AddressSet(toAddr(0x30000),toAddr(0x12ffff));
        AddressSet classified=new AddressSet();long instructionBytes=0,dataBytes=0;
        InstructionIterator instructions=currentProgram.getListing().getInstructions(codeRange,true);
        while(instructions.hasNext()){
            Instruction ins=instructions.next();classified.add(ins.getMinAddress(),ins.getMaxAddress());instructionBytes+=ins.getLength();
        }
        dataIt=currentProgram.getListing().getDefinedData(codeRange,true);
        while(dataIt.hasNext()){
            Data data=dataIt.next();classified.add(data.getMinAddress(),data.getMaxAddress());dataBytes+=data.getLength();
        }
        AddressSet unknown=new AddressSet(codeRange);unknown.delete(classified);
        JsonArray unknownRanges=new JsonArray();long zero=0,nonzero=0;
        for(AddressRange range:unknown.getAddressRanges()){
            byte[] bytes=new byte[(int)range.getLength()];currentProgram.getMemory().getBytes(range.getMinAddress(),bytes);
            long zeros=0;for(byte b:bytes)if(b==0)zeros++;zero+=zeros;nonzero+=bytes.length-zeros;
            JsonObject r=new JsonObject();r.addProperty("start",hex(range.getMinAddress()));r.addProperty("end",hex(range.getMaxAddress()));
            r.addProperty("size",bytes.length);r.addProperty("zero_bytes",zeros);unknownRanges.add(r);
        }write(out.resolve("unclassified_ranges.json"),unknownRanges);
        JsonObject coverage=new JsonObject();coverage.addProperty("section_bytes",0x100000);
        coverage.addProperty("instruction_bytes",instructionBytes);coverage.addProperty("defined_data_bytes",dataBytes);
        coverage.addProperty("function_body_bytes_in_code",functionBytes.intersect(codeRange).getNumAddresses());
        coverage.addProperty("unclassified_bytes",unknown.getNumAddresses());coverage.addProperty("unclassified_zero_bytes",zero);
        coverage.addProperty("unclassified_nonzero_bytes",nonzero);
        coverage.addProperty("meaning","Mixed code/literal section classification only. Unclassified bytes may include literal pools, tables, padding, or undiscovered code. Function discovery and decompilation do not establish semantic correctness.");
        write(out.resolve("coverage.json"),coverage);
        JsonObject summary=new JsonObject();summary.addProperty("schema_version",1);
        summary.addProperty("language",currentProgram.getLanguageID().toString());
        summary.addProperty("function_count",rows.size());summary.addProperty("decompiled",success);
        summary.addProperty("failed",failed);summary.addProperty("functions_with_diagnostics",diagnostics);
        summary.addProperty("annotation_count",annotations.size());summary.addProperty("missing_annotations",missing);
        summary.addProperty("defined_string_count",strings.size());summary.addProperty("direct_call_edges",edges.size());
        summary.add("coverage",coverage);
        if(missing!=0)throw new IOException("Annotation audit failed for "+missing+" seeds; inspect exports/annotations.json");
        write(out.resolve("workspace_complete.json"),summary);
        println("WORKSPACE EXPORT COMPLETE: "+success+"/"+rows.size()+" decompiled; diagnostics="+diagnostics+"; missing annotations="+missing);
    }
}
