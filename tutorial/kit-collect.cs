int required = item.itemType == 0 ? 2 : 1;
if (!kit.Take(item.itemType, required))
{
    ShowHint("Этот тип уже набран");
    return;
}
collected++;
