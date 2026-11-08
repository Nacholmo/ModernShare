// Seed stock C713 firmware memory and annotations from the isolated project.
// @category Kodak
import java.io.*;
import java.math.BigInteger;
import java.nio.file.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class SeedKodak extends GhidraScript {
    private Path root;
    private JsonObject json(String path) throws Exception {
        return JsonParser.parseString(Files.readString(root.resolve(path))).getAsJsonObject();
    }
    private Address addr(JsonObject o) { return toAddr(Long.decode(o.get("address").getAsString())); }
    private void type(long at, DataType dt) throws Exception {
        clearListing(toAddr(at), toAddr(at + dt.getLength() - 1));
        createData(toAddr(at), dt);
    }
    @Override public void run() throws Exception {
        root = Path.of(getScriptArgs()[0]).toAbsolutePath();
        Memory mem = currentProgram.getMemory();
        MemoryBlock code = mem.getBlock(toAddr(0x30000));
        code.setName("firmware_code"); code.setRead(true); code.setWrite(false); code.setExecute(true);
        code.setComment("Stock code section. RAM addresses, not firmware file offsets. Contains literal pools and zero caves.");
        for (JsonElement element : json("input/manifest.json").getAsJsonArray("sections")) {
            JsonObject s = element.getAsJsonObject();
            int index = s.get("index").getAsInt();
            if (index != 1 && index != 2) continue;
            try (InputStream stream = Files.newInputStream(root.resolve(s.get("path").getAsString()))) {
                MemoryBlock b = mem.createInitializedBlock("firmware_"+s.get("name").getAsString(),
                    toAddr(s.get("ram_address").getAsLong()), stream, s.get("size").getAsLong(), monitor, false);
                b.setRead(true); b.setWrite(index == 1); b.setExecute(false);
            }
        }
        // Reserve genuinely missing RAM only; leave values unknown, not fabricated zeros.
        long dataEnd = 0x130000;
        for (MemoryBlock b: mem.getBlocks()) {
            if (b.getName().equals("firmware_data")) dataEnd = b.getEnd().getOffset()+1;
        }
        if (dataEnd < 0x1a0000) {
            MemoryBlock b = mem.createUninitializedBlock("runtime_ram",toAddr(dataEnd),0x1a0000-dataEnd,false);
            b.setRead(true); b.setWrite(true); b.setExecute(false);
            b.setComment("Runtime RAM: no dump imported; initial contents unknown.");
        }
        MemoryBlock isp = mem.createUninitializedBlock("isp_mmio",toAddr(0x0ff10000),0x2000,false);
        isp.setRead(true); isp.setWrite(true); isp.setExecute(false); isp.setVolatile(true);
        createLabel(toAddr(0x0ff10118),"isp_color_effect",true);
        createLabel(toAddr(0x0ff11000),"isp_per_shot_tone_lut",true);
        currentProgram.getProgramContext().setValue(currentProgram.getRegister("gp"),
            toAddr(0x30000),toAddr(0x12ffff),BigInteger.valueOf(0x172ef4));
        runScript("ApplyAnnotations.java", getScriptArgs());
        println("Kodak seed annotations and memory mapping completed.");
    }
}
