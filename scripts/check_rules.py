"""Test pure C# rules and the actual Collect body without pretending to run Unity."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/rule-tests';work.mkdir(parents=True,exist_ok=True)
manager=(ROOT/'unity-project/Assets/Scripts/GameManager.cs').read_text(encoding='utf-8')
method=re.search(r'    public void Collect\(Collectible item\)\s*\{.*?\n    \}',manager,re.S).group(0)
fixture='''using System.Collections.Generic;
public class TestObject { }
public class Collectible { public TestObject gameObject = new TestObject(); }
public class CollectContract
{
    public bool IsPlaying = true;
    private const int Target = 5;
    public int collected;
    public int DestroyCalls;
    public string hint;
    public readonly List<TestObject> createdObjects = new List<TestObject>();
    private void Destroy(TestObject item) { DestroyCalls++; }
    private void ShowHint(string value) { hint = value; }
METHOD
}
'''.replace('METHOD',method)
(work/'CollectContract.cs').write_text(fixture,encoding='utf-8')
project='''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>
<OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework>
<LangVersion>9.0</LangVersion><ImplicitUsings>disable</ImplicitUsings>
<Nullable>disable</Nullable><EnableDefaultCompileItems>false</EnableDefaultCompileItems>
</PropertyGroup><ItemGroup>
<Compile Include="CollectContract.cs" />
<Compile Include="../../unity-project/Assets/Scripts/MechanicModels.cs" />
<Compile Include="../../tests/Rules.cs" />
</ItemGroup></Project>'''
(work/'Rules.csproj').write_text(project,encoding='utf-8')
dotnet=os.environ.get('DOTNET_BIN') or shutil.which('dotnet')
if not dotnet:raise RuntimeError('Set DOTNET_BIN to the installed .NET SDK executable')
run=subprocess.run([dotnet,'run','--project',str(work/'Rules.csproj'),'--configuration','Release'],text=True,encoding='utf-8',capture_output=True)
print(run.stdout,end='')
if run.returncode:
    print(run.stderr);raise SystemExit(run.returncode)
count=int(re.search(r'PASS: (\d+) assertions',run.stdout).group(1))
(ROOT/'work/rule-check.json').write_text(json.dumps({'assertions':count,'models':6,'actual_method':'GameManager.Collect','unity_executed':False,'scope':'Pure C# models and callback acceptance contract; no scene, physics, rendering or input execution.'},indent=2)+'\n',encoding='utf-8')
