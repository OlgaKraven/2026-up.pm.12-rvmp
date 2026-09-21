using UnityEngine;

[RequireComponent(typeof(Rigidbody2D), typeof(Collider2D))]
public class PlayerController : MonoBehaviour
{
    [SerializeField, Min(1f)] private float speed = 5f;
    private Rigidbody2D body;
    private Vector2 startPosition;

    private void Awake()
    {
        body = GetComponent<Rigidbody2D>();
        body.gravityScale = 0f;
        body.freezeRotation = true;
        startPosition = transform.position;
    }

    private void FixedUpdate()
    {
        if (GameManager.Instance == null || !GameManager.Instance.IsPlaying)
        {
            body.linearVelocity = Vector2.zero;
            return;
        }

        Vector2 keyboard = new Vector2(
            ReadAxis(KeyCode.A, KeyCode.LeftArrow, KeyCode.D, KeyCode.RightArrow),
            ReadAxis(KeyCode.S, KeyCode.DownArrow, KeyCode.W, KeyCode.UpArrow));
        Vector2 direction = Vector2.ClampMagnitude(
            keyboard + GameManager.Instance.MobileDirection, 1f);
        body.linearVelocity = direction * speed;
    }

    private static float ReadAxis(
        KeyCode negativeA, KeyCode negativeB,
        KeyCode positiveA, KeyCode positiveB)
    {
        float value = 0f;
        if (Input.GetKey(negativeA) || Input.GetKey(negativeB)) value -= 1f;
        if (Input.GetKey(positiveA) || Input.GetKey(positiveB)) value += 1f;
        return value;
    }

    public void ReturnToStart()
    {
        body.linearVelocity = Vector2.zero;
        body.position = startPosition;
    }
}
