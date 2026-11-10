// Native Film chooser activation/navigation/OK/Cancel, plus accepted UI8 regressions.
// @category Kodak
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.*;
import ghidra.app.emulator.EmulatorHelper;

public class TestFilmChooser extends TestStoredReview {
 static final long CR=0x1e6200,CL=0x1e6240,CI=0x1e62c0,POOL=0x1e6000;
 int chooserMode=1;
 long chooser(String name){return Long.decode(manifest.getAsJsonObject("chooser_symbols").get(name).getAsString());}
 @Override EmulatorHelper fresh(){EmulatorHelper e=super.fresh();e.writeMemory(toAddr(0x1a0000),Arrays.copyOfRange(fw,0x144c00,0x194800));return e;}
 @Override int call(EmulatorHelper e,ReviewFS fs,long entry,long r0,long r1)throws Exception{
  byte[] header=e.readMemory(toAddr(0x1241a0),1536);int jpeg=byteAt(e,0x133185);
  registers(e,entry,r0,r1,0x12345678);int steps=0;
  while(steps++<30000){long pc=e.getExecutionAddress().getOffset();if(pc==RET)break;
   require(pc!=0xfe450&&pc!=0xd6f0c,"no firmware flashing");
   if(pc>=0x11ae14&&pc<=0x11ae5c&&(0x11ae5c-pc)%8==0){restore(e,pc);continue;}
   if(fs!=null&&fs.service(e,pc))continue;
   require(e.step(monitor),"entry="+Long.toHexString(entry)+" pc="+Long.toHexString(pc)+" "+e.getLastError());
  }

  require(steps<30000&&reg(e,"sp")==SP&&reg(e,"blink")==RET,"return/stack entry="+Long.toHexString(entry)+" pc="+e.getExecutionAddress()+" sp="+Long.toHexString(reg(e,"sp"))+" blink="+Long.toHexString(reg(e,"blink")));
  for(int i=13;i<=25;i++)require(reg(e,"r"+i)==0xabc00000L+i,"saved r"+i);
  require(Arrays.equals(header,e.readMemory(toAddr(0x1241a0),1536))&&byteAt(e,0x133185)==jpeg,"capture header/JPEG unchanged");
  if(fs!=null)require(fs.handles.isEmpty(),"no file handle leak");return steps;
 }
 class ChooserFS extends NativeFS {
  int activations=0,previewUpdates=0;List<Long> boundaries=new ArrayList<>();
  ChooserFS(byte[] a,byte[] b){super(a,b);}
  @Override boolean service(EmulatorHelper e,long pc){
   if(pc==0x62a9c){require(reg(e,"r0")<3,"preview level");previewUpdates++;returned(e,1);return true;}
   if(pc==0x7bffc){activations++;return false;}
   if(pc==0x7c260&&reg(e,"r0")==0xa8){screens.add(0xa8L);return false;}
   if(pc==0x7bfcc&&(reg(e,"r0")==CR||reg(e,"r0")==SHARE)){repaints++;returned(e,0);return true;}
   if(pc==0x7c460&&(reg(e,"r0")==CR||reg(e,"r0")==SHARE))return false;
   if(pc==0x8f26c&&(reg(e,"r0")==CL||reg(e,"r0")==LIST))return false;
   if(pc==0x8f2c0&&reg(e,"r0")==CL)return false;
   if(pc==0x471a0||pc==0x47138||pc==0x78734||pc==0x7871c||pc==0x7874c||pc==0x30480||pc==0x304b4||pc==0x30554||pc==0x55488||pc==0x6aa44||pc==0x6aa60){boundaries.add(pc);returned(e,0);return true;}
   return super.service(e,pc);
  }
 }
 void chooserGlobals(EmulatorHelper e,int film){
  nativeGlobals(e,SHARE);e.writeMemoryValue(toAddr(SDSTATE),4,1);e.writeMemoryValue(toAddr(SDSTATE+4),4,10);e.writeMemoryValue(toAddr(SDSTATE+8),4,0);
  e.writeMemoryValue(toAddr(0x1682d0),1,film);e.writeMemory(toAddr(TAB),map(film));
  e.writeMemoryValue(toAddr(MODE),1,chooserMode);e.writeMemoryValue(toAddr(NORMAL),1,2);e.writeMemoryValue(toAddr(0x1683a8),1,1);
  e.writeMemoryValue(toAddr(LIST+8),4,SHARE);e.writeMemoryValue(toAddr(0x168190+8),4,SHARE);e.writeMemoryValue(toAddr(0x168404+8),4,SHARE);
 }
 void flow(int initial,int target,boolean cancel)throws Exception{
  EmulatorHelper e=fresh();try{
   ChooserFS fs=new ChooserFS(config(initial,0,1,10),null);chooserGlobals(e,initial);
   byte[] mapBefore=e.readMemory(toAddr(TAB),24);byte[] slot=fs.slots[0].clone();
   e.writeMemoryValue(toAddr(LCD),2,1);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
   int steps=call(e,fs,0x40240,2,0);steps+=call(e,fs,0x41544,SHARE,0x5000);
   require(fs.activations==1&&word(e,0x134db8)==CR,"native 7bffc activates chooser root");
   require(byteAt(e,CL+0x31)==initial,"current film initially highlighted");
   for(int i=0;i<7;i++)require(word(e,CI+24*i)==(i==initial?0x005a005a:0),"only current film ticked");
   steps+=call(e,fs,0x8f26c,CL,target); // Native focus/scroll; no preference mutation.
   require(byteAt(e,0x1682d0)==initial&&Arrays.equals(mapBefore,e.readMemory(toAddr(TAB),24))&&fs.writes==0,"browsing changes neither film, map nor SD");
   require(byteAt(e,CL+0x31)==target,"browse target highlighted");
   steps+=call(e,fs,cancel?0x41544:0x90094,cancel?CR:CL,cancel?0x780:0);
   int expected=cancel?initial:target;choice(e,expected,0);
   require(word(e,0x134db8)==SHARE&&byteAt(e,LIST+0x31)==0,"native return to Film row");
   require(byteAt(e,OPTION)==1&&byteAt(e,NORMAL)==2,"brightness preferences retained");
   require(byteAt(e,MODE)==chooserMode,"chooser preserves camera/Review mode");hardware(e,2,1,1,chooserMode);
   require(fs.previewUpdates==(!cancel&&initial!=target&&chooserMode==1?1:0),"preview updates only on changed OK");
   require(fs.writes==(!cancel&&initial!=target?1:0),"commit once only for changed OK choice");
   require(Arrays.equals(fs.slots[0],slot),"old active SD slot preserved");
   if(!cancel&&initial!=target)require(Arrays.equals(fs.slots[1],config(target,0,1,11)),"selected film and Review saved together");
   passed("native chooser mode="+chooserMode+" initial="+initial+" target="+target+" cancel="+cancel,steps);
  }finally{e.dispose();}
 }
 void relocatedGetters(int film)throws Exception{
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
       new long[]{0x1257a0,0x125860,0x125920,0x1e6000,0x1e60c0}[selected-1]+48*(ccm?input:3);
     require(steps<100&&reg(e,"r0")==expected,"getter film="+film+" mode="+mode+" arg="+input+" got="+Long.toHexString(reg(e,"r0"))+" expected="+Long.toHexString(expected));
     require(reg(e,"sp")==SP&&reg(e,"r2")==0x87654321L&&reg(e,"blink")==RET,"getter ABI");checks++;
    }
   }
   require(Arrays.equals(h,e.readMemory(toAddr(0x1241a0),1536))&&d==e.readMemoryByte(toAddr(FLAG)),"getter changed DNG");
   passed("film "+film+": "+checks+" actual CCM/Ymat getter cases",checks);
  }finally{e.dispose();}
 }
 void keys()throws Exception{
  EmulatorHelper e=fresh();try{
   ChooserFS fs=new ChooserFS(config(0,0,1,10),null);chooserGlobals(e,0);
   e.writeMemoryValue(toAddr(LCD),2,1);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
   int steps=call(e,fs,0x40240,2,0);steps+=call(e,fs,0x41544,SHARE,0x5000);
   for(int i=1;i<7;i++){
    steps+=call(e,fs,0x41544,CR,0x400);
    require(byteAt(e,CL+0x31)==i,"Down key moves to film "+i);
    require(byteAt(e,0x1682d0)==0&&fs.writes==0,"Down key never commits");
   }
   for(int i=5;i>=0;i--){steps+=call(e,fs,0x41544,CR,0x380);require(byteAt(e,CL+0x31)==i,"Up key moves to film "+i);}
   steps+=call(e,fs,0x41544,CR,0x700);require(word(e,0x134db8)==SHARE&&fs.writes==0,"Back key cancels");
   passed("physical Up/Down event dispatch scrolls all seven films; Back cancels",steps);
  }finally{e.dispose();}
 }
 @Override void actions()throws Exception{
  EmulatorHelper e=fresh();try{
   ReviewFS fs=new ReviewFS(config(3,0,0,11),null);
   e.writeMemoryValue(toAddr(NORMAL),1,2);e.writeMemoryValue(toAddr(LCD),2,1);
   int steps=call(e,fs,ui("start"),ROOT,0x4405);choice(e,3,0);
   steps+=call(e,fs,ui("start"),ROOT,0x5003);require(byteAt(e,OPTION)==1&&Arrays.equals(fs.slots[1],config(3,0,1,12)),"toggle saves Review flag");
   steps+=call(e,fs,ui("start"),ROOT,0x5001);choice(e,3,1);require(Arrays.equals(fs.slots[0],config(3,1,1,13)),"format save retains Review flag");
   steps+=call(e,fs,chooser("choose"),ROOT,0x5004);choice(e,4,1);require(Arrays.equals(fs.slots[1],config(4,1,1,14)),"film save retains Review flag");
   e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);steps+=call(e,fs,0x3c4e0,4,0);hardware(e,2,1,1,4);
   e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);steps+=call(e,fs,ui("start"),ROOT,0x5003);hardware(e,2,1,0,4);
   require(Arrays.equals(fs.slots[0],config(4,1,0,15))&&status(e).equals("v0.9: SD saved"),"disable immediately restores and saves");
   int writes=fs.writes;steps+=call(e,fs,ui("start"),ROOT,0x5002);
   require(fs.screens.get(fs.screens.size()-1)==0x9e&&byteAt(e,0x132919)==0xa8,"shortcut opens native brightness with ModernShare return");
   // Native Cancel/finish handler consults the saved return screen.
   steps+=call(e,fs,0xeab78,ROOT,0x700);require(fs.screens.get(fs.screens.size()-1)==0xa8,"native return to ModernShare");
   steps+=call(e,fs,ui("start"),ROOT,0x4405);require(fs.selected==2&&byteAt(e,OPTION+1)==0,"brightness row retained on return");
   steps+=call(e,fs,ui("start"),ROOT,0x5004);require(fs.screens.get(fs.screens.size()-1)==0x3b&&fs.writes==writes,"Hidden menu retained without save");
   passed("Review toggle/chooser commit/format/shortcut/return/Hidden integration",steps);
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
 public void run()throws Exception{
  Path build=Path.of(getScriptArgs()[0]);fw=Files.readAllBytes(build.resolve("KC713.FW"));manifest=JsonParser.parseString(Files.readString(build.resolve("manifest.json"))).getAsJsonObject();
  keys();flow(0,6,false);
  super.run();state=0x1682d0;
  payload=0x87654321L;for(int film=0;film<7;film++)relocatedGetters(film);payload=0x12345678;
  for(int initial=0;initial<7;initial++)for(int target=0;target<7;target++){
   if(initial!=0||target!=6)flow(initial,target,false);
   flow(initial,target,true);
  }
  for(int mode:new int[]{2,4}){chooserMode=mode;flow(3,6,false);flow(3,6,true);}chooserMode=1;
  JsonObject r=new JsonObject();r.addProperty("passed",true);r.addProperty("firmware_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw)));
  r.addProperty("engine","Native root event dispatch, pointer-based screen activation, list focus/scroll/ticks, list OK, Share return, film apply/preview/save, and UI8 brightness/SD regressions. SDK, photo, drawing refresh/timer, file and compiler restore boundaries modeled. Camera interaction/output require trial.");r.add("scenarios",results);
  Files.writeString(build.resolve("chooser-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(r)+"\n");
  println("FILM CHOOSER COMPLETE: "+results.size()+" scenarios");
 }
}
