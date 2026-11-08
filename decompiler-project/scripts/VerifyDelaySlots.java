// Regression check for conditional clearing in a delayed tail branch.
// @category Kodak
import java.nio.file.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
public class VerifyDelaySlots extends GhidraScript {
 public void run() throws Exception {
  Path root=Path.of(getScriptArgs()[0]);DecompInterface dc=new DecompInterface();dc.openProgram(currentProgram);
  JsonArray rows=new JsonArray();
  for(long address:new long[]{0x472d0,0x6f1a0,0x78e84,0xbea08,0xbf04c,0x1062bc}){
   Function f=getFunctionAt(toAddr(address));if(f==null)throw new IllegalStateException("Missing regression function");
   DecompileResults result=dc.decompileFunction(f,45,monitor);
   JsonObject row=new JsonObject();row.addProperty("address",String.format("0x%08x",address));
   row.addProperty("completed",result.decompileCompleted());row.addProperty("diagnostic",result.getErrorMessage());rows.add(row);
   if(!result.decompileCompleted())throw new IllegalStateException(result.getErrorMessage());
  }
  dc.dispose();Files.writeString(root.resolve("diagnostics/delay_slot_regressions.json"),new GsonBuilder().setPrettyPrinting().create().toJson(rows)+"\n");
  println("DELAY SLOT REGRESSIONS PASSED: all six previously failing stock functions decompile.");
 }
}
