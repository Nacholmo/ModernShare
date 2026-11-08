// Apply the two getter signatures checked against their first-pass assembly.
// @category Kodak
import java.util.List;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;

public class RefineCaptureTypes extends GhidraScript {
    @Override public void run() throws Exception {
        DataType matrix=currentProgram.getDataTypeManager().getDataType("/CaptureMatrixQ16");
        if(matrix==null)throw new IllegalStateException("CaptureMatrixQ16 not defined; seed the project first.");
        for(long at:new long[]{0xaf508,0xaf514}){
            Function f=getFunctionAt(toAddr(at));
            if(f==null)throw new IllegalStateException("Missing getter at "+Long.toHexString(at));
            f.setReturnType(new PointerDataType(matrix,4),SourceType.USER_DEFINED);
            f.replaceParameters(List.of(new ParameterImpl(at==0xaf508?"illuminant":"color_mode",
                UnsignedIntegerDataType.dataType,currentProgram)),
                Function.FunctionUpdateType.DYNAMIC_STORAGE_ALL_PARAMS,true,SourceType.USER_DEFINED);
        }
        analyzeChanges(currentProgram);
        println("Applied assembly-reviewed capture getter signatures.");
    }
}
