if (!sequence.Take(item.itemIndex, false))
{
    HitHazard();
    return;
}
collected = sequence.Expected - 1;
