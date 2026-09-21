using System.Collections.Generic;
using System.IO;
using UnityEngine;

public class GameManager : MonoBehaviour
{
    private enum GameState { Playing, Won, Lost }

    public static GameManager Instance { get; private set; }
    public bool IsPlaying => state == GameState.Playing;
    public Vector2 MobileDirection { get; private set; }

    private const int Target = 5;
    private readonly List<GameObject> createdObjects = new();
    private readonly Vector2[] crystalPositions =
    {
        new(-5.7f, 2.8f), new(-2.5f, 0.8f), new(0.8f, 3.0f),
        new(3.2f, -1.8f), new(5.7f, 2.2f)
    };
    private readonly Vector2[] hazardPositions =
    {
        new(-4.0f, -1.8f), new(-0.6f, -0.2f), new(2.2f, 1.5f),
        new(5.0f, -0.5f)
    };

    private PlayerController player;
    private GameState state;
    private int collected;
    private int hearts;
    private float invulnerableUntil;
    private float hintUntil;
    private string hint = "";
    private GUIStyle titleStyle;
    private GUIStyle textStyle;
    private GUIStyle centerStyle;
    private GUIStyle buttonStyle;
    private Texture2D panelTexture;
    private Texture2D buttonTexture;
    private Texture2D buttonPressedTexture;

    private void Awake()
    {
        Instance = this;
        Application.targetFrameRate = 60;
        BuildLevel();
        RestartGame();
    }

    private void Update()
    {
        if (Input.GetKeyDown(KeyCode.R)) RestartGame();

        // Клавиши F6-F9 нужны преподавателю для быстрой демонстрации и снимков.
        if (Input.GetKeyDown(KeyCode.F6) && IsPlaying) DebugCollectOne();
        if (Input.GetKeyDown(KeyCode.F7)) DebugSetState(true);
        if (Input.GetKeyDown(KeyCode.F8)) DebugSetState(false);
        if (Input.GetKeyDown(KeyCode.F9)) CaptureScreenshot();
    }

    private void BuildLevel()
    {
        CreateCamera();
        CreateDecor();
        CreateWalls();

        var playerObject = CreateSpriteObject(
            "Player", new Vector2(-6.5f, -3.1f), new Vector2(0.75f, 0.75f),
            new Color(0.19f, 0.88f, 1f), Shape.Circle, 10);
        playerObject.AddComponent<Rigidbody2D>();
        playerObject.AddComponent<CircleCollider2D>();
        player = playerObject.AddComponent<PlayerController>();

        foreach (Vector2 position in hazardPositions)
        {
            var hazard = CreateSpriteObject(
                "Hazard", position, new Vector2(0.85f, 0.85f),
                new Color(1f, 0.25f, 0.28f), Shape.Cross, 4);
            hazard.AddComponent<CircleCollider2D>();
            hazard.AddComponent<Hazard>();
        }

        var exit = CreateSpriteObject(
            "Exit", new Vector2(6.5f, 3.15f), new Vector2(1.2f, 1.2f),
            new Color(0.25f, 0.82f, 0.45f), Shape.Exit, 2);
        exit.AddComponent<BoxCollider2D>();
        exit.AddComponent<ExitZone>();

        CreateCrystals();
    }

    private void CreateCamera()
    {
        Camera camera = Camera.main;
        if (camera == null)
        {
            var cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            camera = cameraObject.AddComponent<Camera>();
        }
        camera.orthographic = true;
        camera.orthographicSize = 5.3f;
        camera.transform.position = new Vector3(0f, 0f, -10f);
        camera.backgroundColor = new Color(0.035f, 0.055f, 0.10f);
    }

    private void CreateDecor()
    {
        CreateSpriteObject("Field", Vector2.zero, new Vector2(16.4f, 9.2f),
            new Color(0.07f, 0.10f, 0.18f), Shape.Square, -10);
        for (int x = -7; x <= 7; x += 2)
            for (int y = -4; y <= 4; y += 2)
                CreateSpriteObject("FloorDot", new Vector2(x, y), Vector2.one * 0.06f,
                    new Color(0.18f, 0.23f, 0.34f), Shape.Circle, -9);
    }

    private void CreateWalls()
    {
        CreateWall("WallTop", new Vector2(0f, 4.65f), new Vector2(17f, 0.3f));
        CreateWall("WallBottom", new Vector2(0f, -4.65f), new Vector2(17f, 0.3f));
        CreateWall("WallLeft", new Vector2(-8.35f, 0f), new Vector2(0.3f, 9.6f));
        CreateWall("WallRight", new Vector2(8.35f, 0f), new Vector2(0.3f, 9.6f));
        CreateWall("WallA", new Vector2(-3.8f, 1.2f), new Vector2(0.35f, 3.0f));
        CreateWall("WallB", new Vector2(1.4f, -2.2f), new Vector2(3.2f, 0.35f));
        CreateWall("WallC", new Vector2(4.4f, 2.0f), new Vector2(0.35f, 2.5f));
    }

    private void CreateWall(string name, Vector2 position, Vector2 scale)
    {
        var wall = CreateSpriteObject(name, position, scale,
            new Color(0.20f, 0.27f, 0.40f), Shape.Square, 1);
        wall.AddComponent<BoxCollider2D>();
    }

    private void CreateCrystals()
    {
        foreach (Vector2 position in crystalPositions)
        {
            var crystal = CreateSpriteObject(
                "Crystal", position, new Vector2(0.62f, 0.82f),
                new Color(1f, 0.78f, 0.16f), Shape.Diamond, 5);
            crystal.AddComponent<PolygonCollider2D>();
            crystal.AddComponent<Collectible>();
            createdObjects.Add(crystal);
        }
    }

    private GameObject CreateSpriteObject(
        string name, Vector2 position, Vector2 scale,
        Color color, Shape shape, int order)
    {
        var item = new GameObject(name);
        item.transform.position = position;
        item.transform.localScale = scale;
        var renderer = item.AddComponent<SpriteRenderer>();
        renderer.sprite = CreateSprite(shape, color);
        renderer.sortingOrder = order;
        return item;
    }

    private static Sprite CreateSprite(Shape shape, Color color)
    {
        const int size = 64;
        var texture = new Texture2D(size, size, TextureFormat.RGBA32, false);
        texture.filterMode = FilterMode.Bilinear;
        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float nx = (x + 0.5f) / size * 2f - 1f;
                float ny = (y + 0.5f) / size * 2f - 1f;
                bool inside = shape switch
                {
                    Shape.Circle => nx * nx + ny * ny <= 0.90f,
                    Shape.Diamond => Mathf.Abs(nx) + Mathf.Abs(ny) <= 0.92f,
                    Shape.Cross => Mathf.Abs(nx - ny) < 0.22f || Mathf.Abs(nx + ny) < 0.22f,
                    Shape.Exit => Mathf.Max(Mathf.Abs(nx), Mathf.Abs(ny)) <= 0.92f &&
                                  Mathf.Min(Mathf.Abs(nx), Mathf.Abs(ny)) >= 0.22f,
                    _ => true
                };
                texture.SetPixel(x, y, inside ? color : Color.clear);
            }
        }
        texture.Apply();
        return Sprite.Create(texture, new Rect(0, 0, size, size),
            new Vector2(0.5f, 0.5f), size);
    }

    public void Collect(Collectible item)
    {
        if (!IsPlaying) return;
        collected++;
        createdObjects.Remove(item.gameObject);
        Destroy(item.gameObject);
        ShowHint($"Кристалл собран: {collected} из {Target}");
    }

    public void HitHazard()
    {
        if (!IsPlaying || Time.time < invulnerableUntil) return;
        hearts--;
        invulnerableUntil = Time.time + 1f;
        player.ReturnToStart();
        if (hearts <= 0)
        {
            state = GameState.Lost;
            MobileDirection = Vector2.zero;
        }
        else ShowHint("Опасность! Потеряна одна жизнь");
    }

    public void TryFinishLevel()
    {
        if (!IsPlaying) return;
        if (collected == Target)
        {
            state = GameState.Won;
            MobileDirection = Vector2.zero;
        }
        else ShowHint($"Сначала соберите все кристаллы: {collected} из {Target}");
    }

    private void ShowHint(string message)
    {
        hint = message;
        hintUntil = Time.time + 2.2f;
    }

    private void RestartGame()
    {
        foreach (GameObject item in createdObjects)
            if (item != null) Destroy(item);
        createdObjects.Clear();
        collected = 0;
        hearts = 3;
        state = GameState.Playing;
        MobileDirection = Vector2.zero;
        hint = "Соберите 5 кристаллов и войдите в зелёный портал";
        hintUntil = Time.time + 4f;
        if (player != null) player.ReturnToStart();
        CreateCrystals();
    }

    private void DebugCollectOne()
    {
        if (createdObjects.Count == 0) return;
        Collect(createdObjects[0].GetComponent<Collectible>());
    }

    private void DebugSetState(bool won)
    {
        if (won)
        {
            foreach (GameObject item in new List<GameObject>(createdObjects))
                if (item != null) Destroy(item);
            createdObjects.Clear();
            collected = Target;
            state = GameState.Won;
        }
        else
        {
            hearts = 0;
            state = GameState.Lost;
        }
        MobileDirection = Vector2.zero;
    }

    private void CaptureScreenshot()
    {
        string directory = Path.GetFullPath(Path.Combine(Application.dataPath,
            "../Documentation/Screenshots"));
        Directory.CreateDirectory(directory);
        string stateName = state.ToString().ToLowerInvariant();
        string path = Path.Combine(directory,
            $"game-{stateName}-{collected}-of-{Target}.png");
        ScreenCapture.CaptureScreenshot(path, 1);
        ShowHint("Снимок сохранён: " + Path.GetFileName(path));
    }

    private void CreateGuiStyles()
    {
        if (titleStyle != null) return;
        panelTexture = SolidTexture(new Color(0.055f, 0.075f, 0.13f, 0.96f));
        buttonTexture = SolidTexture(new Color(0.12f, 0.18f, 0.30f, 0.94f));
        buttonPressedTexture = SolidTexture(new Color(0.16f, 0.55f, 0.75f, 0.98f));

        titleStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = 28, fontStyle = FontStyle.Bold,
            normal = { textColor = Color.white }
        };
        textStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = 19, normal = { textColor = new Color(0.82f, 0.88f, 0.98f) }
        };
        centerStyle = new GUIStyle(titleStyle)
        {
            alignment = TextAnchor.MiddleCenter, fontSize = 34
        };
        buttonStyle = new GUIStyle(GUI.skin.button)
        {
            fontSize = 25, fontStyle = FontStyle.Bold,
            alignment = TextAnchor.MiddleCenter,
            normal = { background = buttonTexture, textColor = Color.white },
            hover = { background = buttonPressedTexture, textColor = Color.white },
            active = { background = buttonPressedTexture, textColor = Color.white }
        };
    }

    private static Texture2D SolidTexture(Color color)
    {
        var texture = new Texture2D(1, 1);
        texture.SetPixel(0, 0, color);
        texture.Apply();
        return texture;
    }

    private void OnGUI()
    {
        CreateGuiStyles();
        float scale = Mathf.Min(Screen.width / 1280f, Screen.height / 720f);
        GUI.matrix = Matrix4x4.Scale(Vector3.one * scale);

        GUI.DrawTexture(new Rect(24, 20, 1232, 78), panelTexture);
        GUI.Label(new Rect(48, 35, 430, 45), "КРИСТАЛЬНЫЙ МАРШРУТ", titleStyle);
        GUI.Label(new Rect(500, 35, 280, 45), $"Кристаллы: {collected}/{Target}", textStyle);
        GUI.Label(new Rect(820, 35, 250, 45), $"Жизни: {new string('♥', hearts)}", textStyle);
        GUI.Label(new Rect(1080, 35, 150, 45), "R — заново", textStyle);

        Vector2 direction = Vector2.zero;
        if (GUI.RepeatButton(new Rect(110, 540, 72, 72), "↑", buttonStyle)) direction.y += 1f;
        if (GUI.RepeatButton(new Rect(110, 620, 72, 72), "↓", buttonStyle)) direction.y -= 1f;
        if (GUI.RepeatButton(new Rect(30, 620, 72, 72), "←", buttonStyle)) direction.x -= 1f;
        if (GUI.RepeatButton(new Rect(190, 620, 72, 72), "→", buttonStyle)) direction.x += 1f;
        MobileDirection = Vector2.ClampMagnitude(direction, 1f);

        if (Time.time < hintUntil)
        {
            GUI.DrawTexture(new Rect(340, 620, 600, 58), panelTexture);
            GUI.Label(new Rect(360, 629, 560, 40), hint, textStyle);
        }

        if (state == GameState.Playing) return;
        GUI.DrawTexture(new Rect(340, 210, 600, 280), panelTexture);
        string heading = state == GameState.Won ? "УРОВЕНЬ ПРОЙДЕН" : "ПОПРОБУЙТЕ ЕЩЁ";
        string message = state == GameState.Won
            ? "Все кристаллы собраны, портал открыт."
            : "Жизни закончились. Измените маршрут.";
        GUI.Label(new Rect(370, 250, 540, 60), heading, centerStyle);
        GUI.Label(new Rect(405, 330, 470, 45), message, textStyle);
        if (GUI.Button(new Rect(475, 400, 330, 62), "НАЧАТЬ ЗАНОВО", buttonStyle))
            RestartGame();
    }

    private enum Shape { Square, Circle, Diamond, Cross, Exit }
}
