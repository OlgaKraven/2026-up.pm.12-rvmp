Sprite picture = name == "Player" ? Resources.Load<Sprite>("player") : null;
renderer.sprite = picture != null ? picture : CreateSprite(shape, color);
