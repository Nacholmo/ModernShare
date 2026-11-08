// Diagnostic inspection of disputed function ownership and AUX p-code.
// @category Kodak
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.pcode.*;
public class InspectProgram extends GhidraScript {
 public void run() throws Exception {
  for(long n:new long[]{0x67e04,0x67f9e,0x67fa6,0x67fb8,0x67fc0,0x680d6,0x68100,0x68190}){
   Address a=toAddr(n);Function f=getFunctionContaining(a);Instruction i=getInstructionAt(a);
   println(a+" owner="+(f==null?null:f.getName()+"@"+f.getEntryPoint())+" instruction="+i);
   if(f!=null&&n==0x67e04)println("BODY "+f.getBody());
  }
  for(Instruction i:currentProgram.getListing().getInstructions(new AddressSet(toAddr(0x67f88),toAddr(0x67fc8)),true)){
   println(i.getAddress()+" "+i+" flow="+i.getFlowType()+" flows="+java.util.Arrays.toString(i.getFlows()));
  }
  for(PcodeOp op:getInstructionAt(toAddr(0x11e15e)).getPcode())println("AUX PCODE "+op);
 }
}
