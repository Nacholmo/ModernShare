// Execute actual preferences instructions; model only stock OS/UI/file boundaries.
// @category Kodak
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.*;
import ghidra.app.emulator.EmulatorHelper;

public class TestSettings extends TestModernShare {
 static final long SDSTATE=0x16839c;
 long symbol(String name){return Long.decode(manifest.getAsJsonObject("settings_symbols").get(name).getAsString());}
 byte[] record(int film,int dng,long generation){
  int magic=0x444f4d4b,config=0x10000|(film<<8)|dng,g=(int)generation;
  return ByteBuffer.allocate(16).order(ByteOrder.LITTLE_ENDIAN).putInt(magic).putInt(config).putInt(g).putInt(~(magic^config^g)).array();
 }
 long generation(byte[] b){return Integer.toUnsignedLong(ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).getInt(8));}
 class Filesystem {
  byte[][] slots=new byte[2][];
  Map<Long,Integer> handles=new HashMap<>();Map<Long,Boolean> writable=new HashMap<>();
  List<String> operations=new ArrayList<>();
  int next=100,opens=0,reads=0,writes=0,closes=0;
  int failSlot=-1;String fault="";long initStatus=0;int inits=0,repaints=0,selects=0;
  Filesystem(byte[] a,byte[] b){slots[0]=a;slots[1]=b;}
  boolean fail(int slot,String action){return failSlot==slot&&fault.equals(action);}
  boolean service(EmulatorHelper e,long pc){
   if(pc==0xcabfc){require(reg(e,"r0")==ROOT&&reg(e,"r1")==0x4405&&reg(e,"r2")==0x12345678,"original capture init arguments");inits++;e.writeMemoryValue(toAddr(0x132904),1,1);returned(e,initStatus);return true;}
   if(pc==0x62a9c){returned(e,1);return true;}
   if(pc==0x7bfcc){require(reg(e,"r0")==ROOT,"settings repaint root");repaints++;returned(e,0);return true;}
   if(pc==0x7c460){require(reg(e,"r0")==ROOT&&reg(e,"r1")==0x4804,"native list");returned(e,LIST);return true;}
   if(pc==0x8f26c){require(reg(e,"r0")==LIST&&reg(e,"r1")==0,"film first selection");selects++;returned(e,0);return true;}
   if(pc==0x73224){
    String path=e.readNullTerminatedString(toAddr(reg(e,"r0")),64);
    int slot=path.equals("B:\\KMOD0.CFG")?0:path.equals("B:\\KMOD1.CFG")?1:-1;
    require(slot>=0,"absolute SD-only settings path: "+path);
    boolean write=reg(e,"r1")==1;
    require((write&&reg(e,"r2")==1)||(!write&&reg(e,"r1")==0&&reg(e,"r2")==0),"open ABI");
    opens++;operations.add((write?"create":"open")+slot);
    if(fail(slot,write?"create":"open")||(!write&&slots[slot]==null)){returned(e,5);return true;}
    long h=next++;handles.put(h,slot);writable.put(h,write);
    if(write)slots[slot]=new byte[0];
    e.writeMemoryValue(toAddr(reg(e,"r3")),4,h);returned(e,0);return true;
   }
   if(pc==0x73234||pc==0x73240){
    long h=reg(e,"r0");require(handles.containsKey(h),"valid file handle");int slot=handles.get(h);boolean write=pc==0x73240;
    require(writable.get(h)==write&&reg(e,"r2")==16&&reg(e,"r3")== (write?0:1),"read/write ABI");
    long ptr=reg(e,"r1"),count=reg(e,"r4");String action=write?"write":"read";
    int n=write?16:Math.min(16,slots[slot].length);if(fail(slot,action+"-short"))n=7;
    if(write){writes++;slots[slot]=e.readMemory(toAddr(ptr),n);}else{reads++;e.writeMemory(toAddr(ptr),Arrays.copyOf(slots[slot],n));}
    operations.add(action+slot);e.writeMemoryValue(toAddr(count),4,n);returned(e,fail(slot,action)?9:0);return true;
   }
   if(pc==0x7324c){
    long p=reg(e,"r0"),h=word(e,p);require(handles.containsKey(h),"close exactly once");int slot=handles.remove(h);boolean write=writable.remove(h);
    closes++;operations.add("close"+slot);e.writeMemoryValue(toAddr(p),4,0);returned(e,fail(slot,write?"write-close":"read-close")?13:0);return true;
   }
   return false;
  }
 }
 int invoke(EmulatorHelper e,Filesystem fs,String name,long entry,long event,long expected)throws Exception{
  byte[] header=e.readMemory(toAddr(0x1241a0),1536);int jpeg=e.readMemoryByte(toAddr(0x133185));
  registers(e,entry,ROOT,event,0x12345678);int steps=0;
  while(steps++<2400){long pc=e.getExecutionAddress().getOffset();if(pc==RET)break;
   if(pc>=0x11ae14&&pc<=0x11ae5c&&(0x11ae5c-pc)%8==0){restore(e,pc);continue;}
   if(fs.service(e,pc))continue;
   require(e.step(monitor),name+" pc="+Long.toHexString(pc)+" "+e.getLastError());
  }
  require(steps<2400&&reg(e,"sp")==SP&&reg(e,"blink")==RET&&reg(e,"r0")==expected,"settings return/stack "+name+" steps="+steps+" pc="+e.getExecutionAddress()+" sp="+Long.toHexString(reg(e,"sp"))+" r0="+Long.toHexString(reg(e,"r0")));
  for(int i=13;i<=25;i++)require(reg(e,"r"+i)==0xabc00000L+i,"settings saved register "+i+" "+name);
  require(fs.handles.isEmpty(),"no leaked handles "+name);
  require(Arrays.equals(header,e.readMemory(toAddr(0x1241a0),1536))&&jpeg==e.readMemoryByte(toAddr(0x133185)),"DNG header/JPEG untouched");
  return steps;
 }
 String status(EmulatorHelper e){return e.readNullTerminatedString(toAddr(word(e,ITEMS+76)),64);}
 void choice(EmulatorHelper e,int film,int dng){
  require((e.readMemoryByte(toAddr(0x1682d0))&255)==film&&(e.readMemoryByte(toAddr(FLAG))&255)==dng,"restored preferences");
  require(Arrays.equals(e.readMemory(toAddr(TAB),24),map(film)),"film map applies before capture");
 }
 void load(String name,Filesystem fs,int film,int dng,long gen,int slot,boolean valid,boolean review)throws Exception{
  EmulatorHelper e=fresh();try{
   int steps=invoke(e,fs,name,symbol(review?"menu_init":"capture_init"),0x4405,0);
   choice(e,film,dng);require(word(e,SDSTATE)==1&&word(e,SDSTATE+4)==gen&&word(e,SDSTATE+8)==slot,"loaded generation/slot");
   require(status(e).equals(valid?"v0.8: SD loaded":"v0.8: defaults"),"loaded status");
   require(fs.writes==0&&fs.opens==2&&fs.inits==(review?0:1)&&fs.selects==(review?1:0),"read-only once load");
   // Opening the menu or returning to capture must not overwrite session state.
   int opens=fs.opens;fs.slots[0]=record(1,1,gen+100);
   steps+=invoke(e,fs,name+" again",symbol(review?"capture_init":"menu_init"),0x4405,0);
   require(fs.opens==opens&&fs.writes==0,"no reload/no write on later init");choice(e,film,dng);
   passed(name,steps);
  }finally{e.dispose();}
 }
 void saveCases()throws Exception{
  EmulatorHelper e=fresh();try{
   Filesystem fs=new Filesystem(null,null);invoke(e,fs,"save setup",symbol("capture_init"),0x4405,0);
   long dispatch=0x1256c0;int steps=invoke(e,fs,"film autosave",dispatch,0x5000,0);choice(e,1,0);
   require(Arrays.equals(fs.slots[0],record(1,0,1))&&fs.slots[1]==null&&word(e,SDSTATE+8)==0,"first save to A");
   require(status(e).equals("v0.8: SD saved"),"saved feedback");
   steps+=invoke(e,fs,"DNG autosave",dispatch,0x5001,0);choice(e,1,1);
   require(Arrays.equals(fs.slots[1],record(1,1,2))&&Arrays.equals(fs.slots[0],record(1,0,1)),"second save B preserves A");
   require(word(e,SDSTATE+4)==2&&word(e,SDSTATE+8)==1&&fs.writes==2,"two commits");
   int writes=fs.writes;steps+=invoke(e,fs,"refresh no save",dispatch,0x4409,0);require(writes==fs.writes,"refresh writes nothing");
   Filesystem reboot=new Filesystem(fs.slots[0],fs.slots[1]);load("reboot restores menu choices",reboot,1,1,2,1,true,false);
   passed("menu actions automatically alternate and save",steps);
  }finally{e.dispose();}
  for(String fault:new String[]{"create","write","write-short","write-close"}){
   EmulatorHelper x=fresh();try{
    Filesystem fs=new Filesystem(record(5,0,20),record(4,1,19));invoke(x,fs,"failure setup",symbol("capture_init"),0x4405,0);
    byte[] previous=fs.slots[0].clone();fs.failSlot=1;fs.fault=fault;
    int steps=invoke(x,fs,"save "+fault,0x1256c0,0x5001,0);choice(x,5,1);
    require(word(x,SDSTATE+4)==20&&word(x,SDSTATE+8)==0&&Arrays.equals(fs.slots[0],previous),"failed write keeps committed generation/slot and active file");
    require(status(x).equals("v0.8: SD error"),"failure status");
    if(fault.equals("write-short"))load("power loss keeps previous valid slot",new Filesystem(fs.slots[0],fs.slots[1]),5,0,20,0,true,false);
    fs.fault="";steps+=invoke(x,fs,"retry "+fault,0x1256c0,0x5000,0);choice(x,6,1);
    require(Arrays.equals(fs.slots[1],record(6,1,21))&&word(x,SDSTATE+8)==1&&status(x).equals("v0.8: SD saved"),"retry same inactive slot");
    passed("save failure and retry: "+fault,steps);
   }finally{x.dispose();}
  }
  EmulatorHelper x=fresh();try{
   // The slot must follow the loaded file, not sequence parity.
   Filesystem fs=new Filesystem(record(3,1,8),null);invoke(x,fs,"nonparity setup",symbol("capture_init"),0x4405,0);
   int steps=invoke(x,fs,"nonparity save",0x1256c0,0x5001,0);
   require(Arrays.equals(fs.slots[0],record(3,1,8))&&Arrays.equals(fs.slots[1],record(3,0,9)),"inactive slot independent of parity");
   passed("save follows actual loaded slot",steps);
  }finally{x.dispose();}
 }
 public void run()throws Exception{
  Path build=Path.of(getScriptArgs()[0]);fw=Files.readAllBytes(build.resolve("KC713.FW"));manifest=JsonParser.parseString(Files.readString(build.resolve("manifest.json"))).getAsJsonObject();
  String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw));require(hash.equals(manifest.get("firmware_sha256").getAsString()),"bound firmware hash");
  require(eWord(0x1508bc)==symbol("capture_init")&&eWord(0x1682d8)==symbol("menu_init")&&eWord(0x1682e8)==symbol("changed")&&eWord(0x1682f0)==symbol("changed"),"native event table integration");
  load("missing settings defaults",new Filesystem(null,null),0,0,0,1,false,false);
  for(int film=0;film<7;film++)for(int dng=0;dng<2;dng++)load("restore film="+film+" dng="+dng,new Filesystem(record(film,dng,7),null),film,dng,7,0,true,false);
  load("B newer",new Filesystem(record(1,0,8),record(6,1,9)),6,1,9,1,true,false);
  load("A newer",new Filesystem(record(2,1,10),record(4,0,9)),2,1,10,0,true,false);
  load("B only",new Filesystem(null,record(4,0,2)),4,0,2,1,true,false);
  load("ties prefer A",new Filesystem(record(2,0,7),record(4,1,7)),2,0,7,0,true,false);
  load("sequence wrap",new Filesystem(record(1,0,0xffffffffL),record(5,1,0)),5,1,0,1,true,false);
  load("sequence wrap reverse",new Filesystem(record(6,1,0),record(1,0,0xffffffffL)),6,1,0,0,true,false);
  load("Review first restores",new Filesystem(null,record(6,0,11)),6,0,11,1,true,true);
  for(String invalid:new String[]{"magic","checksum","short","film7","film255","reserved","schema","dng2"}){
   byte[] bad=record(3,1,12);
   if(invalid.equals("magic"))bad[0]^=1;
   if(invalid.equals("checksum"))bad[12]^=1;
   if(invalid.equals("short"))bad=Arrays.copyOf(bad,7);
   if(invalid.equals("film7"))bad=record(7,1,12);
   if(invalid.equals("film255"))bad=record(255,1,12);
   if(invalid.equals("dng2"))bad=record(3,2,12);
   if(invalid.equals("reserved")||invalid.equals("schema")){
    ByteBuffer b=ByteBuffer.wrap(bad).order(ByteOrder.LITTLE_ENDIAN);int config=b.getInt(4)^(invalid.equals("schema")?0x30000:0x1000000);b.putInt(4,config);b.putInt(12,~(b.getInt(0)^config^b.getInt(8)));
   }
   load("invalid newer "+invalid,new Filesystem(record(1,0,9),bad),1,0,9,0,true,false);
   load("invalid only "+invalid,new Filesystem(null,bad),0,0,0,1,false,false);
  }
  for(String fault:new String[]{"open","read","read-short","read-close"}){
   Filesystem fs=new Filesystem(record(1,0,8),record(6,1,9));fs.failSlot=1;fs.fault=fault;
   load("read failure "+fault,fs,1,0,8,0,true,false);
  }
  EmulatorHelper e=fresh();try{
   Filesystem fs=new Filesystem(record(6,1,9),null);fs.initStatus=17;
   int steps=invoke(e,fs,"failed stock init",symbol("capture_init"),0x4405,17);
   require(word(e,SDSTATE)==0&&fs.opens==0&&fs.inits==1,"stock init failure returns before loading");choice(e,0,0);passed("stock init failure preserved",steps);
   fs.initStatus=0;steps=invoke(e,fs,"stock init retry",symbol("capture_init"),0x4405,0);choice(e,6,1);passed("stock init retry loads",steps);
  }finally{e.dispose();}
  saveCases();gate(false);gate(true);
  JsonObject report=new JsonObject();report.addProperty("passed",true);report.addProperty("firmware_sha256",hash);
  report.addProperty("engine","Actual ARC startup/menu/persistence instructions, stock film map fill, native menu dispatch and capture gate; file/OS boundaries modeled with caller-saved register destruction; compiler restore alias modeled");report.add("scenarios",results);
  Files.writeString(build.resolve("settings-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");println("SD SETTINGS COMPLETE: "+results.size()+" scenarios");
 }
}
