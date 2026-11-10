// UI8 regressions execute stored-photo Review init and native brightness list OK.
// @category Kodak
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.*;
import ghidra.app.emulator.EmulatorHelper;

public class TestStoredReview extends TestReviewBrightness {
 static final long BRIGHT=0x166ae4,BLIST=0x166aa8,REVIEW=0x1608b8,SHARE=0x168370,SETUP=0x166708;
 long payload=0x12345678;
 @Override void hardware(EmulatorHelper e,int request,int model,int option,int mode){
  int effective=option!=0&&(mode==2||mode==4)?1:request;
  boolean bit=(model==2||model==3)?effective==2:effective==1;
  require((word(e,MMIO)&0xffff)==((0xa5a1&~4)|(bit?4:0)),"UI8 physical brightness mode="+mode+" model="+model+" option="+option+" request="+request);
  require(byteAt(e,NORMAL)==2,"normal brightness preserved");
 }
 @Override void registers(EmulatorHelper e,long pc,long r0,long r1,long r2){super.registers(e,pc,r0,r1,payload);}
 class NativeFS extends ReviewFS {
  int photoRenders=0;boolean modeSetter=false,listOK=false;
  NativeFS(byte[] a,byte[] b){super(a,b);}
  @Override boolean service(EmulatorHelper e,long pc){
   if(pc==0x3c4e0)modeSetter=true; // Observe; execute actual hooked code.
   if(pc==0x90094)listOK=true;
   if(pc==0x7c460&&reg(e,"r0")==BRIGHT){require(reg(e,"r1")==0x4801,"native brightness list ID");returned(e,BLIST);return true;}
   if(pc==0x8f26c&&reg(e,"r0")==BLIST){long n=reg(e,"r1");require(n<2,"native brightness index");e.writeMemoryValue(toAddr(BLIST+0x31),1,n);returned(e,0);return true;}
   if(pc==0x8f2c0&&reg(e,"r0")==BLIST){require((reg(e,"r1")==0x166a58||reg(e,"r1")==0x166a70)&&reg(e,"r2")==1,"native brightness tick");returned(e,0);return true;}
   // SDK, storage enumeration and photo rendering are boundaries. Review's own
   // initializer, mode setter, backlight body and UI dispatch execute unmodified.
   if(pc==0xc5090||pc==0x557f4||pc==0x3be8c||pc==0x72174||pc==0x456f0||pc==0x79170){returned(e,0);return true;}
   if(pc==0x79a2c){e.writeMemoryValue(toAddr(reg(e,"r0")),4,1);returned(e,0);return true;}
   if(pc==0xdd2fc){photoRenders++;returned(e,0);return true;}
   return super.service(e,pc);
  }
 }
 void nativeGlobals(EmulatorHelper e,long root){
  e.writeMemoryValue(toAddr(0x134db8),4,root);
  e.writeMemoryValue(toAddr(0x134da8),4,0x14ce38);e.writeMemoryValue(toAddr(0x134dac),4,6);
  e.writeMemoryValue(toAddr(0x134db0),4,0x14ce50);e.writeMemoryValue(toAddr(0x134db4),4,0xb6);
  e.writeMemoryValue(toAddr(BLIST+8),4,BRIGHT);
 }
 void storedReview(boolean old,boolean first,int option,int model)throws Exception{
  byte[] candidate=fw;if(old)fw=Files.readAllBytes(Path.of(getScriptArgs()[1]));
  EmulatorHelper e=fresh();fw=candidate;try{
   NativeFS fs=new NativeFS(null,config(6,1,option,25));nativeGlobals(e,REVIEW);
   e.writeMemoryValue(toAddr(NORMAL),1,2);e.writeMemoryValue(toAddr(LCD),2,model);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
   call(e,null,0x40240,2,0); // Existing physical Power save, with this LCD polarity.
   e.writeMemoryValue(toAddr(SDSTATE),4,first?0:1);e.writeMemoryValue(toAddr(OPTION),1,first?0:option);
   payload=0x150890;int steps=call(e,fs,0x41544,REVIEW,0x4405);payload=0x12345678;
   require(fs.modeSetter&&fs.photoRenders==1&&byteAt(e,MODE)==2,"actual stored-photo initializer reached native mode2 and photo render");
   hardware(e,2,model,old?0:option,2);
   require(fs.opens==(first?2:0)&&fs.writes==0,"Review-first SD load once, no write");
   if(first){choice(e,6,1);require(byteAt(e,OPTION)==option,"Review-first saved override restored");}
   passed((old?"UI7 negative control reproduces dim stored-photo Review":"native stored-photo Review init")+" first="+first+" option="+option+" lcd="+model,steps);
  }finally{payload=0x12345678;e.dispose();}
 }
 void brightness(boolean old,boolean shortcut,int selected,boolean cancel)throws Exception{
  byte[] candidate=fw;if(old)fw=Files.readAllBytes(Path.of(getScriptArgs()[1]));
  EmulatorHelper e=fresh();fw=candidate;try{
   NativeFS fs=new NativeFS(null,null);nativeGlobals(e,BRIGHT);
   e.writeMemoryValue(toAddr(SDSTATE),4,1);e.writeMemoryValue(toAddr(NORMAL),1,2);e.writeMemoryValue(toAddr(LCD),2,1);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
   int steps=0;
   if(shortcut){steps+=call(e,fs,ui("open_brightness"),SHARE,0x5002);require(fs.screens.get(0)==0x9e,"shortcut opens brightness");}
   else e.writeMemoryValue(toAddr(0x132919),1,0x9c);
   payload=shortcut?SHARE:SETUP;
   steps+=call(e,fs,0x41544,BRIGHT,0x4405);payload=0x12345678;
   require(byteAt(e,BLIST+0x31)==1,"native initializer selects normal Power save");
   e.writeMemoryValue(toAddr(BLIST+0x31),1,selected);
   steps+=call(e,fs,cancel?0x41544:0x90094,cancel?BRIGHT:BLIST,cancel?0x700:0);
   long expected=shortcut&&(!old||cancel)?0xa8:0x9c;
   require(fs.screens.get(fs.screens.size()-1)==expected,"native OK/Cancel return target expected="+Long.toHexString(expected));
   if(!cancel){require(fs.listOK&&byteAt(e,NORMAL)==selected+1,"native list OK applies selected brightness");require((word(e,MMIO)&4)==(selected==0?4:0),"native selected physical backlight");}
   if(shortcut&&!old){steps+=call(e,fs,ui("init"),ROOT,0x4405);require(fs.selected==2&&byteAt(e,OPTION+1)==0,"return selects brightness row and consumes marker");}
   passed((old?"UI7 negative control reproduces OK returning to Setup":"native brightness routing")+" shortcut="+shortcut+" selected="+selected+" cancel="+cancel,steps);
  }finally{payload=0x12345678;e.dispose();}
 }
 void staleContext()throws Exception{
  for(int mode:new int[]{1,2,3,4}){
   EmulatorHelper e=fresh();try{
    NativeFS fs=new NativeFS(null,null);nativeGlobals(e,BRIGHT);e.writeMemoryValue(toAddr(SDSTATE),4,1);e.writeMemoryValue(toAddr(NORMAL),1,2);
    int steps=call(e,fs,ui("open_brightness"),SHARE,0x5002);
    payload=SHARE;steps+=call(e,fs,0x41544,BRIGHT,0x4405);payload=0x12345678;
    require(word(e,0x166a68)==0xa8&&word(e,0x166a80)==0xa8,"shortcut first changes both OK targets");
    steps+=call(e,fs,0x3c4e0,mode,0);require(byteAt(e,OPTION+1)==0,"mode entry abandons shortcut context");
    payload=SETUP;steps+=call(e,fs,0x41544,BRIGHT,0x4405);payload=0x12345678;
    require(word(e,0x166a68)==0x9c&&word(e,0x166a80)==0x9c,"native Setup resets both item targets");
    passed("shortcut abandoned via mode="+mode+" resets Setup OK targets",steps);
   }finally{payload=0x12345678;e.dispose();}
  }
 }
 void ordinaryCycle(int model)throws Exception{
  EmulatorHelper e=fresh();try{
   NativeFS fs=new NativeFS(config(0,0,1,10),null);nativeGlobals(e,REVIEW);
   e.writeMemoryValue(toAddr(SDSTATE),4,1);e.writeMemoryValue(toAddr(SDSTATE+4),4,10);e.writeMemoryValue(toAddr(SDSTATE+8),4,0);
   e.writeMemoryValue(toAddr(OPTION),1,1);e.writeMemoryValue(toAddr(NORMAL),1,2);e.writeMemoryValue(toAddr(LCD),2,model);e.writeMemoryValue(toAddr(MMIO),4,0xa5a1);
   payload=0x150890;int steps=call(e,fs,0x41544,REVIEW,0x4405);payload=0x12345678;hardware(e,2,model,1,2);
   steps+=call(e,fs,ui("start"),ROOT,0x5003);hardware(e,2,model,0,2);
   require(byteAt(e,OPTION)==0&&Arrays.equals(fs.slots[1],config(0,0,0,11)),"ordinary Review disable immediately restores and saves");
   steps+=call(e,fs,ui("start"),ROOT,0x5003);hardware(e,2,model,1,2);
   require(Arrays.equals(fs.slots[0],config(0,0,1,12)),"ordinary Review re-enable persists");
   steps+=call(e,fs,0x3c4e0,1,0);hardware(e,2,model,1,1);
   payload=0x150890;steps+=call(e,fs,0x41544,REVIEW,0x4405);payload=0x12345678;hardware(e,2,model,1,2);
   passed("ordinary Review boost, toggle off/on, capture restore and reentry lcd="+model,steps);
  }finally{payload=0x12345678;e.dispose();}
 }
 public void run()throws Exception{
  super.run();
  for(int model:new int[]{1,2,3}){
   if(getScriptArgs().length>1)storedReview(true,false,1,model);ordinaryCycle(model);
   for(boolean first:new boolean[]{false,true})for(int option:new int[]{0,1})storedReview(false,first,option,model);
  }
  for(int selected:new int[]{0,1}){
   if(getScriptArgs().length>1)brightness(true,true,selected,false);
   for(boolean shortcut:new boolean[]{false,true})for(boolean cancel:new boolean[]{false,true})brightness(false,shortcut,selected,cancel);
  }
  staleContext();
  Path build=Path.of(getScriptArgs()[0]);JsonObject r=new JsonObject();r.addProperty("passed",true);
  r.addProperty("firmware_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw)));
  r.addProperty("engine","Native DD320 stored-photo Review initializer, native 90094 brightness OK list dispatch, EAB28 brightness initialization, EAB78 Cancel, patched mode/backlight entries, original MMIO polarity and SD records execute. Optional UI7 negative controls require a separately supplied historical image. SDK/photo/file/UI transition boundaries and compiler restore alias modeled; physical timing/output require camera trial.");
  r.add("scenarios",results);Files.writeString(build.resolve("review-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(r)+"\n");
  println("STORED REVIEW COMPLETE: "+results.size()+" scenarios");
 }
}
