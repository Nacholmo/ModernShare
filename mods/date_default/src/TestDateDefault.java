// Execute the patched default-date paths; memcpy and RTC services are mocked.
// @category Kodak
import java.nio.file.*;
import java.nio.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;
public class TestDateDefault extends GhidraScript {
 static final long SP=0x19f000;
 byte[] fw,expected; JsonArray results=new JsonArray();
 void require(boolean ok,String msg){if(!ok)throw new IllegalStateException(msg);}
 long reg(EmulatorHelper e,String r){return e.readRegister(r).longValue()&0xffffffffL;}
 byte[] tm(int year){return ByteBuffer.allocate(36).order(ByteOrder.LITTLE_ENDIAN).putInt(13).putInt(29).putInt(17).putInt(15).putInt(5).putInt(year-1900).putInt(2).putInt(165).putInt(0).array();}
 EmulatorHelper fresh(long pc){
  EmulatorHelper e=new EmulatorHelper(currentProgram);
  e.writeMemory(toAddr(0x30000),Arrays.copyOfRange(fw,0x200,0x100200));
  e.writeMemory(toAddr(0x130000),Arrays.copyOfRange(fw,0x100200,0x144c00));
  e.writeMemory(toAddr(SP-4096),new byte[8192]);
  for(int i=0;i<=25;i++)e.writeRegister("r"+i,0xabc00000L+i);
  e.writeRegister("sp",SP);e.writeRegister("blink",0x30010);e.writeRegister(e.getPCRegister(),pc);return e;
 }
 void returned(EmulatorHelper e,long value){long ret=reg(e,"blink");for(int i=0;i<=12;i++)e.writeRegister("r"+i,0xdead0000L+i);e.writeRegister("r0",value);e.writeRegister(e.getPCRegister(),ret);}
 void copy(EmulatorHelper e){long dest=reg(e,"r0"),src=reg(e,"r1"),n=reg(e,"r2");require(n==24||n==36,"copy size");e.writeMemory(toAddr(dest),e.readMemory(toAddr(src),(int)n));returned(e,dest);}
 void step(EmulatorHelper e)throws Exception{long pc=e.getExecutionAddress().getOffset();require(e.step(monitor),"step "+Long.toHexString(pc)+": "+e.getLastError());}
 void passed(String name,int steps){JsonObject r=new JsonObject();r.addProperty("name",name);r.addProperty("passed",true);r.addProperty("instructions_and_service_boundaries",steps);results.add(r);println("DATE PASS: "+name);}
 void screen(boolean boot,int year)throws Exception{
  long dest=boot?0x19d0b8:0x19d8c0,end=boot?0xdc46c:0xeae7c;
  EmulatorHelper e=fresh(boot?0xdc458:0xeae58);try{
   byte[] input=tm(year),tail=new byte[16];Arrays.fill(tail,(byte)0xa5);
   e.writeMemory(toAddr(dest),input);e.writeMemory(toAddr(dest+24),tail);
   if(!boot)e.writeRegister("r13",dest);
   int count=0,copies=0;
   while(e.getExecutionAddress().getOffset()!=end&&count++<80){
    if(e.getExecutionAddress().getOffset()==0x54010){require(reg(e,"r0")==dest&&reg(e,"r1")==0x1284ac&&reg(e,"r2")==24,"screen memcpy args");copy(e);copies++;}else step(e);
   }
   boolean fallback=boot||year<2007||year>2037;
   require(count<80&&copies==(fallback?1:0),"screen completion/copy count");
   require(Arrays.equals(e.readMemory(toAddr(dest),24),Arrays.copyOf(fallback?expected:input,24)),"screen date/time");
   require(Arrays.equals(e.readMemory(toAddr(dest+24),16),tail),"adjacent globals modified");
   require(reg(e,"sp")==SP,"screen stack");
   for(int i=13;i<=25;i++)require(reg(e,"r"+i)==(!boot&&i==13?dest:0xabc00000L+i),"screen saved r"+i);
   passed(boot?"boot screen default":"setup screen retained year "+year+(fallback?" falls back":" preserved"),count);
  }finally{e.dispose();}
 }
 void rtc(int year,boolean error)throws Exception{
  EmulatorHelper e=fresh(0xf05d2);try{
   e.writeRegister("r13",0x13cb50);e.writeRegister("r15",0);
   e.writeMemoryValue(toAddr(0x13cb68),1,0x55);
   int count=0,reads=0,sets=0;
   while(e.getExecutionAddress().getOffset()!=0xf05f8&&count++<80){long pc=e.getExecutionAddress().getOffset();
    if(pc==0x69390){require(reg(e,"r0")==0x16a6e4,"RTC read pointer");e.writeMemory(toAddr(0x16a6e4),tm(year));reads++;returned(e,error?1:0);}
    else if(pc==0x69424){require(reg(e,"r0")==0x16a708,"RTC fallback pointer");require(Arrays.equals(e.readMemory(toAddr(reg(e,"r0")),36),expected),"RTC fallback date");sets++;returned(e,0);}
    else step(e);
   }
   boolean fallback=error||year<2007;
   require(count<80&&reads==1&&sets==(fallback?1:0),"RTC service count");
   require((e.readMemoryByte(toAddr(0x13cb68))&255)==(fallback?1:0),"RTC date prompt flag");
   require(reg(e,"sp")==SP,"RTC stack");
   passed(error?"lost RTC read failure":"RTC year "+year+(fallback?" resets":" retained"),count);
  }finally{e.dispose();}
 }
 void reset(boolean setup)throws Exception{
  EmulatorHelper e=fresh(setup?0xeb220:0xdc23c);try{
   e.writeRegister("r0",0x180000);e.writeRegister("r1",0x5000);e.writeRegister("r2",0);
   int count=0,copies=0;boolean reached=false;
   while(count++<100){long pc=e.getExecutionAddress().getOffset();
    if(pc==0x54010){require(reg(e,"r1")== (setup?0x128540:0x1284ac)&&reg(e,"r2")==36,"reset template");copy(e);copies++;}
    else if(pc==0x7bee0){require(reg(e,"r0")==0x180000&&reg(e,"r1")==0x18,"setup reset enabled property");returned(e,1);}
    else if(pc==0x69424){require(Arrays.equals(e.readMemory(toAddr(reg(e,"r0")),36),expected),"reset date setter argument");reached=true;break;}
    else step(e);
   }
   require(reached&&copies==1,"reset reaches RTC setter");passed(setup?"setup Reset default action":"startup Reset default action",count);
  }finally{e.dispose();}
 }
 public void run()throws Exception{
  Path build=Path.of(getScriptArgs()[0]);fw=Files.readAllBytes(build.resolve("KC713.FW"));
  JsonObject m=JsonParser.parseString(Files.readString(build.resolve("manifest.json"))).getAsJsonObject();
  ByteBuffer b=ByteBuffer.allocate(36).order(ByteOrder.LITTLE_ENDIAN);for(JsonElement v:m.getAsJsonArray("struct_tm"))b.putInt(v.getAsInt());expected=b.array();
  String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw));require(hash.equals(m.get("firmware_sha256").getAsString()),"manifest hash");
  screen(true,2007);for(int y:new int[]{2007,2025,2026,2037,2006,1900,2038})screen(false,y);
  rtc(2026,true);for(int y:new int[]{2006,2007,2026,2037})rtc(y,false);
  reset(false);reset(true);
  JsonObject report=new JsonObject();report.addProperty("passed",true);report.addProperty("firmware_sha256",hash);report.addProperty("engine","Actual patched screen code, stock lost-RTC recovery and both default-reset paths through RTC setter; memcpy and hardware RTC/UI property services mocked");report.addProperty("limits","Snippet tests stop before screen rendering; reset action tests stop at RTC setter; no physical RTC or camera validation");report.add("scenarios",results);
  Files.writeString(build.resolve("date-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");println("DATE COMPLETE: "+results.size()+" scenarios");
 }
}
