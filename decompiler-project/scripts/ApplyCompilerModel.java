// Apply verified shared-prologue / shared-epilogue semantics to callers.
// @category Kodak
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;

public class ApplyCompilerModel extends GhidraScript {
    @Override public void run() throws Exception {
        if(!currentProgram.getLanguageID().toString().equals("ARCompact:LE:32:kodak"))
            throw new IllegalStateException("This project requires the Kodak-specific language.");
        Path root=Path.of(getScriptArgs()[0]);
        JsonArray helpers=JsonParser.parseString(Files.readString(root.resolve("annotations/compiler_helpers.json"))).getAsJsonArray();
        List<Address> remove=new ArrayList<>();
        for(Function f:currentProgram.getFunctionManager().getFunctions(true)){
            long at=f.getEntryPoint().getOffset();if(at>=0x11adb8&&at<=0x11ae9a)remove.add(f.getEntryPoint());
            else if(f.getBody().intersects(toAddr(0x11adb8),toAddr(0x11ae9a))){
                AddressSet clipped=new AddressSet(f.getBody());clipped.delete(toAddr(0x11adb8),toAddr(0x11ae9a));
                if(!clipped.isEmpty())f.setBody(clipped);
            }
        }
        for(Address at:remove)currentProgram.getFunctionManager().removeFunction(at);
        for(JsonElement e:helpers){
            JsonObject h=e.getAsJsonObject();Address at=toAddr(Long.decode(h.get("address").getAsString()));
            disassemble(at);Instruction instruction=getInstructionAt(at);
            if(instruction==null)throw new IllegalStateException("Cannot decode helper at "+at);
            String name=h.get("name").getAsString();
            Function f=currentProgram.getFunctionManager().createFunction(name,at,
                new AddressSet(instruction.getMinAddress(),instruction.getMaxAddress()),SourceType.USER_DEFINED);
            f.setCallFixup(name);
            f.setComment("MetaWare shared "+h.get("kind").getAsString()+" helper. Body ownership is only the entry instruction because suffixes overlap. The call-fixup models the full register and stack effects for callers. Review diagnostics/compiler_helpers.binutils.asm and annotations/compiler_helpers.json; standalone decompilation of this entry is incomplete.");
        }
        println("Applied "+helpers.size()+" assembly-reviewed compiler helper fixups.");
    }
}
