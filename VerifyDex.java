import com.android.tools.smali.baksmali.Adaptors.ClassDefinition;
import com.android.tools.smali.baksmali.BaksmaliOptions;
import com.android.tools.smali.baksmali.formatter.BaksmaliWriter;
import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.iface.ClassDef;
import com.android.tools.smali.dexlib2.iface.DexFile;
import com.android.tools.smali.dexlib2.iface.Method;
import com.android.tools.smali.dexlib2.iface.MethodImplementation;
import java.io.StringWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.TreeSet;

/** Compare complete canonical disassembly, including annotations and debug metadata. */
public class VerifyDex {
    static String canonical(ClassDef cls) throws Exception {
        BaksmaliOptions options = new BaksmaliOptions();
        options.accessorComments = false;
        StringWriter text = new StringWriter();
        ClassDefinition definition = new ClassDefinition(options, cls);
        definition.writeTo(new BaksmaliWriter(text));
        if (definition.hadValidationErrors()) {
            throw new IllegalStateException("Disassembly validation failed: " + cls.getType());
        }
        return text.toString();
    }

    // DexPool combines adjacent equivalent try ranges and drops duplicate catches
    // of the same type. Check actual handler selection rather than label layout.
    static String withoutTryLayout(String text) {
        return text.lines().map(String::trim)
            .filter(line -> !line.isEmpty() && !line.startsWith(".catch")
                && !line.startsWith(":try_start_") && !line.startsWith(":try_end_"))
            .collect(java.util.stream.Collectors.joining("\n"));
    }

    static String methodKey(Method method) {
        return method.getName() + method.getParameterTypes() + method.getReturnType();
    }

    static String effectiveHandlers(MethodImplementation body, int address) {
        if (body == null) return "";
        HashSet<String> seen = new HashSet<>();
        ArrayList<String> result = new ArrayList<>();
        for (var block : body.getTryBlocks()) {
            if (address < block.getStartCodeAddress()
                    || address >= block.getStartCodeAddress() + block.getCodeUnitCount()) continue;
            for (var handler : block.getExceptionHandlers()) {
                String type = handler.getExceptionType();
                if (type == null) type = "*";
                if (seen.add(type)) result.add(type + "@" + handler.getHandlerCodeAddress());
                if (type.equals("*")) return result.toString();
            }
        }
        return result.toString();
    }

    static void compareTrySemantics(ClassDef before, ClassDef after) {
        HashMap<String, Method> methods = new HashMap<>();
        for (Method method : after.getMethods()) methods.put(methodKey(method), method);
        for (Method old : before.getMethods()) {
            Method replacement = methods.get(methodKey(old));
            if (replacement == null) throw new IllegalStateException("Missing method");
            MethodImplementation first = old.getImplementation();
            MethodImplementation second = replacement.getImplementation();
            TreeSet<Integer> boundaries = new TreeSet<>();
            for (MethodImplementation body : new MethodImplementation[] {first, second}) {
                if (body == null) continue;
                for (var block : body.getTryBlocks()) {
                    boundaries.add(block.getStartCodeAddress());
                    boundaries.add(block.getStartCodeAddress() + block.getCodeUnitCount());
                }
            }
            for (int address : boundaries) {
                if (!effectiveHandlers(first, address).equals(effectiveHandlers(second, address))) {
                    throw new IllegalStateException("Exception behavior changed: "
                        + before.getType() + " " + methodKey(old) + "@" + address);
                }
            }
        }
    }

    static LinkedHashMap<String, String> methodBodies(String text) {
        LinkedHashMap<String, String> result = new LinkedHashMap<>();
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile(
            "(?ms)^\\.method ([^\\n]+)\\n.*?^\\.end method$").matcher(text);
        while (matcher.find()) result.put(matcher.group(1), matcher.group());
        return result;
    }

    public static void main(String[] args) throws Exception {
        DexFile original = DexFileFactory.loadDexFile(args[0], null);
        DexFile patched = DexFileFactory.loadDexFile(args[1], original.getOpcodes());
        HashMap<String, ClassDef> after = new HashMap<>();
        for (ClassDef cls : patched.getClasses()) after.put(cls.getType(), cls);
        if (after.size() != original.getClasses().size()) {
            throw new IllegalStateException("Class counts differ");
        }
        ArrayList<String> changed = new ArrayList<>();
        ArrayList<String> normalized = new ArrayList<>();
        for (ClassDef cls : original.getClasses()) {
            ClassDef other = after.remove(cls.getType());
            if (other == null) throw new IllegalStateException("Missing class: " + cls.getType());
            String beforeText = canonical(cls);
            String afterText = canonical(other);
            if (!beforeText.equals(afterText)) {
                if (!cls.getType().equals("LX/00MT;")
                        && withoutTryLayout(beforeText).equals(withoutTryLayout(afterText))) {
                    compareTrySemantics(cls, other);
                    normalized.add(cls.getType());
                } else {
                    changed.add(cls.getType());
                }
                if (args.length > 3) {
                    Path diffs = Path.of(args[3]);
                    Files.createDirectories(diffs);
                    String name = cls.getType().replace('/', '_').replace(';', '_');
                    Files.writeString(diffs.resolve(name + "-before.smali"), beforeText);
                    Files.writeString(diffs.resolve(name + "-after.smali"), afterText);
                }
            }
            if (cls.getType().equals("LX/00MT;")) {
                Files.writeString(Path.of(args[2]), afterText);
                var beforeMethods = methodBodies(beforeText);
                var afterMethods = methodBodies(afterText);
                if (!beforeMethods.keySet().equals(afterMethods.keySet())) {
                    throw new IllegalStateException("Target class method set changed");
                }
                HashSet<String> modified = new HashSet<>();
                for (String signature : beforeMethods.keySet()) {
                    if (!beforeMethods.get(signature).equals(afterMethods.get(signature))) {
                        modified.add(signature.substring(signature.indexOf(" A") + 1,
                            signature.indexOf('(')));
                    }
                }
                if (!modified.equals(java.util.Set.of("A00", "A01", "A03"))) {
                    throw new IllegalStateException("Unexpected changed target methods: " + modified);
                }
            }
        }
        if (!changed.equals(java.util.List.of("LX/00MT;"))) {
            throw new IllegalStateException("Unexpected changed classes: " + changed);
        }
        System.out.println("{\"class_count\":" + original.getClasses().size()
            + ",\"equivalent_other_classes\":" + (original.getClasses().size() - 1)
            + ",\"changed_classes\":[\"LX/00MT;\"],\"changed_methods\":[\"A00\",\"A01\",\"A03\"]"
            + ",\"exception_table_normalization_count\":" + normalized.size()
            + ",\"comparison\":\"complete canonical smali and effective exception handlers\"}");
    }
}
