// Repair four early seeds that were code locations, not independent functions.
// @category Kodak
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class CorrectBoundaries extends GhidraScript {
    @Override public void run() throws Exception {
        Path root=Path.of(getScriptArgs()[0]);
        JsonArray corrections=JsonParser.parseString(Files.readString(root.resolve("annotations/boundary_corrections.json"))).getAsJsonArray();
        for(JsonElement e:corrections){
            JsonObject correction=e.getAsJsonObject();Address site=toAddr(Long.decode(correction.get("site").getAsString()));
            Address entry=toAddr(Long.decode(correction.get("entry").getAsString()));
            Function wrong=getFunctionAt(site);if(wrong!=null)currentProgram.getFunctionManager().removeFunction(site);
            for(Symbol symbol:currentProgram.getSymbolTable().getSymbols(site))
                if(symbol.getName().equals(correction.get("previous_name").getAsString()))symbol.delete();
            Function f=getFunctionAt(entry);if(f!=null)currentProgram.getFunctionManager().removeFunction(entry);
            disassemble(entry);f=createFunction(entry,correction.get("function_name").getAsString());
            if(f==null)throw new IllegalStateException("Cannot reconstruct verified function entry "+entry);
            createLabel(site,correction.get("site_name").getAsString(),true);
        }
        println("Corrected "+corrections.size()+" interior-location function seeds.");
    }
}
