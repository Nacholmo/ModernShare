// Actual menu/stock dispatch and capture-gate instructions; UI services are mocked.
// @category Kodak
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;
public class TestShareMenu extends GhidraScript {
 static final long ROOT=0x180000,LIST=0x168154,ITEMS=0x1681b8,FLAG=0x13358c,SP=0x19f000,RET=0x30010;
 Path build;byte[] fw;JsonObject manifest;JsonArray results=new JsonArray();
 long reg(EmulatorHelper e,String r){return e.readRegister(r).longValue()&0xffffffffL;}
 long word(EmulatorHelper e,long p){byte[] b=e.readMemory(toAddr(p),4);return ((long)b[0]&255)|((long)(b[1]&255)<<8)|((long)(b[2]&255)<<16)|((long)(b[3]&255)<<24);}
 void require(boolean b,String s){if(!b)throw new IllegalStateException(s);}
 void returned(EmulatorHelper e,long value){long pc=reg(e,"blink");for(int i=0;i<=12;i++)e.writeRegister("r"+i,0xdead0000L+i);e.writeRegister("r0",value);e.writeRegister(e.getPCRegister(),pc);}
 // Known SLEIGH ld.ab base/destination alias issue in compiler helper: model its
 // intended verified restore at this boundary, rather than executing the broken p-code.
 void restore(EmulatorHelper e,long pc){int n=1+(int)((0x11ae5c-pc)/8);long sp=reg(e,"sp");for(int i=0;i<n;i++)e.writeRegister("r"+(13+i),word(e,sp+4*i));long ret=word(e,sp+4*n);e.writeRegister("sp",sp+4*n+4);e.writeRegister("blink",ret);e.writeRegister(e.getPCRegister(),ret);}
 EmulatorHelper fresh(){EmulatorHelper e=new EmulatorHelper(currentProgram);e.writeMemory(toAddr(0x30000),Arrays.copyOfRange(fw,0x200,0x100200));e.writeMemory(toAddr(0x130000),Arrays.copyOfRange(fw,0x100200,0x144c00));e.writeMemory(toAddr(SP-4096),new byte[8192]);e.writeMemory(toAddr(ROOT),new byte[64]);return e;}
 void registers(EmulatorHelper e,long pc,long r0,long r1,long r2){for(int i=0;i<=25;i++)e.writeRegister("r"+i,0xabc00000L+i);e.writeRegister("r0",r0);e.writeRegister("r1",r1);e.writeRegister("r2",r2);e.writeRegister("sp",SP);e.writeRegister("blink",RET);e.writeRegister(e.getPCRegister(),pc);}
 void event(EmulatorHelper e,String name,long event,int initial,int mode,boolean missing) throws Exception {
  e.writeMemoryValue(toAddr(FLAG),1,initial);e.writeMemoryValue(toAddr(0x132904),1,mode);
  byte[] header=e.readMemory(toAddr(0x1241a0),1536);int jpeg=e.readMemoryByte(toAddr(0x133185));
  long start=Long.decode(manifest.getAsJsonObject("symbols").get("start").getAsString());registers(e,start,ROOT,event,0x12345678);
  int steps=0,selects=0,opens=0,defaults=0;long opened=-1;boolean expectToggle=event==0x5000;
  while(steps++<1000){long pc=e.getExecutionAddress().getOffset();if(pc==RET)break;
   if(pc>=0x11ae3c&&pc<=0x11ae5c&&(0x11ae5c-pc)%8==0){restore(e,pc);continue;}
   if(pc==0x7c460){require(reg(e,"r0")==ROOT&&reg(e,"r1")==0x4804,"list lookup arguments");returned(e,missing?0:LIST);continue;}
   if(pc==0x8f26c){require(reg(e,"r0")==LIST&&reg(e,"r1")==0,"initial list selection");selects++;returned(e,0);continue;}
   if(pc==0x7bfcc){require(reg(e,"r0")==ROOT,"refresh root");e.writeRegister("r1",0x4409);e.writeRegister("r2",0);e.writeRegister(e.getPCRegister(),start);continue;}
   if(pc==0xb953c){require(reg(e,"r0")==ROOT&&reg(e,"r1")==event&&reg(e,"r2")==0x12345678,"default delegation arguments");defaults++;returned(e,0);continue;}
   if(pc==0x7c260){opened=reg(e,"r0");require(reg(e,"r1")==0,"screen-open payload");opens++;returned(e,0);continue;}
   if(pc==0x456f0){require(reg(e,"r0")==0x61,"mode-dial query");returned(e,1);continue;}
   require(e.step(monitor),"menu at "+Long.toHexString(pc)+": "+e.getLastError());
  }
  require(steps<1000&&reg(e,"sp")==SP&&reg(e,"blink")==RET&&reg(e,"r0")==0,"return/stack/status");
  for(int i=13;i<=25;i++)require(reg(e,"r"+i)==0xabc00000L+i,"callee-saved r"+i);
  int value=e.readMemoryByte(toAddr(FLAG))&255;require(value==(expectToggle?(initial^1):initial),"DNG flag state");
  require((e.readMemoryByte(toAddr(0x132904))&255)==mode,"camera mode modified");
  require(e.readMemoryByte(toAddr(0x133185))==jpeg&&Arrays.equals(header,e.readMemory(toAddr(0x1241a0),1536)),"JPEG flag or DNG header modified");
  if(event==0x4405||event==0x4409||expectToggle){if(!missing)require(e.readNullTerminatedString(toAddr(word(e,ITEMS+4)),64).equals(value==0?"DNG saving: OFF":"DNG saving: ON"),"displayed DNG status");}
  require(selects==(event==0x4405?1:0),"selection count");
  boolean close=event==0x680||event==0x780||event==0x700;
  require(opens==((event==0x5001||close)?1:0),"open count");
  if(event==0x5001)require(opened==0x3b,"hidden menu ID");
  if(close)require(opened==(mode==1?1:0x7c),"return to capture/review");
  require(defaults==((event==0x4403||event==0x681||event==0x1234)?1:0),"default callback count");
  JsonObject r=new JsonObject();r.addProperty("name",name);r.addProperty("event",String.format("0x%x",event));r.addProperty("passed",true);r.addProperty("instructions",steps);r.addProperty("dng_enabled",value!=0);results.add(r);println("SHARE MENU PASS: "+name);
 }
 void gate(boolean enabled) throws Exception {EmulatorHelper e=fresh();try{
  e.writeMemoryValue(toAddr(FLAG),1,enabled?1:0);e.writeMemoryValue(toAddr(0x1324fc),4,0x2e3000);e.writeMemoryValue(toAddr(0x2e3004),4,0x300000);e.writeMemoryValue(toAddr(0x2e3034),4,1234);
  registers(e,0x33d10,0,0,0);e.writeRegister("r14",0x1324dc);
  int steps=0;boolean called=false;
  while(steps++<100){long pc=e.getExecutionAddress().getOffset();if(pc==0x33d32)break;if(pc==0x67a18){returned(e,7096320);continue;}if(pc==0x67898){called=true;require(reg(e,"r0")==0&&reg(e,"r1")==1234&&reg(e,"r2")==0x300000&&reg(e,"r3")==7096320,"capture writer arguments");break;}require(e.step(monitor),"gate: "+e.getLastError());}
  require(steps<100&&called==enabled,"stock capture gate");JsonObject r=new JsonObject();r.addProperty("name",enabled?"capture DNG ON":"capture DNG OFF");r.addProperty("passed",true);r.addProperty("writer_called",called);results.add(r);
 }finally{e.dispose();}}
 void captureOpen() throws Exception {EmulatorHelper e=fresh();try{
  e.writeMemoryValue(toAddr(0x132904),1,1);registers(e,0xcbd00,0xdead,0xdead,0);int steps=0,opens=0;
  while(steps++<20){long pc=e.getExecutionAddress().getOffset();if(pc==0xcbd0e)break;if(pc==0x7c260){require(reg(e,"r0")==0xa8&&reg(e,"r1")==0,"capture opens mod menu");opens++;returned(e,0);continue;}require(pc!=0x3c4e0,"capture mode switched to review");require(e.step(monitor),"capture open: "+e.getLastError());}
  require(steps<20&&opens==1&&e.readMemoryByte(toAddr(0x132904))==1,"capture mode retained");JsonObject r=new JsonObject();r.addProperty("name","capture opening retains mode");r.addProperty("passed",true);results.add(r);
 }finally{e.dispose();}}
 public void run() throws Exception {
  build=Path.of(getScriptArgs()[0]);fw=Files.readAllBytes(build.resolve("KC713.FW"));manifest=JsonParser.parseString(Files.readString(build.resolve("manifest.json"))).getAsJsonObject();
  EmulatorHelper e=fresh();try{
   require(e.readMemoryByte(toAddr(FLAG))==1,"DNG boot default");
   event(e,"open enabled",0x4405,1,1,false);event(e,"toggle off",0x5000,1,1,false);event(e,"reopen remains off",0x4405,0,1,false);event(e,"toggle on",0x5000,0,1,false);
   event(e,"refresh enabled",0x4409,1,1,false);event(e,"refresh disabled",0x4409,0,1,false);event(e,"missing list refresh",0x4409,1,1,true);
   event(e,"hidden menu capture",0x5001,1,1,false);event(e,"hidden menu review",0x5001,0,2,false);
   event(e,"close Share capture",0x680,1,1,false);event(e,"close Menu capture",0x780,0,1,false);event(e,"close Delete capture",0x700,1,1,false);event(e,"close Share review",0x680,0,2,false);
   event(e,"creation default",0x4403,1,1,false);event(e,"Share release default",0x681,1,1,false);event(e,"unknown default",0x1234,1,1,false);
  }finally{e.dispose();}
  gate(false);gate(true);captureOpen();
  JsonObject report=new JsonObject();report.addProperty("passed",true);report.addProperty("firmware_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw)));report.addProperty("engine","Actual custom callbacks, stock event dispatch, stock close handler and stock CFA gate; UI services mocked; compiler restore boundary modeled for known SLEIGH alias issue");report.add("scenarios",results);Files.writeString(build.resolve("menu-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");println("SHARE MENU COMPLETE: "+results.size()+" scenarios");
 }
}
