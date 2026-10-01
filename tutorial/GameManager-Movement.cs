using UnityEngine;

public class GameManager : MonoBehaviour
{
    public static GameManager Instance { get; private set; }
    public bool IsPlaying => true;
    public Vector2 MobileDirection { get; private set; }
    private float mobileInputUntil;

    private void Awake()
    {
        Instance = this;
        Camera camera = Camera.main;
        if (camera == null)
        {
            var cameraObject = new GameObject("Main Camera");
            camera = cameraObject.AddComponent<Camera>();
            cameraObject.tag = "MainCamera";
        }
        camera.orthographic = true;
        camera.orthographicSize = 5.3f;
        camera.transform.position = new Vector3(0, 0, -10);
        var player = new GameObject("Player");
        var texture = new Texture2D(32, 32);
        for (int y = 0; y < 32; y++)
            for (int x = 0; x < 32; x++) texture.SetPixel(x, y, Color.cyan);
        texture.Apply();
        var renderer = player.AddComponent<SpriteRenderer>();
        renderer.sprite = Sprite.Create(texture, new Rect(0, 0, 32, 32),
            new Vector2(0.5f, 0.5f), 32);
        player.AddComponent<Rigidbody2D>();
        player.AddComponent<BoxCollider2D>();
        player.AddComponent<PlayerController>();
    }

    private void OnGUI()
    {
        Vector2 direction = Vector2.zero;
        if (GUI.RepeatButton(new Rect(90, 20, 70, 70), "UP")) direction.y++;
        if (GUI.RepeatButton(new Rect(90, 100, 70, 70), "DOWN")) direction.y--;
        if (GUI.RepeatButton(new Rect(10, 100, 70, 70), "LEFT")) direction.x--;
        if (GUI.RepeatButton(new Rect(170, 100, 70, 70), "RIGHT")) direction.x++;
        if (direction != Vector2.zero)
        {
            MobileDirection = direction;
            mobileInputUntil = Time.time + 0.08f;
        }
        else if (Time.time >= mobileInputUntil) MobileDirection = Vector2.zero;
    }
}
