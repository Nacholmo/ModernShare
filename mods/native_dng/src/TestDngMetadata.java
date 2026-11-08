// Execute the metadata wrapper's actual patched instructions with stock-builder/strftime mocks.
// @category Kodak
import java.nio.file.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;

public class TestDngMetadata extends GhidraScript {
    static final long HEADER=0x1241a0, META=0x180000, SP=0x19f000, RET=0xa4294, JPEG=0x400000;
    static final DateTimeFormatter DATE=DateTimeFormatter.ofPattern("uuuu:MM:dd HH:mm:ss");
    long reg(EmulatorHelper e,String r) {return e.readRegister(r).longValue()&0xffffffffL;}
    long word(EmulatorHelper e,long at) {return ByteBuffer.wrap(e.readMemory(toAddr(at),4)).order(ByteOrder.LITTLE_ENDIAN).getInt()&0xffffffffL;}
    void require(boolean v,String s) {if(!v) throw new IllegalStateException(s);}
    void returned(EmulatorHelper e,long value) {
        long next=reg(e,"blink");
        for(int i=0;i<=12;i++) e.writeRegister("r"+i,0xdead0000L+i);
        e.writeRegister("r0",value);e.writeRegister(e.getPCRegister(),next);
    }
    @Override public void run() throws Exception {
        Path root=Path.of(getScriptArgs()[0]),build=Path.of(getScriptArgs()[1]);
        byte[] fw=Files.readAllBytes(build.resolve("KC713.FW")),template=Files.readAllBytes(build.resolve("header.bin"));
        JsonObject layout=JsonParser.parseString(Files.readString(build.resolve("header-layout.json"))).getAsJsonObject();
        int date=layout.get("DATE").getAsInt(),exposure=layout.get("EXPOSURE").getAsInt();
        int aperture=layout.get("FNUMBER").getAsInt(),iso=layout.get("ISO").getAsInt();
        JsonArray fixtures=JsonParser.parseString(Files.readString(build.resolve("metadata-fixtures.json"))).getAsJsonArray();
        JsonArray results=new JsonArray();
        EmulatorHelper e=new EmulatorHelper(currentProgram);
        try {
            e.writeMemory(toAddr(0x30000),Arrays.copyOfRange(fw,0x200,0x100200));
            for(JsonElement element:fixtures) {
                JsonObject fixture=element.getAsJsonObject();String name=fixture.get("name").getAsString();
                LocalDateTime time=LocalDateTime.parse(fixture.get("date").getAsString(),DATE);
                int us=fixture.get("exposure_us").getAsInt(),fn=fixture.get("fnumber_100").getAsInt();
                int speed=fixture.get("iso").getAsInt(),status=fixture.get("stock_result").getAsInt();
                byte[] metadata=new byte[160];ByteBuffer m=ByteBuffer.wrap(metadata).order(ByteOrder.LITTLE_ENDIAN);
                int[] tm={time.getSecond(),time.getMinute(),time.getHour(),time.getDayOfMonth(),time.getMonthValue()-1,time.getYear()-1900,0,0,0};
                for(int i=0;i<tm.length;i++)m.putInt(12+i*4,tm[i]);
                m.putInt(0x48,us);m.putInt(0x4c,fn);m.putInt(0x60,speed);
                e.writeMemory(toAddr(META),metadata);
                byte[] stack=new byte[256];Arrays.fill(stack,(byte)0xa5);e.writeMemory(toAddr(SP-128),stack);
                for(int i=0;i<=25;i++)e.writeRegister("r"+i,0xabc00000L+i);
                e.writeRegister("r0",JPEG);e.writeRegister("r1",0x11111111);e.writeRegister("r14",META);
                e.writeRegister("sp",SP);e.writeRegister("blink",0x33333333);e.writeRegister(e.getPCRegister(),0xa4290);
                int steps=0,stockCalls=0,formatterCalls=0;
                while(steps++<1000) {
                    long pc=e.getExecutionAddress().getOffset();
                    if(pc==RET)break;
                    if(pc==0xa3a04) {
                        stockCalls++;
                        require(reg(e,"r0")==JPEG&&reg(e,"r1")==META,"stock builder arguments");
                        require(word(e,HEADER+exposure)==0&&word(e,HEADER+aperture)==0,"stale exposure/aperture");
                        require(e.readMemoryByte(toAddr(HEADER+iso))==0&&e.readMemoryByte(toAddr(HEADER+date))==0,"stale ISO/date");
                        if(status!=0)e.writeMemoryValue(toAddr(META+0x48),4,Math.max(us,714));
                        returned(e,status);continue;
                    }
                    if(pc==0x116be4) {
                        formatterCalls++;
                        require(reg(e,"r0")==HEADER+date&&reg(e,"r1")==20&&reg(e,"r3")==META+12,"strftime arguments");
                        require(reg(e,"r2")==0x127a08&&e.readNullTerminatedString(toAddr(reg(e,"r2")),64).equals("%Y:%m:%d %H:%M:%S"),"native format string");
                        ByteBuffer t=ByteBuffer.wrap(e.readMemory(toAddr(reg(e,"r3")),36)).order(ByteOrder.LITTLE_ENDIAN);
                        LocalDateTime actual=LocalDateTime.of(t.getInt(20)+1900,t.getInt(16)+1,t.getInt(12),t.getInt(8),t.getInt(4),t.getInt(0));
                        e.writeMemory(toAddr(HEADER+date),(actual.format(DATE)+"\0").getBytes(StandardCharsets.US_ASCII));
                        returned(e,19);continue;
                    }
                    require(e.step(monitor),"metadata emulation at "+Long.toHexString(pc)+": "+e.getLastError());
                }
                require(steps<1000&&stockCalls==1&&formatterCalls==(status==0?0:1),"call/step count");
                require(reg(e,"r0")==status&&reg(e,"sp")==SP&&reg(e,"blink")==RET,"result/stack/return");
                for(int i=13;i<=25;i++) require(reg(e,"r"+i)==(i==14?META:0xabc00000L+i),"callee-saved r"+i);
                byte[] expected=template.clone();ByteBuffer out=ByteBuffer.wrap(expected).order(ByteOrder.LITTLE_ENDIAN);
                Arrays.fill(expected,date,date+20,(byte)0);
                out.putInt(exposure,status==0?0:Math.max(us,714));out.putInt(aperture,status==0?0:fn);out.putShort(iso,(short)(status==0?0:speed));
                if(status!=0)System.arraycopy((time.format(DATE)+"\0").getBytes(StandardCharsets.US_ASCII),0,expected,date,20);
                byte[] actual=e.readMemory(toAddr(HEADER),1536);
                require(Arrays.equals(actual,expected),"header differs outside expected per-shot fields");
                Files.write(build.resolve("emulated-header-"+name+".bin"),actual);
                if(fixture.has("payload_dng")) {
                    byte[] source=Files.readAllBytes(root.resolve(fixture.get("payload_dng").getAsString()));
                    System.arraycopy(actual,0,source,0,1536);Files.write(build.resolve("emulated-metadata-"+name+".DNG"),source);
                }
                JsonObject row=new JsonObject();row.addProperty("name",name);row.addProperty("passed",true);
                row.addProperty("instructions",steps);row.addProperty("stock_calls",stockCalls);row.addProperty("formatter_calls",formatterCalls);results.add(row);
                println("DNG METADATA EMULATION PASS: "+name);
            }
        } finally {e.dispose();}
        JsonObject report=new JsonObject();report.addProperty("passed",true);
        report.addProperty("firmware_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(fw)));
        report.addProperty("engine","Actual wrapper/callsite instructions; stock EXIF builder and strftime mocked; one memory state reused across shots");
        report.add("scenarios",results);Files.writeString(build.resolve("metadata-emulation.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");
        println("DNG METADATA EMULATION COMPLETE: "+results.size()+" consecutive scenarios");
    }
}
