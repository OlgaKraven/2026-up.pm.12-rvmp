// Учебные модели правил. Unity-объекты и интерфейс подключаются отдельно.
public static class MechanicModels
{
    public sealed class Selection
    {
        public int Progress { get; private set; }
        public int Errors { get; private set; }
        public bool Take(bool correct)
        {
            if (!correct) { Errors++; return false; }
            Progress++; return true;
        }
        public void Reset() { Progress = 0; Errors = 0; }
    }

    public sealed class Sequence
    {
        public int Expected { get; private set; } = 1;
        public int Errors { get; private set; }
        public bool Take(int index, bool resetOnError)
        {
            if (index != Expected)
            {
                Errors++;
                if (resetOnError) Expected = 1;
                return false;
            }
            Expected++; return true;
        }
        public void Reset() { Expected = 1; Errors = 0; }
    }

    public sealed class Delivery
    {
        public bool HasCargo { get; private set; }
        public int Delivered { get; private set; }
        public bool Pickup()
        {
            if (HasCargo) return false;
            HasCargo = true; return true;
        }
        public bool Unload()
        {
            if (!HasCargo) return false;
            HasCargo = false; Delivered++; return true;
        }
        public bool Drop()
        {
            if (!HasCargo) return false;
            HasCargo = false; return true;
        }
        public void Reset() { HasCargo = false; Delivered = 0; }
    }

    public sealed class Capacity
    {
        public int Carried { get; private set; }
        public int Delivered { get; private set; }
        public bool Pickup(int capacity)
        {
            if (Carried >= capacity) return false;
            Carried++; return true;
        }
        public int Unload()
        {
            int amount = Carried; Delivered += amount; Carried = 0;
            return amount;
        }
        public void Reset() { Carried = 0; Delivered = 0; }
    }

    public sealed class Kit
    {
        private readonly int[] counts = new int[3];
        public int Count(int type) => counts[type];
        public bool Take(int type, int required)
        {
            if (type < 0 || type >= counts.Length || counts[type] >= required)
                return false;
            counts[type]++; return true;
        }
        public bool Complete(int a, int b, int c)
            => counts[0] >= a && counts[1] >= b && counts[2] >= c;
        public void Reset() { for (int i = 0; i < counts.Length; i++) counts[i] = 0; }
    }

    public sealed class Access
    {
        private readonly bool[] flags = new bool[3];
        public bool Activate(int index)
        {
            if (index < 0 || index >= flags.Length || flags[index]) return false;
            flags[index] = true; return true;
        }
        public bool Enabled(int index) => flags[index];
        public bool All(int required)
        {
            for (int i = 0; i < required; i++) if (!flags[i]) return false;
            return true;
        }
        public void Reset() { for (int i = 0; i < flags.Length; i++) flags[i] = false; }
    }
}
