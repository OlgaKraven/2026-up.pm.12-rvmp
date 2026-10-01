if (!selection.Take(item.itemType == 0))
{
    HitHazard();
    return;
}
collected = selection.Progress;
