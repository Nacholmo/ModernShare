// Read-only audit of old Share action/result callbacks, disconnected from the active root.
// @category Kodak
import java.nio.file.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.Reference;
public class AuditSettingsSpace extends GhidraScript {
 public void run()throws Exception{
  long lo=0xebecc,hi=0xec208;JsonArray inside=new JsonArray(),outside=new JsonArray(),graphics=new JsonArray();
  for(long a=lo;a<hi;a++){if(a>=0xec04c&&a<0xec088)continue;for(Reference r:getReferencesTo(toAddr(a))){long from=r.getFromAddress().getOffset();JsonObject o=new JsonObject();o.addProperty("from",r.getFromAddress().toString());o.addProperty("to",Long.toHexString(a));o.addProperty("type",r.getReferenceType().toString());
   if(from>=lo&&from<hi)inside.add(o);else if(from>=0x1a0000&&a==0xec003)graphics.add(o);else outside.add(o);
  }
  }
  JsonObject report=new JsonObject();report.addProperty("start","0xebecc");report.addProperty("end_exclusive","0xec208");report.addProperty("preserved_literal_gap","0xec04c..0xec087, including shared literal 0xec05c; only obsolete event-table pointer 0xec050 is cleared");report.add("internal_references",inside);report.add("unexpected_external_references",outside);report.add("graphics_rle_value_coincidences",graphics);report.addProperty("graphics_note","Odd value 0xec003 is embedded in packed graphics RLE data, not a callable ARC entry or a pointer table; graphics bytes are preserved");report.addProperty("passed",outside.size()==0);Files.writeString(Path.of(getScriptArgs()[0]),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");if(outside.size()!=0)throw new IllegalStateException("unexpected references into settings space");println("SETTINGS SPACE AUDIT PASS");
 }
}
