// Read-only reference audit for the disconnected original Share create/init callbacks.
// @category Kodak
import java.nio.file.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.Reference;
public class AuditClassicSpace extends GhidraScript {
 public void run()throws Exception{
  long lo=0xebc90,hi=0xebecc;JsonArray allowed=new JsonArray(),unexpected=new JsonArray();
  for(long a=lo;a<hi;a++)for(Reference r:getReferencesTo(toAddr(a))){long from=r.getFromAddress().getOffset();JsonObject o=new JsonObject();o.addProperty("from",r.getFromAddress().toString());o.addProperty("to",Long.toHexString(a));o.addProperty("type",r.getReferenceType().toString());
   if((from>=lo&&from<hi)||from==0x1683a0||from==0x1683a8||from==0xebed0||from==0xebefc||from==0xebf00)allowed.add(o);else unexpected.add(o);
  }
  JsonObject report=new JsonObject();report.addProperty("start","0xebc90");report.addProperty("end_exclusive","0xebecc");report.add("internal_or_disconnected_table_references",allowed);report.add("unexpected_external_references",unexpected);report.addProperty("required_disconnections","Redirect original create/init event pointers at 0x1683a0/0x1683a8; NOP original legacy calls at 0xebed0/0xebefc/0xebf00");report.addProperty("passed",unexpected.size()==0);Files.writeString(Path.of(getScriptArgs()[0]),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");if(unexpected.size()!=0)throw new IllegalStateException("reclaim area has external references");println("CLASSIC SPACE AUDIT PASS");
 }
}
