"""ParseInstances 单实例非嵌套输出 bug：
输入 {"index":"3",...}（无实例名→值映射嵌套），每个 property.Value 不是
Object 就被 continue，导致 0 实例抛异常。修复：若根对象含 "index" 字段
（说明是单实例输出），把它当唯一实例解析。"""
from pathlib import Path

p = Path(r"D:\游戏文件\chatgpt\gameflow\src\Gameflow.Infrastructure.Windows\MuMuTargetAdapter.cs")
src = p.read_text(encoding="utf-8")
old = """        var instances = ImmutableArray.CreateBuilder<MuMuInstanceInfo>();
        foreach (var property in root.EnumerateObject())
        {
            if (property.Value.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            var entry = property.Value;
            if (!TryGetProperty(entry, \"index\", out var indexValue) ||
                !int.TryParse(GetString(indexValue) ?? property.Name, NumberStyles.Integer, CultureInfo.InvariantCulture, out var index))
            {
                index = int.TryParse(property.Name, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedName)
                    ? parsedName
                    : -1;
            }

            if (index < 0)
            {
                continue;
            }
"""
new = """        var instances = ImmutableArray.CreateBuilder<MuMuInstanceInfo>();
        // 单实例输出：根对象本身就是实例（含 index 字段），没有 index→实例 映射。
        if (TryGetProperty(root, "index", out _))
        {
            root = JsonDocument.Parse(root.GetRawText()).RootElement;
            var singleIndex = GetString(root, "index");
            var port = GetString(root, "adb_port");
            var host = GetString(root, "adb_host_ip")
                ?? GetString(root, "adb_ip")
                ?? GetString(root, "adb_host")
                ?? "127.0.0.1";
            var endpoint = GetString(root, "adb_endpoint")
                ?? GetString(root, "adb_url")
                ?? (string.IsNullOrWhiteSpace(port) ? null : $"{host}:{port}");
            instances.Add(new MuMuInstanceInfo(
                int.TryParse(singleIndex, NumberStyles.Integer, CultureInfo.InvariantCulture, out var idx) ? idx : -1,
                GetString(root, "name") ?? "MuMu",
                GetBoolean(root, "is_android_started"),
                int.TryParse(port, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedPort) ? parsedPort : null,
                endpoint));
            return [.. instances];
        }
        foreach (var property in root.EnumerateObject())
        {
            if (property.Value.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            var entry = property.Value;
            if (!TryGetProperty(entry, "index", out var indexValue) ||
                !int.TryParse(GetString(indexValue) ?? property.Name, NumberStyles.Integer, CultureInfo.InvariantCulture, out var index))
            {
                index = int.TryParse(property.Name, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedName)
                    ? parsedName
                    : -1;
            }

            if (index < 0)
            {
                continue;
            }
"""
assert old in src
src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print("ParseInstances 单实例兼容已加")
