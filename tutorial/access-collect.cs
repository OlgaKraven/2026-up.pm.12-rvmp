if (!access.Activate(item.itemIndex - 1))
{
    ShowHint("Условие уже выполнено");
    return;
}
collected++;
