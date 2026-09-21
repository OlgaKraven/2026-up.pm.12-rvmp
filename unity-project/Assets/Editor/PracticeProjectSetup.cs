using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;

public static class PracticeProjectSetup
{
    [MenuItem("Practice/Prepare Main Scene")]
    public static void PrepareMainScene()
    {
        Directory.CreateDirectory("Assets/Scenes");
        Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,
            NewSceneMode.Single);
        EditorSceneManager.SaveScene(scene, "Assets/Scenes/Main.unity");
        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene("Assets/Scenes/Main.unity", true)
        };
        AssetDatabase.SaveAssets();
    }
}
