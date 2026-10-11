import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.iface.ClassDef;
import com.android.tools.smali.dexlib2.iface.DexFile;
import com.android.tools.smali.dexlib2.immutable.ImmutableDexFile;
import java.util.ArrayList;

/** Replace exactly one class; retain every other class from the original DEX. */
public class MergeDex {
    public static void main(String[] args) throws Exception {
        DexFile original = DexFileFactory.loadDexFile(args[0], null);
        DexFile replacement = DexFileFactory.loadDexFile(args[1], original.getOpcodes());
        if (replacement.getClasses().size() != 1) {
            throw new IllegalStateException("Replacement DEX must contain exactly one class");
        }
        ClassDef patched = replacement.getClasses().iterator().next();
        if (!patched.getType().equals("LX/00MT;")) {
            throw new IllegalStateException("Unexpected replacement class: " + patched.getType());
        }
        ArrayList<ClassDef> classes = new ArrayList<>();
        int replaced = 0;
        for (ClassDef cls : original.getClasses()) {
            if (cls.getType().equals(patched.getType())) {
                classes.add(patched);
                replaced++;
            } else {
                classes.add(cls);
            }
        }
        if (replaced != 1) throw new IllegalStateException("Expected one target class");
        DexFileFactory.writeDexFile(args[2], new ImmutableDexFile(original.getOpcodes(), classes));
        DexFile result = DexFileFactory.loadDexFile(args[2], null);
        if (result.getClasses().size() != original.getClasses().size()) {
            throw new IllegalStateException("Class count changed");
        }
        System.out.println("Replaced LX/00MT; and retained " + (classes.size() - 1) + " other classes");
    }
}
