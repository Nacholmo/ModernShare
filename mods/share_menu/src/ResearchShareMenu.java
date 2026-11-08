// Read-only exploration of UI callback entries omitted from the stock full export.
// @category Kodak
import java.nio.file.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
public class ResearchShareMenu extends GhidraScript {
 public void run() throws Exception {
  Path out=Path.of(getScriptArgs()[0]);Files.createDirectories(out);
  DecompInterface dc=new DecompInterface();dc.openProgram(currentProgram);
  try {
   for(long at:new long[]{0xb967c,0xb97ac,0xb97c4,0xd6904,0xd694c,0xd6b10,0xd6bd0,0xd75f0,0xd760c,0xd762c,0x7bffc,0x7c260,0x7bf20,0x8f0d8,0x8f1e4}) {
    Function f=getFunctionAt(toAddr(at));
    if(f==null) {disassemble(toAddr(at));f=createFunction(toAddr(at),"UI_"+Long.toHexString(at));}
    if(f==null){println("NO FUNCTION "+Long.toHexString(at));continue;}
    DecompileResults result=dc.decompileFunction(f,60,monitor);
    if(result.decompileCompleted()) Files.writeString(out.resolve(String.format("%08x.c",at)),result.getDecompiledFunction().getC());
    StringBuilder asm=new StringBuilder();for(Instruction i:currentProgram.getListing().getInstructions(f.getBody(),true))asm.append(i.getAddress()+" "+i+"\n");
    Files.writeString(out.resolve(String.format("%08x.asm",at)),asm.toString());println("EXPORTED "+Long.toHexString(at));
   }
  }finally{dc.dispose();}
 }
}
