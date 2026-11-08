// Actual native dispatch, menu, film getters and capture gate; UI services mocked.
// @category Kodak
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;
import ghidra.program.model.symbol.Reference;
public class TestModSettings extends GhidraScript {
 static final long ROOT=0x180000,LIST=0x168154,ITEMS=0x1681b8,FLAG=0x13358c,SP=0x19f000,RET=0x30010,TAB=0x125780;
 byte[] fw;JsonObject manifest;JsonArray results=new JsonArray();long state,start;
 long reg(EmulatorHelper e,String r){return e.readRegister(r).longValue()&0xffffffffL;}
 long word(EmulatorHelper e,long p){byte[] b=e.readMemory(toAddr(p),4);return ((long)b[0]&255)|((long)(b[1]&255)<<8)|((long)(b[2]&255)<<16)|((long)(b[3]&255)<<24);}
 void require(boolean b,String s){if(!b)throw new IllegalStateException(s);}
 void returned(EmulatorHelper e,long value){long pc=reg(e,"blink");for(int i=0;i<=12;i++)e.writeRegister("r"+i,0xdead0000L+i);e.writeRegister("r0",value);e.writeRegister(e.getPCRegister(),pc);}
 // Model the verified compiler restore boundary for the known SLEIGH ld.ab alias issue.
 void restore(EmulatorHelper e,long pc){int n=1+(int)((0x11ae5c-pc)/8);long sp=reg(e,"sp");for(int i=0;i<n;i++)e.writeRegister("r"+(13+i),word(e,sp+4*i));long ret=word(e,sp+4*n);e.writeRegister("sp",sp+4*n+4);e.writeRegister("blink",ret);e.writeRegister(e.getPCRegister(),ret);}
 EmulatorHelper fresh(){EmulatorHelper e=new EmulatorHelper(currentProgram);e.writeMemory(toAddr(0x30000),Arrays.copyOfRange(fw,0x200,0x100200));e.writeMemory(toAddr(0x130000),Arrays.copyOfRange(fw,0x100200,0x144c00));e.writeMemory(toAddr(SP-4096),new byte[8192]);e.writeMemory(toAddr(ROOT),new byte[64]);return e;}
 void registers(EmulatorHelper e,long pc,long r0,long r1,long r2){for(int i=0;i<=25;i++)e.writeRegister("r"+i,0xabc00000L+i);e.writeRegister("r0",r0);e.writeRegister("r1",r1);e.writeRegister("r2",r2);e.writeRegister("sp",SP);e.writeRegister("blink",RET);e.writeRegister(e.getPCRegister(),pc);}
 byte[] map(int film){byte[] b=new byte[24];if(film==0){b[9]=2;b[17]=3;b[22]=1;}else Arrays.fill(b,(byte)(film-1));return b;}
 void passed(String name,int steps){JsonObject r=new JsonObject();r.addProperty("name",name);r.addProperty("passed",true);r.addProperty("instructions_and_service_boundaries",steps);results.add(r);println("MOD SETTINGS PASS: "+name);}
 int event(EmulatorHelper e,String name,long event,int dng,int mode,int film,boolean missing)throws Exception{
  e.writeMemoryValue(toAddr(FLAG),1,dng);e.writeMemoryValue(toAddr(0x132904),1,mode);e.writeMemoryValue(toAddr(state),1,film);e.writeMemory(toAddr(TAB),map(film));
  byte[] header=e.readMemory(toAddr(0x1241a0),1536),before=e.readMemory(toAddr(TAB-16),16),after=e.readMemory(toAddr(TAB+24),16);
  int jpeg=e.readMemoryByte(toAddr(0x133185));registers(e,start,ROOT,event,0x12345678);
  int steps=0,selects=0,opens=0,defaults=0,refreshes=0;long opened=-1;
  while(steps++<1000){long pc=e.getExecutionAddress().getOffset();if(pc==RET)break;
   if(pc>=0x11ae3c&&pc<=0x11ae5c&&(0x11ae5c-pc)%8==0){restore(e,pc);continue;}
   if(pc==0x7c460){require(reg(e,"r0")==ROOT&&reg(e,"r1")==0x4804,"list lookup");returned(e,missing?0:LIST);continue;}
   if(pc==0x8f26c){require(reg(e,"r0")==LIST&&reg(e,"r1")==0,"initial selection");selects++;returned(e,0);continue;}
   if(pc==0x7bfcc){require(reg(e,"r0")==ROOT,"refresh root");refreshes++;e.writeRegister("r1",0x4409);e.writeRegister("r2",0);e.writeRegister(e.getPCRegister(),start);continue;}
   if(pc==0xb953c){require(reg(e,"r0")==ROOT&&reg(e,"r1")==event&&reg(e,"r2")==0x12345678,"default delegation");defaults++;returned(e,0);continue;}
   if(pc==0x7c260){opened=reg(e,"r0");require(reg(e,"r1")==0,"screen payload");opens++;returned(e,0);continue;}
   if(pc==0x456f0){require(reg(e,"r0")==0x61,"mode dial query");returned(e,1);continue;}
   require(e.step(monitor),"event "+name+" at "+Long.toHexString(pc)+": "+e.getLastError());
  }
  require(steps<1000&&reg(e,"sp")==SP&&reg(e,"blink")==RET&&reg(e,"r0")==0,"return/stack/status");
  for(int i=13;i<=25;i++)require(reg(e,"r"+i)==0xabc00000L+i,"callee saved r"+i);
  int next=event==0x5001?(film+1)%5:film,value=event==0x5000?(dng^1):dng;
  require((e.readMemoryByte(toAddr(state))&255)==next&&Arrays.equals(e.readMemory(toAddr(TAB),24),map(next)),"selected film map");
  require((e.readMemoryByte(toAddr(FLAG))&255)==value,"DNG state");
  require(e.readMemoryByte(toAddr(0x133185))==jpeg&&Arrays.equals(header,e.readMemory(toAddr(0x1241a0),1536)),"JPEG flag/DNG header changed");
  require(Arrays.equals(before,e.readMemory(toAddr(TAB-16),16))&&Arrays.equals(after,e.readMemory(toAddr(TAB+24),16)),"film table guard bytes");
  require((e.readMemoryByte(toAddr(0x132904))&255)==mode,"capture mode changed");
  if(!missing&&(event==0x4405||event==0x4409||event==0x5000||event==0x5001)){
   require(e.readNullTerminatedString(toAddr(word(e,ITEMS+4)),64).equals(value==0?"DNG saving: OFF":"DNG saving: ON"),"DNG label");
   long label=Long.decode(manifest.getAsJsonObject("labels").get("FILM_"+next).getAsString());
   require(word(e,ITEMS+28)==label,"film label pointer");
  }
  require(e.readNullTerminatedString(toAddr(word(e,ITEMS+76)),64).equals("FW: "+manifest.get("version").getAsString()),"version row");
  require(selects==(event==0x4405?1:0)&&refreshes==((event==0x5000||event==0x5001)?1:0),"UI callback counts");
  boolean close=event==0x680||event==0x780||event==0x700;
  require(opens==((event==0x5002||close)?1:0),"open count");
  if(event==0x5002)require(opened==0x3b,"hidden menu target");if(close)require(opened==(mode==1?1:0x7c),"close target");
  require(defaults==((event==0x4403||event==0x681||event==0x1234)?1:0),"default count");passed(name,steps);return next;
 }
 void getters(int film)throws Exception{
  EmulatorHelper e=fresh();try{
   e.writeMemoryValue(toAddr(state),1,film);e.writeMemory(toAddr(TAB),map(film));int checks=0;
   for(int i=0;i<3;i++)e.writeMemoryValue(toAddr(0x197868+4*i),4,0x16cac8+48*i);
   for(int i=0;i<3;i++)e.writeMemoryValue(toAddr(0x19787c+4*i),4,0x16cb58+48*i);
   byte[] h=e.readMemory(toAddr(0x1241a0),1536);int d=e.readMemoryByte(toAddr(FLAG));
   for(int mode:new int[]{0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,255}){
    e.writeMemoryValue(toAddr(0x1328ff),1,mode);int selected=map(film)[mode<24?mode:0];
    for(int arg=0;arg<6;arg++){
     boolean ccm=arg<3;int input=ccm?arg:arg-3+2;
     registers(e,ccm?0xaf508:0xaf514,input,0x12345678,0x87654321L);int steps=0;
     while(e.getExecutionAddress().getOffset()!=RET&&steps++<100)require(e.step(monitor),"film getter: "+e.getLastError());
     long expected=selected==0?(ccm?0x16cac8+48*input:0x16cb58+48*(input==3?1:input==4?2:0)):
       0x1257a0+192*(selected-1)+48*(ccm?input:3);
     require(steps<100&&reg(e,"r0")==expected,"getter film="+film+" mode="+mode+" arg="+input+" got="+Long.toHexString(reg(e,"r0"))+" expected="+Long.toHexString(expected));
     require(reg(e,"sp")==SP&&reg(e,"r2")==0x87654321L&&reg(e,"blink")==RET,"getter ABI");checks++;
    }
   }
   require(Arrays.equals(h,e.readMemory(toAddr(0x1241a0),1536))&&d==e.readMemoryByte(toAddr(FLAG)),"getter changed DNG");
   passed("film "+film+": "+checks+" actual CCM/Ymat getter cases",checks);
  }finally{e.dispose();}
 }
 void gate(boolean enabled)throws Exception{EmulatorHelper e=fresh();try{
  e.writeMemoryValue(toAddr(FLAG),1,enabled?1:0);e.writeMemoryValue(toAddr(0x1324fc),4,0x2e3000);e.writeMemoryValue(toAddr(0x2e3004),4,0x300000);e.writeMemoryValue(toAddr(0x2e3034),4,1234);
  registers(e,0x33d10,0,0,0);e.writeRegister("r14",0x1324dc);int steps=0;boolean called=false;
  while(steps++<100){long pc=e.getExecutionAddress().getOffset();if(pc==0x33d32)break;if(pc==0x67a18){returned(e,7096320);continue;}if(pc==0x67898){called=true;require(reg(e,"r0")==0&&reg(e,"r1")==1234&&reg(e,"r2")==0x300000&&reg(e,"r3")==7096320,"writer arguments");break;}require(e.step(monitor),"gate: "+e.getLastError());}
  require(steps<100&&called==enabled,"capture gate");passed(enabled?"capture DNG ON":"capture DNG OFF",steps);
 }finally{e.dispose();}}
 void allocationAudit(Path build)throws Exception{
  JsonArray refs=new JsonArray();for(long[] range:new long[][]{{0x1247a0,0x124800},{0x1259e0,0x125a00}})
   for(long at=range[0];at<range[1];at++)for(Reference ref:getReferencesTo(toAddr(at))){JsonObject r=new JsonObject();r.addProperty("from",ref.getFromAddress().toString());r.addProperty("to",Long.toHexString(at));refs.add(r);}
  JsonObject report=new JsonObject();report.add("stock_static_references_into_extensions",refs);report.addProperty("passed",refs.size()==0);Files.writeString(build.resolve("static-placement-audit.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");require(refs.size()==0,"extension has stock references");
 }
 public void run()throws Exception{
  Path build=Path.of(getScriptArgs()[0]);fw=Files.readAllBytes(build.resolve("KC713.FW"));manifest=JsonParser.parseString(Files.readString(build.resolve("manifest.json"))).getAsJsonObject();
  state=Long.decode(manifest.get("film_state_address").getAsString());start=Long.decode(manifest.getAsJsonObject("symbols").get("start").getAsString());
  String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw));require(hash.equals(manifest.get("firmware_sha256").getAsString()),"firmware manifest hash");allocationAudit(build);
  EmulatorHelper e=fresh();try{
   require(e.readMemoryByte(toAddr(FLAG))==1&&e.readMemoryByte(toAddr(state))==0&&Arrays.equals(e.readMemory(toAddr(TAB),24),map(0)),"boot defaults");
   event(e,"open defaults",0x4405,1,1,0,false);event(e,"DNG OFF",0x5000,1,1,0,false);event(e,"DNG ON",0x5000,0,1,0,false);
   for(int f=0;f<5;f++){int next=event(e,"next film from "+f,0x5001,1,1,f,false);event(e,"reopen film "+next,0x4405,0,1,next,false);event(e,"refresh film "+next,0x4409,1,1,next,false);}
   event(e,"missing list refresh",0x4409,1,1,3,true);event(e,"film change missing list",0x5001,0,1,4,true);
   event(e,"version row inert",0x5003,1,1,2,false);event(e,"hidden capture",0x5002,1,1,4,false);event(e,"hidden review",0x5002,0,2,1,false);
   event(e,"close Share capture",0x680,1,1,1,false);event(e,"close Menu capture",0x780,0,1,2,false);event(e,"close Delete capture",0x700,1,1,3,false);event(e,"close Share review",0x680,0,2,4,false);
   event(e,"creation delegates",0x4403,1,1,0,false);event(e,"release delegates",0x681,1,1,0,false);event(e,"unknown delegates",0x1234,1,1,0,false);
  }finally{e.dispose();}
  for(int f=0;f<5;f++)getters(f);gate(false);gate(true);
  JsonObject report=new JsonObject();report.addProperty("passed",true);report.addProperty("firmware_sha256",hash);report.addProperty("engine","Actual menu, stock event dispatcher/close handler, both stock hooked matrix getters and capture gate; UI services mocked; compiler restore boundary modeled for known SLEIGH alias issue");report.addProperty("matrix_getter_cases",780);report.add("scenarios",results);Files.writeString(build.resolve("menu-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");println("MOD SETTINGS COMPLETE: "+results.size()+" scenarios including 780 matrix cases");
 }
}
