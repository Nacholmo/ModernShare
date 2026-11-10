// Execute the patched row-text call and the name+value hook instruction by instruction.
// Only the two stock routines it calls (string lookup, text draw) are modelled.
// Usage: -postScript TestRowHook.java BUILD_DIR   (writes BUILD_DIR/ember-rowhook-emulation.json)
// @category Kodak
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;

public class TestEmberRowHook extends GhidraScript {
 static final long CALL=0x8fc2a,AFTER=0x8fc32,STRING=0x8a3c0,DRAW=0x78ce0,HOOK=0x12fd90,HOOK_END=0x12fe7a;
 static final long SP=0x19f000,ITEM=0x180000,NAMEPTR=0x184abc,VALUE=0x150d3c;
 byte[] fw;JsonArray results=new JsonArray();
 long reg(EmulatorHelper e,String r){return e.readRegister(r).longValue()&0xffffffffL;}
 void require(boolean b,String s){if(!b)throw new IllegalStateException(s);}
 void returned(EmulatorHelper e,long value){long pc=reg(e,"blink");for(int i=0;i<=12;i++)e.writeRegister("r"+i,0xdead0000L+i);e.writeRegister("r0",value);e.writeRegister(e.getPCRegister(),pc);}
 // text = item+4, name = item+8, align = r23 (copied to r6 in the call's delay slot); dual = expect two draws
 void scenario(String name,long item,long text,long nameField,long align,boolean dual,boolean selected)throws Exception{
  EmulatorHelper e=new EmulatorHelper(currentProgram);
  try{
   e.writeMemory(toAddr(0x30000),Arrays.copyOfRange(fw,0x200,0x100200));
   e.writeMemory(toAddr(0x130000),Arrays.copyOfRange(fw,0x100200,0x144c00));
   for(int i=0;i<=25;i++)e.writeRegister("r"+i,0xabc00000L+i);
   long x=69,y=38,w=name.contains("narrow")?160:409,h=36,colour=0x00e4edf1L;
   e.writeRegister("r0",x);e.writeRegister("r1",y);e.writeRegister("r2",w);e.writeRegister("r3",h);
   long resolved=text<0x345?VALUE:text; e.writeRegister("r4",resolved);e.writeRegister("r5",colour);e.writeRegister("r23",align);e.writeRegister("r18",item);e.writeRegister("r16",selected?1:0);
   e.writeRegister("sp",SP);e.writeRegister("blink",0x30010);
   e.writeMemoryValue(toAddr(item),4,0x00270027);e.writeMemoryValue(toAddr(item+4),4,text);e.writeMemoryValue(toAddr(item+8),4,nameField);
   byte[] guard=new byte[64];Arrays.fill(guard,(byte)0x5a);e.writeMemory(toAddr(SP),guard);e.writeMemory(toAddr(SP-96),guard);
   e.writeRegister(e.getPCRegister(),CALL);
   List<long[]> draws=new ArrayList<>();int lookups=0,steps=0;
   while(steps++<400){
    long pc=e.getExecutionAddress().getOffset();
    if(pc==AFTER)break;
    if(pc==STRING){require(nameField<0x345,"no pointer string lookup");require(reg(e,"r0")==nameField,"string lookup id");require(reg(e,"sp")==SP-32,"stack during lookup");lookups++;returned(e,NAMEPTR);continue;}
    if(pc==DRAW){long[] a=new long[8];for(int i=0;i<7;i++)a[i]=reg(e,"r"+i);a[7]=reg(e,"sp");draws.add(a);returned(e,0);continue;}
    require(pc==CALL||pc==CALL+4||(pc>=HOOK&&pc<HOOK_END),name+": left the hook at "+Long.toHexString(pc));
    require(e.step(monitor),name+" at "+Long.toHexString(pc)+": "+e.getLastError());
   }
   require(steps<400,name+": did not return");
   require(reg(e,"sp")==SP,name+": stack pointer");
   for(int i=13;i<=25;i++)require(reg(e,"r"+i)==(i==18?item:i==16?(selected?1:0):i==23?align:0xabc00000L+i),name+": callee-saved r"+i);
   require(Arrays.equals(e.readMemory(toAddr(SP),64),guard),name+": wrote above its frame");
   require(Arrays.equals(e.readMemory(toAddr(SP-96),64-32),Arrays.copyOf(guard,32)),name+": wrote below its frame");
   if(dual){
    require(lookups==(nameField<0x345?1:0)&&draws.size()==2,name+": expected name + value draws, got "+draws.size());
    long[] a=draws.get(0),b=draws.get(1);
    require(a[0]==x&&a[1]==y&&a[2]==w&&a[3]==h&&a[4]==(nameField<0x345?NAMEPTR:nameField)&&a[5]==colour&&a[6]==4&&a[7]==SP-32,name+": name draw arguments");
    require(b[0]==x+Math.max(0,w-24-224)&&b[1]==y&&b[2]==Math.min(w-24,224)&&b[3]==h&&b[4]==resolved&&b[5]==(selected?0x0060bbf2L:0x00b1bdc4L)&&b[6]==6&&b[7]==SP-32,name+": bounded value draw arguments");
   }else{
    require(lookups==0&&draws.size()==1,name+": expected the stock single draw");
    long[] a=draws.get(0);
    require(a[0]==x&&a[1]==y&&a[2]==w&&a[3]==h&&a[4]==resolved&&a[5]==colour&&a[6]==align&&a[7]==SP,name+": stock draw arguments");
   }
   JsonObject r=new JsonObject();r.addProperty("name",name);r.addProperty("passed",true);r.addProperty("draws",draws.size());r.addProperty("steps",steps);results.add(r);
   println("EMBER ROW HOOK PASS "+name);
  }finally{e.dispose();}
 }
 public void run()throws Exception{
  Path build=Path.of(getScriptArgs()[0]);fw=Files.readAllBytes(build.resolve("KC713.FW"));
  String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw));
  scenario("capture value buffer idle",0x150aec,VALUE,0x55,4,true,false);
  scenario("capture value buffer focused",0x150aec,VALUE,0x55,4,true,true);
  scenario("narrow value box without cap",ITEM,VALUE,0x55,4,true,false);
  scenario("capture native string id idle",0x150aec,0xc8,0x55,4,true,false);
  scenario("capture native string id focused",0x150b04,0x60,0x5f,4,true,true);
  scenario("video native string id",0x169528,0xc8,0x55,4,true,true);
  scenario("Share Film pointer name idle",0x1681b8,0x168262,0x168250,4,true,false);
  scenario("Share Film pointer name focused",0x1681b8,0x168262,0x168250,4,true,true);
  scenario("Share File format pointer name",0x1681d0,0x168234,0x168255,4,true,true);
  scenario("lowest name id",ITEM,VALUE,1,4,true,false);
  scenario("highest name id",ITEM,VALUE,0x344,4,true,true);
  scenario("name id past table",ITEM,VALUE,0x345,4,false,false);
  scenario("unrelated pointer name",ITEM,0x16238c,0x16238f,4,false,true);
  scenario("no name",ITEM,VALUE,0,4,false,false);
  scenario("review fixed row",ITEM,0x169,0x157668,4,false,true);
  scenario("unrelated two string ids",ITEM,0xbf,0xbe,4,false,false);
  scenario("Setup action at capture table end",0x150bdc,0xbf,0xbe,4,false,true);
  scenario("Setup action at video table end",0x169588,0xbf,0xbe,4,false,true);
  scenario("centred row",ITEM,VALUE,0x55,5,false,true);
  scenario("right to left",ITEM,VALUE,0x55,6,false,true);
  JsonObject report=new JsonObject();report.addProperty("passed",true);report.addProperty("firmware_sha256",hash);
  report.addProperty("engine","Ghidra p-code emulation of the patched call at 0x8fc2a and the hook; string lookup 0x8a3c0 and text draw 0x78ce0 modelled, caller-saved registers trashed on return");
  report.add("scenarios",results);
  Files.writeString(build.resolve("ember-rowhook-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
  println("EMBER ROW HOOK COMPLETE "+results.size()+" scenarios");
 }
}
