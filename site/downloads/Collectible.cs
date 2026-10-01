using UnityEngine;

[RequireComponent(typeof(Collider2D))]
public class Collectible : MonoBehaviour
{
    private Vector3 startScale;

    private void Awake()
    {
        GetComponent<Collider2D>().isTrigger = true;
        startScale = transform.localScale;
    }

    private void Update()
    {
        transform.Rotate(0f, 0f, 70f * Time.deltaTime);
        float pulse = 1f + Mathf.Sin(Time.time * 4f) * 0.08f;
        transform.localScale = startScale * pulse;
    }

    private void OnTriggerEnter2D(Collider2D other)
    {
        if (!other.TryGetComponent<PlayerController>(out _)) return;
        GameManager.Instance.Collect(this);
    }
}
