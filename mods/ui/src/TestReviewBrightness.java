// Actual ARC Review override, native MMIO backlight logic, UI handlers and SD record I/O.
// @category Kodak
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.*;
import ghidra.app.emulator.EmulatorHelper;

public class TestReviewBrightness extends TestSettings {
 static final long OPTION=0x1683a8,MODE=0x132904,NORMAL=0x13295f,LCD=0x1328f2,MMIO=0xfef00d8;
 @Override long statusAddress(){return 0x16841c;}
 @Override String dngLabel(boolean enabled){return enabled?"JPEG + DNG":"JPEG";}
 long ui(String name){return Long.decode(manifest.getAsJsonObject("symbols").get(name).getAsString());}
 int byteAt(EmulatorHelper e,long address){return e.readMemoryByte(toAddr(address))&255;}
 byte[] config(int film,int dng,int review,long generation){return record(film,dng|(review<<1),generation);}
 class ReviewFS extends Filesystem {
  int selected=-1;List<Long> screens=new ArrayList<>();
  ReviewFS(byte[] a,byte[] b){super(a,b);}
  @Override boolean service(EmulatorHelper e,long pc){
   if(pc==0x7bfcc){require(reg(e,"r0")==ROOT||reg(e,"r0")==0,"root or suppressed repaint");repaints++;returned(e,0);return true;}
   if(pc==0x7c460){require(reg(e,"r0")==ROOT&&reg(e,"r1")==0x4804,"Share lookup");returned(e,LIST);return true;}
   if(pc==0x8f26c){selected=(int)reg(e,"r1");require(reg(e,"r0")==LIST&&(selected==0||selected==2),"Share selected row");selects++;returned(e,0);return true;}
   if(pc==0x7c260){require(reg(e,"r1")==0,"screen argument");screens.add(reg(e,"r0"));returned(e,0);return true;}
   return super.service(e,pc);
  }
 }
 int call(EmulatorHelper e,ReviewFS fs,long entry,long r0,long r1)throws Exception{
  byte[] header=e.readMemory(toAddr(0x1241a0),1536);int jpeg=byteAt(e,0x133185);
  registers(e,entry,r0,r1,0x12345678);int steps=0;
  while(steps++<5000){long pc=e.getExecutionAddress().getOffset();if(pc==RET)break;
   require(pc!=0xfe450&&pc!=0xd6f0c,"no firmware flashing");
   if(pc>=0x11ae14&&pc<=0x11ae5c&&(0x11ae5c-pc)%8==0){restore(e,pc);continue;}
   if(fs!=null&&fs.service(e,pc))continue;
   require(e.step(monitor),"entry="+Long.toHexString(entry)+" pc="+Long.toHexString(pc)+" "+e.getLastError());
  }
  require(steps<5000&&reg(e,"sp")==SP&&reg(e,"blink")==RET,"return and stack at "+Long.toHexString(entry));
  for(int i=13;i<=25;i++)require(reg(e,"r"+i)==0xabc00000L+i,"saved r"+i);
  require(Arrays.equals(header,e.readMemory(toAddr(0x1241a0),1536))&&byteAt(e,0x133185)==jpeg,"capture header/JPEG unchanged");
  if(fs!=null)require(fs.handles.isEmpty(),"no file handle leak");return steps;
 }
 void hardware(EmulatorHelper e,int request,int model,int option,int mode){
  int effective=option!=0&&mode==4?1:request;
  boolean bit=(model==2||model==3)?effective==2:effective==1;
  long expected=(0xa5a1&~4)|(bit?4:0);
  require((word(e,MMIO)&0xffff)==expected,"backlight polarity/model="+model+" mode="+mode+" option="+option+" request="+request);
  require(byteAt(e,NORMAL)==2,"physical override must not overwrite saved normal brightness");
 }
 void hardwareMatrix()throws Exception{
  for(int option=0;option<2;option++)for(int mode:new int[]{0,1,2,3,4,5})for(int model:new int[]{1,2,3})for(int request:new int[]{1,2}){
   EmulatorHelper e=fresh();try{
    e.writeMemoryValue(toAddr(OPTION),1,option);e.writeMemoryValue(toAddr(MODE),1,mode);e.writeMemoryValue(toAddr(NORMAL),1,2);
    e.writeMemoryValue(toAddr(LCD),2,model);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
    int steps=call(e,null,0x40240,request,0);hardware(e,request,model,option,mode);
    passed("physical override option="+option+" mode="+mode+" lcd="+model+" request="+request,steps);
   }finally{e.dispose();}
  }
 }
 void transitions()throws Exception{
  for(int model:new int[]{1,2,3}){
   EmulatorHelper e=fresh();try{
    e.writeMemoryValue(toAddr(SDSTATE),4,1);e.writeMemoryValue(toAddr(OPTION),1,1);
    e.writeMemoryValue(toAddr(NORMAL),1,2);e.writeMemoryValue(toAddr(LCD),2,model);
    int steps=0;
    for(int mode:new int[]{4,1,4,2,3,4,0}){
     e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);steps+=call(e,null,0x3c4e0,mode,0);
     require(byteAt(e,MODE)==mode,"native mode stored");hardware(e,2,model,1,mode);
    }
    passed("Review entry/exit restores normal setting lcd="+model,steps);
   }finally{e.dispose();}
  }
 }
 void loadRecord(String name,byte[] a,byte[] b,int film,int dng,int review,long gen,int slot,boolean loaded)throws Exception{
  EmulatorHelper e=fresh();try{
   ReviewFS fs=new ReviewFS(a,b);e.writeMemoryValue(toAddr(NORMAL),1,2);e.writeMemoryValue(toAddr(LCD),2,1);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
   int steps=call(e,fs,symbol("capture_init"),ROOT,0x4405);
   choice(e,film,dng);require(byteAt(e,OPTION)==review,"Review flag restored");
   require(word(e,SDSTATE)==1&&word(e,SDSTATE+4)==gen&&word(e,SDSTATE+8)==slot,"generation/slot");
   require(status(e).equals(loaded?"v0.9: SD loaded":"v0.9: defaults"),"status");
   require(fs.opens==2&&fs.writes==0,"read only startup");hardware(e,2,1,review,1);
   int opens=fs.opens;steps+=call(e,fs,ui("start"),ROOT,0x4405);require(fs.opens==opens&&fs.selected==0,"load once and initial selection");
   require(word(e,ITEMS+76)==(review==0?Long.decode(manifest.getAsJsonObject("labels").get("REVIEW_NORMAL").getAsString()):0x1e1),"Review row display");
   require(word(e,ITEMS+52)==0x1e0,"normal brightness row");passed(name,steps);
  }finally{e.dispose();}
 }
 void persistence()throws Exception{
  loadRecord("missing records preserve default Review Normal",null,null,0,0,0,0,1,false);
  for(int film=0;film<7;film++)for(int dng=0;dng<2;dng++)for(int review=0;review<2;review++)
   loadRecord("restore film="+film+" dng="+dng+" review="+review,config(film,dng,review,19),null,film,dng,review,19,0,true);
  loadRecord("newest B carries Review flag",config(1,0,0,20),config(6,1,1,21),6,1,1,21,1,true);
  loadRecord("sequence wrap retains Review flag",config(1,1,0,0xffffffffL),config(5,0,1,0),5,0,1,0,1,true);
  loadRecord("ties prefer A",config(2,0,1,7),config(4,1,0,7),2,0,1,7,0,true);
  for(String invalid:new String[]{"magic","checksum","short","film7","reserved","schema"}){
   byte[] bad=config(3,1,1,22);
   if(invalid.equals("magic"))bad[0]^=1;
   if(invalid.equals("checksum"))bad[12]^=1;
   if(invalid.equals("short"))bad=Arrays.copyOf(bad,7);
   if(invalid.equals("film7"))bad=config(7,1,1,22);
   if(invalid.equals("reserved")||invalid.equals("schema")){
    ByteBuffer buf=ByteBuffer.wrap(bad).order(ByteOrder.LITTLE_ENDIAN);int flags=buf.getInt(4)^(invalid.equals("schema")?0x30000:4);
    buf.putInt(4,flags);buf.putInt(12,~(buf.getInt(0)^flags^buf.getInt(8)));
   }
   loadRecord("reject invalid newer "+invalid,config(1,0,1,9),bad,1,0,1,9,0,true);
  }
  for(String fault:new String[]{"open","read","read-short","read-close"}){
   EmulatorHelper e=fresh();try{
    ReviewFS fs=new ReviewFS(config(1,0,1,8),config(6,1,0,9));fs.failSlot=1;fs.fault=fault;
    int steps=call(e,fs,symbol("capture_init"),ROOT,0x4405);choice(e,1,0);require(byteAt(e,OPTION)==1,"read failure fallback");passed("read failure "+fault,steps);
   }finally{e.dispose();}
  }
 }
 void actions()throws Exception{
  EmulatorHelper e=fresh();try{
   ReviewFS fs=new ReviewFS(config(3,0,0,11),null);
   e.writeMemoryValue(toAddr(NORMAL),1,2);e.writeMemoryValue(toAddr(LCD),2,1);
   int steps=call(e,fs,ui("start"),ROOT,0x4405);choice(e,3,0);
   steps+=call(e,fs,ui("start"),ROOT,0x5003);require(byteAt(e,OPTION)==1&&Arrays.equals(fs.slots[1],config(3,0,1,12)),"toggle saves Review flag");
   steps+=call(e,fs,ui("start"),ROOT,0x5001);choice(e,3,1);require(Arrays.equals(fs.slots[0],config(3,1,1,13)),"format save retains Review flag");
   steps+=call(e,fs,ui("start"),ROOT,0x5000);choice(e,4,1);require(Arrays.equals(fs.slots[1],config(4,1,1,14)),"film save retains Review flag");
   e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);steps+=call(e,fs,0x3c4e0,4,0);hardware(e,2,1,1,4);
   e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);steps+=call(e,fs,ui("start"),ROOT,0x5003);hardware(e,2,1,0,4);
   require(Arrays.equals(fs.slots[0],config(4,1,0,15))&&status(e).equals("v0.9: SD saved"),"disable immediately restores and saves");
   int writes=fs.writes;steps+=call(e,fs,ui("start"),ROOT,0x5002);
   require(fs.screens.get(fs.screens.size()-1)==0x9e&&byteAt(e,0x132919)==0xa8,"shortcut opens native brightness with ModernShare return");
   // Native Cancel/finish handler consults the saved return screen.
   steps+=call(e,fs,0xeab78,ROOT,0x700);require(fs.screens.get(fs.screens.size()-1)==0xa8,"native return to ModernShare");
   steps+=call(e,fs,ui("start"),ROOT,0x4405);require(fs.selected==2&&byteAt(e,OPTION+1)==0,"brightness row retained on return");
   steps+=call(e,fs,ui("start"),ROOT,0x5004);require(fs.screens.get(fs.screens.size()-1)==0x3b&&fs.writes==writes,"Hidden menu retained without save");
   passed("Review toggle/film/format/shortcut/return/Hidden integration",steps);
  }finally{e.dispose();}
  for(String fault:new String[]{"create","write","write-short","write-close"}){
   EmulatorHelper x=fresh();try{
    ReviewFS fs=new ReviewFS(config(2,0,0,20),config(1,1,1,19));call(x,fs,symbol("capture_init"),ROOT,0x4405);
    byte[] active=fs.slots[0].clone();fs.failSlot=1;fs.fault=fault;
    int steps=call(x,fs,ui("start"),ROOT,0x5003);
    require(byteAt(x,OPTION)==1&&word(x,SDSTATE+4)==20&&word(x,SDSTATE+8)==0,"save failure keeps active session and committed slot");
    require(Arrays.equals(fs.slots[0],active)&&status(x).equals("v0.9: SD error"),"failure feedback and previous record preserved");
    if(fault.equals("write-short"))loadRecord("interrupted write restores previous Review choice",fs.slots[0],fs.slots[1],2,0,0,20,0,true);
    fs.fault="";steps+=call(x,fs,ui("start"),ROOT,0x5001);
    require(Arrays.equals(fs.slots[1],config(2,1,1,21)),"retry persists active Review option");passed("write failure and retry "+fault,steps);
   }finally{x.dispose();}
  }
 }
 void reviewStartup()throws Exception{
  for(int review:new int[]{0,1}){
   EmulatorHelper e=fresh();try{
    ReviewFS fs=new ReviewFS(null,config(6,1,review,25));e.writeMemoryValue(toAddr(NORMAL),1,2);
    e.writeMemoryValue(toAddr(LCD),2,1);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
    int steps=call(e,fs,0x3c4e0,4,0);hardware(e,2,1,review,4);choice(e,6,1);
    require(byteAt(e,OPTION)==review&&fs.opens==2&&fs.inits==0,"Review-first reads SD without capture init");
    int opens=fs.opens;e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);steps+=call(e,fs,0x3c4e0,1,0);
    if(review!=0)hardware(e,2,1,review,1);
    steps+=call(e,fs,symbol("capture_init"),ROOT,0x4405);require(fs.opens==opens,"later capture does not reload");
    passed("Review-button startup review="+review,steps);
   }finally{e.dispose();}
  }
  for(int mode:new int[]{1,4})for(int option:new int[]{0,1})for(long setter:new long[]{0xeabb0,0xeabb8}){
   EmulatorHelper e=fresh();try{
    e.writeMemoryValue(toAddr(MODE),1,mode);e.writeMemoryValue(toAddr(OPTION),1,option);e.writeMemoryValue(toAddr(LCD),2,1);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
    int steps=call(e,null,setter,0,0);int normal=setter==0xeabb0?1:2;
    require(byteAt(e,NORMAL)==normal,"native brightness choice saved unchanged");
    int effective=option!=0&&mode==4?1:normal;
    require((word(e,MMIO)&4)==(effective==1?4:0),"native choice respects only Review override");
    passed("native brightness choice mode="+mode+" option="+option+" value="+normal,steps);
   }finally{e.dispose();}
  }
 }
 public void run()throws Exception{
  Path build=Path.of(getScriptArgs()[0]);fw=Files.readAllBytes(build.resolve("KC713.FW"));manifest=JsonParser.parseString(Files.readString(build.resolve("manifest.json"))).getAsJsonObject();
  hardwareMatrix();transitions();persistence();actions();reviewStartup();gate(false);gate(true);
  JsonObject r=new JsonObject();r.addProperty("passed",true);r.addProperty("firmware_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw)));
  r.addProperty("engine","Actual native MMIO backlight implementation, patched mode setter, native brightness setters/return, Share dispatch, SD load/validate/save, stock film-map apply and capture gate. File/UI/preview boundaries and known restore alias modelled; hardware timing not tested.");
  r.add("scenarios",results);Files.writeString(build.resolve("review-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(r)+"\n");
  println("REVIEW COMPLETE: "+results.size()+" scenarios");
 }
}
