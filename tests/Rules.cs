using System;

internal static class Rules
{
    private static int assertions;
    private static void Check(bool value, string message)
    {
        assertions++;
        if (!value) throw new Exception(message);
    }
    private static void Main()
    {
        var selection = new MechanicModels.Selection();
        Check(!selection.Take(false), "Wrong selection rejected");
        Check(selection.Errors == 1 && selection.Progress == 0, "Wrong selection not progress");
        for (int i = 0; i < 5; i++) Check(selection.Take(true), "Correct selection");
        Check(selection.Progress == 5 && selection.Errors == 1, "Independent counts");
        selection.Reset(); Check(selection.Progress == 0 && selection.Errors == 0, "Selection reset");

        var sequence = new MechanicModels.Sequence();
        Check(sequence.Take(1, false), "First in order");
        Check(!sequence.Take(3, false) && sequence.Expected == 2 && sequence.Errors == 1, "Wrong preserves order");
        Check(sequence.Take(2, false), "Retry correct index");
        Check(!sequence.Take(5, true) && sequence.Expected == 1 && sequence.Errors == 2, "Wrong resets order only");
        for (int i = 1; i <= 5; i++) Check(sequence.Take(i, true), "Complete sequence");
        Check(sequence.Expected == 6, "All five accepted");
        sequence.Reset(); Check(sequence.Expected == 1 && sequence.Errors == 0, "Sequence reset");

        var delivery = new MechanicModels.Delivery();
        Check(!delivery.Unload(), "Empty depot no score");
        Check(delivery.Pickup() && !delivery.Pickup(), "One cargo limit");
        Check(delivery.Delivered == 0, "Pickup is not delivery");
        Check(delivery.Unload() && !delivery.Unload() && delivery.Delivered == 1, "Unload exactly once");
        Check(delivery.Pickup() && delivery.Drop() && !delivery.Drop(), "Drop exactly once");
        Check(!delivery.HasCargo && delivery.Delivered == 1, "Drop preserves deliveries");
        Check(delivery.Pickup() && delivery.Unload() && delivery.Delivered == 2, "Delivery after drop");
        delivery.Reset(); Check(!delivery.HasCargo && delivery.Delivered == 0, "Delivery reset");

        foreach (var pair in new[] { (3, 6), (2, 6), (4, 8), (5, 10), (3, 9) })
        {
            var capacity = new MechanicModels.Capacity();
            Check(capacity.Unload() == 0, "Empty capacity unload");
            for (int trip = 0; trip < pair.Item2 / pair.Item1; trip++)
            {
                for (int i = 0; i < pair.Item1; i++) Check(capacity.Pickup(pair.Item1), "Fits capacity");
                Check(!capacity.Pickup(pair.Item1), "Capacity boundary rejects extra");
                Check(capacity.Unload() == pair.Item1 && capacity.Carried == 0, "Unload entire cargo");
                Check(capacity.Unload() == 0, "No repeated delivery");
            }
            Check(capacity.Delivered == pair.Item2, "Variant 16-20 target reachable");
            capacity.Reset(); Check(capacity.Carried == 0 && capacity.Delivered == 0, "Capacity reset");
        }

        foreach (var required in new[] { new[] { 2, 1, 0 }, new[] { 1, 1, 1 } })
        {
            var kit = new MechanicModels.Kit();
            Check(!kit.Take(-1, 1) && !kit.Take(3, 1), "Invalid kit types rejected");
            Check(!kit.Complete(required[0], required[1], required[2]), "Empty kit incomplete");
            for (int type = 0; type < 3; type++)
            {
                for (int i = 0; i < required[type]; i++) Check(kit.Take(type, required[type]), "Required kit item");
                Check(!kit.Take(type, required[type]), "Extra kit item rejected");
            }
            Check(kit.Complete(required[0], required[1], required[2]), "Exact kit complete");
            kit.Reset(); Check(kit.Count(0) == 0 && kit.Count(1) == 0 && kit.Count(2) == 0, "Kit reset");
        }

        var access = new MechanicModels.Access();
        Check(!access.Activate(-1) && !access.Activate(3), "Invalid access index rejected");
        Check(!access.All(2) && !access.All(3), "No access initially");
        Check(access.Activate(0) && !access.Activate(0), "Repeated switch is not second switch");
        Check(access.Enabled(0) && !access.Enabled(1) && !access.All(2), "Independent access flags");
        Check(access.Activate(1) && access.All(2) && !access.All(3), "Two distinct flags");
        Check(access.Activate(2) && access.All(3), "Three distinct flags");
        access.Reset(); Check(!access.Enabled(0) && !access.Enabled(1) && !access.Enabled(2), "Access reset");

        var contract = new CollectContract();
        var item = new Collectible();
        contract.createdObjects.Add(item.gameObject);
        contract.Collect(null); Check(contract.collected == 0, "Null callback ignored");
        contract.Collect(new Collectible()); Check(contract.collected == 0, "Foreign or obsolete item ignored");
        contract.IsPlaying = false; contract.Collect(item);
        Check(contract.collected == 0 && contract.createdObjects.Count == 1, "End state blocks collection");
        contract.IsPlaying = true; contract.Collect(item);
        Check(contract.collected == 1 && contract.DestroyCalls == 1 && contract.createdObjects.Count == 0, "First contact consumed");
        contract.Collect(item);
        Check(contract.collected == 1 && contract.DestroyCalls == 1, "Second callback before deferred destroy ignored");
        Check(contract.hint.Contains("1 из 5"), "Hint reflects accepted result");
        Console.WriteLine($"PASS: {assertions} assertions; 6 models and actual Collect body; Unity not executed");
    }
}
