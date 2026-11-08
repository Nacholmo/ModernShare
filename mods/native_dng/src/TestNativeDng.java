// Execute the actual patched instructions with mocked file APIs, never save the stock project.
// @category Kodak
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.nio.*;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.io.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;

public class TestNativeDng extends GhidraScript {
    static final long ENTRY=0x67898, LOG=0x125cc0, SP=0x19f000, RET=0x30010, BUF=0x300000;
    static final int PIXELS=7096320;
    Path build, root;
    byte[] fw, raw;
    boolean captureMetadata;
    JsonObject fixture, layout;
    static final long META=0x2e3000, HEADER=0x1241a0;
    static final DateTimeFormatter DATE=DateTimeFormatter.ofPattern("uuuu:MM:dd HH:mm:ss");
    JsonArray results=new JsonArray();
    void require(boolean ok,String message) { if(!ok) throw new IllegalStateException(message); }
    long reg(EmulatorHelper e,String r) { return e.readRegister(r).longValue() & 0xffffffffL; }
    long word(EmulatorHelper e,long at) {
        byte[] b=e.readMemory(toAddr(at),4);
        return ((long)b[0]&255)|(((long)b[1]&255)<<8)|(((long)b[2]&255)<<16)|(((long)b[3]&255)<<24);
    }
    void returned(EmulatorHelper e,long value) {
        long address=reg(e,"blink");
        // Deliberately destroy all caller-saved general registers after every mocked call.
        for(int i=0;i<=12;i++) e.writeRegister("r"+i,0xdead0000L+i);
        e.writeRegister("r0",value);
        e.writeRegister(e.getPCRegister(),address);
    }
    void scenario(String name,int kind,int length,String path,int pathError,int openError,
                  int writeError,int shortAt,int closeError,long expected) throws Exception {
        EmulatorHelper e=new EmulatorHelper(currentProgram);
        StringBuilder trace=new StringBuilder();
        try {
            e.writeMemory(toAddr(0x30000),Arrays.copyOfRange(fw,0x200,0x100200));
            byte[] stack=new byte[4096];Arrays.fill(stack,(byte)0xa5);
            e.writeMemory(toAddr(SP-3072),stack);
            e.writeMemory(toAddr(LOG),new byte[40]);
            e.writeMemoryValue(toAddr(LOG+4),4,17);
            byte[] expectedHeader=Files.readAllBytes(build.resolve("header.bin"));
            byte[] capture=null;
            if(captureMetadata) {
                capture=new byte[256];ByteBuffer m=ByteBuffer.wrap(capture).order(ByteOrder.LITTLE_ENDIAN);
                LocalDateTime time=LocalDateTime.parse(fixture.get("date").getAsString(),DATE);
                int[] tm={time.getSecond(),time.getMinute(),time.getHour(),time.getDayOfMonth(),time.getMonthValue()-1,time.getYear()-1900,0,0,0};
                for(int i=0;i<tm.length;i++)m.putInt(0x64+i*4,tm[i]);
                m.putInt(4,(int)BUF);m.putInt(0x34,1234);
                m.putInt(0xb0,fixture.get("exposure_us").getAsInt());m.putShort(0xb4,fixture.get("iso").getAsShort());
                m.put(0xf2,fixture.get("aperture_flag").getAsByte());m.putShort(0xf4,fixture.get("aperture_index").getAsShort());
                e.writeMemory(toAddr(META),capture);e.writeMemoryValue(toAddr(0x1324fc),4,META);
                // Independently execute the stock aperture switch and division. This checks
                // the new lookup table against the real firmware, including out-of-range indices.
                e.writeRegister("r14",META);e.writeRegister("r13",0x180000);e.writeRegister("r15",4800);
                e.writeRegister(e.getPCRegister(),0x5457e);
                int stockSteps=0;
                while(e.getExecutionAddress().getOffset()!=0x545ec&&stockSteps++<100) {
                    if(e.getExecutionAddress().getOffset()==0x11affc) {
                        require(reg(e,"r1")==10,"stock aperture divisor");
                        returned(e,reg(e,"r0")/10);continue;
                    }
                    require(e.step(monitor),"stock aperture switch: "+e.getLastError());
                }
                require(stockSteps<100&&word(e,0x18004c)==fixture.get("fnumber_100").getAsInt(),"stock aperture differs from fixture");
                ByteBuffer h=ByteBuffer.wrap(expectedHeader).order(ByteOrder.LITTLE_ENDIAN);
                h.putInt(layout.get("EXPOSURE").getAsInt(),Math.max(714,fixture.get("exposure_us").getAsInt()));
                h.putInt(layout.get("FNUMBER").getAsInt(),fixture.get("fnumber_100").getAsInt());
                h.putShort(layout.get("ISO").getAsInt(),fixture.get("iso").getAsShort());
                System.arraycopy((time.format(DATE)+"\0").getBytes(StandardCharsets.US_ASCII),0,expectedHeader,layout.get("DATE").getAsInt(),20);
                // Deliberately seed stale metadata. Each capture must replace it before writing.
                byte[] stale=expectedHeader.clone();Arrays.fill(stale,layout.get("DATE").getAsInt(),layout.get("DATE").getAsInt()+20,(byte)0);
                ByteBuffer.wrap(stale).order(ByteOrder.LITTLE_ENDIAN).putInt(layout.get("EXPOSURE").getAsInt(),123);
                e.writeMemory(toAddr(HEADER),stale);
            }
            // Initialize a real sensor frame: a successful mocked file write reads this memory.
            e.writeMemory(toAddr(BUF),raw);
            for(int i=0;i<=25;i++) e.writeRegister("r"+i,0xabc00000L+i);
            e.writeRegister("sp",SP);e.writeRegister("blink",RET);
            e.writeRegister("r0",kind);e.writeRegister("r1",1234);
            e.writeRegister("r2",BUF);e.writeRegister("r3",length);
            e.writeRegister(e.getPCRegister(),ENTRY);
            int writes=0,closes=0,steps=0,formatters=0;boolean stock=false;
            ByteArrayOutputStream file=new ByteArrayOutputStream();
            while(steps++<1200) {
                long pc=e.getExecutionAddress().getOffset();
                trace.append(String.format("%08x sp=%08x r0=%08x r12=%08x r13=%08x blink=%08x%n",pc,reg(e,"sp"),reg(e,"r0"),reg(e,"r12"),reg(e,"r13"),reg(e,"blink")));
                if(pc==0x6789e) {
                    stock=true;
                    require(kind!=0 || length!=PIXELS,"unexpected stock fallback");
                    require(reg(e,"sp")==SP-24,"stock prologue stack");
                    require(word(e,SP-4)==RET,"stock saved return address");
                    for(int i=13;i<=17;i++) require(reg(e,"r"+i)==0xabc00000L+i,"stock register changed");
                    require(reg(e,"r0")==kind && reg(e,"r1")==1234 && reg(e,"r2")==BUF && reg(e,"r3")==length,"stock arguments changed");
                    break;
                }
                if(pc==RET) break;
                if(captureMetadata&&pc==0x116be4) {
                    formatters++;
                    require(writes==0,"metadata formatter ran after file write");
                    require(reg(e,"r0")==HEADER+layout.get("DATE").getAsInt()&&reg(e,"r1")==20&&reg(e,"r3")==META+0x64,"capture date formatter arguments");
                    require(reg(e,"r2")==0x127a08,"stock date format pointer");
                    e.writeMemory(toAddr(reg(e,"r0")),(fixture.get("date").getAsString()+"\0").getBytes(StandardCharsets.US_ASCII));
                    returned(e,19);continue;
                }
                if(pc==0x4b724) {
                    if(captureMetadata) require(formatters==1&&Arrays.equals(e.readMemory(toAddr(HEADER),1536),expectedHeader),"current-shot metadata missing before path/open/write");
                    require(reg(e,"r0")==1234,"path ID argument");
                    e.writeMemory(toAddr(reg(e,"r1")),(path+"\0").getBytes(StandardCharsets.US_ASCII));
                    returned(e,pathError);continue;
                }
                if(pc==0x116930) {
                    String text=e.readNullTerminatedString(toAddr(reg(e,"r0")),256);
                    require(text.equals(path),"path helper or path pointer");
                    returned(e,text.length());continue;
                }
                if(pc==0x73224) {
                    String actual=e.readNullTerminatedString(toAddr(reg(e,"r0")),256);
                    require(actual.equals(path.substring(0,path.length()-12)+"CCDI"+path.substring(path.length()-8,path.length()-3)+"DNG"),"DNG filename: "+actual);
                    require(reg(e,"r1")==1 && reg(e,"r2")==1,"open flags");
                    e.writeMemoryValue(toAddr(reg(e,"r3")),4,0x123456);
                    returned(e,openError);continue;
                }
                if(pc==0x73240) {
                    writes++;
                    require(reg(e,"r0")==0x123456 && reg(e,"r3")==0,"write handle/mode");
                    long n=reg(e,"r2"),ptr=reg(e,"r1"),out=reg(e,"r4");
                    require(n==(writes==1?1536:PIXELS),"write length");
                    require(ptr==(writes==1?0x1241a0:BUF),"write pointer");
                    int count=(int)n-(shortAt==writes?1:0);
                    int error=(writeError!=0 && ((name.startsWith("payload") && writes==2)||(!name.startsWith("payload") && writes==1)))?writeError:0;
                    if(error!=0) count=0;
                    e.writeMemoryValue(toAddr(out),4,count);
                    if(count>0) file.write(e.readMemory(toAddr(ptr),count));
                    returned(e,error);continue;
                }
                if(pc==0x7324c) {
                    closes++;
                    require(word(e,reg(e,"r0"))==0x123456,"close handle pointer");
                    returned(e,closeError);continue;
                }
                require(e.step(monitor),"emulator at "+Long.toHexString(pc)+": "+e.getLastError());
            }
            require(steps<1200,"instruction limit");
            if(!stock) {
                require(reg(e,"r0")== (expected&0xffffffffL),"return status "+Long.toHexString(reg(e,"r0"))+" expected "+expected);
                require(reg(e,"sp")==SP && reg(e,"blink")==RET,"stack/return restoration");
                for(int i=13;i<=25;i++) require(reg(e,"r"+i)==0xabc00000L+i,"callee-saved r"+i);
                require(closes==((pathError!=0||openError!=0||path.length()<12||path.length()>127)?0:1),"close count");
                require(word(e,LOG+4)==18,"attempt counter");
                if(expected==0) {
                    require(writes==2 && word(e,LOG+8)==5,"success state");
                    require(word(e,LOG+20)==1536 && word(e,LOG+24)==PIXELS,"diagnostic counts");
                    byte[] expectedFile=new byte[1536+raw.length];
                    System.arraycopy(expectedHeader,0,expectedFile,0,1536);
                    System.arraycopy(raw,0,expectedFile,1536,raw.length);
                    require(Arrays.equals(file.toByteArray(),expectedFile),"actual write content");
                    if(name.equals("success")) Files.write(build.resolve("emulated.DNG"),file.toByteArray());
                    if(captureMetadata&&name.startsWith("capture-")) Files.write(build.resolve("emulated-"+name+".DNG"),file.toByteArray());
                } else require(word(e,LOG+12)==(expected&0xffffffffL),"diagnostic first error");
            }
            if(captureMetadata) {
                require(formatters==(stock?0:1),"formatter count/fallback");
                require(Arrays.equals(e.readMemory(toAddr(META),256),capture),"capture record modified");
            }
            JsonObject row=new JsonObject();row.addProperty("name",name);row.addProperty("passed",true);
            row.addProperty("instructions",steps);row.addProperty("writes",writes);row.addProperty("closes",closes);row.addProperty("stock_fallback",stock);
            if(captureMetadata) {row.addProperty("metadata_before_write",!stock);row.addProperty("stock_aperture_verified",true);row.add("fixture",fixture.deepCopy());}
            results.add(row);println("DNG EMULATION PASS: "+name);
        } finally { Files.writeString(build.resolve("trace-"+name+".txt"),trace.toString());e.dispose(); }
    }
    @Override public void run() throws Exception {
        root=Path.of(getScriptArgs()[0]);build=Path.of(getScriptArgs()[1]);
        fw=Files.readAllBytes(build.resolve("KC713.FW"));
        // Public regression fixture: deterministic sensor bytes, no personal photographs.
        raw=new byte[PIXELS];for(int i=0;i<raw.length;i++)raw[i]=(byte)(i*73+19);
        JsonObject manifest=JsonParser.parseString(Files.readString(build.resolve("manifest.json"))).getAsJsonObject();
        captureMetadata=manifest.has("metadata_timing")&&manifest.get("metadata_timing").getAsString().equals("before_raw_write");
        JsonArray fixtures=null;
        if(captureMetadata) {
            layout=JsonParser.parseString(Files.readString(build.resolve("header-layout.json"))).getAsJsonObject();
            fixtures=JsonParser.parseString(Files.readString(build.resolve("capture-fixtures.json"))).getAsJsonArray();
            fixture=fixtures.get(0).getAsJsonObject();
        }
        String p="A:/DCIM/100KC713/100_0293.JPG";
        scenario("success",0,PIXELS,p,0,0,0,0,0,0);
        scenario("path-error",0,PIXELS,p,11,0,0,0,0,11);
        scenario("open-error",0,PIXELS,p,0,13,0,0,0,13);
        scenario("header-error",0,PIXELS,p,0,0,17,0,0,17);
        scenario("header-short",0,PIXELS,p,0,0,0,1,0,-1);
        scenario("payload-error",0,PIXELS,p,0,0,19,0,0,19);
        scenario("payload-short",0,PIXELS,p,0,0,0,2,0,-1);
        scenario("close-error",0,PIXELS,p,0,0,0,0,23,23);
        scenario("header-error-close-error",0,PIXELS,p,0,0,17,0,23,17);
        scenario("payload-error-close-error",0,PIXELS,p,0,0,19,0,23,19);
        scenario("short-path",0,PIXELS,"short.JPG",0,0,0,0,0,-1);
        scenario("long-path",0,PIXELS,"x".repeat(116)+"100_0293.JPG",0,0,0,0,0,-1);
        scenario("minimum-path",0,PIXELS,"100_0293.JPG",0,0,0,0,0,0);
        scenario("maximum-path",0,PIXELS,"x".repeat(115)+"100_0293.JPG",0,0,0,0,0,0);
        scenario("black-frame-stock",1,PIXELS,p,0,0,0,0,0,0);
        scenario("unknown-kind-stock",2,PIXELS,p,0,0,0,0,0,0);
        scenario("16-bit-frame-stock",0,PIXELS*2,p,0,0,0,0,0,0);
        scenario("small-frame-stock",0,1024,p,0,0,0,0,0,0);
        if(captureMetadata) for(JsonElement element:fixtures) {
            fixture=element.getAsJsonObject();
            if(fixture.has("payload_dng")) {
                byte[] source=Files.readAllBytes(root.resolve(fixture.get("payload_dng").getAsString()));
                raw=Arrays.copyOfRange(source,1536,source.length);
            }
            scenario("capture-"+fixture.get("name").getAsString(),0,PIXELS,p,0,0,0,0,0,0);
        }
        JsonObject report=new JsonObject();report.addProperty("passed",true);report.addProperty("engine","Ghidra ARCompact p-code emulator; external file APIs mocked");
        report.addProperty("firmware_sha256",HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(fw)));
        report.add("scenarios",results);Files.writeString(build.resolve("emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");
        println("DNG EMULATION COMPLETE: "+results.size()+" scenarios");
    }
}
