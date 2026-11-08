namespace Otthonra.Api;

/// <summary>Only canonical, public traits influence the showcase; entity IDs stay internal.</summary>
internal sealed record LandingTraits(string Type, string Budget, string Area, string Rooms, string Owner, string[] Places)
{
    public IEnumerable<string> Keys()
    {
        yield return "type:" + Type;
        yield return "budget:" + Budget;
        yield return "area:" + Area;
        yield return "rooms:" + Rooms;
        yield return "owner:" + Owner;
        foreach (var place in Places) yield return "place:" + place;
    }

    public static string Bucket(decimal? value, params decimal[] boundaries)
    {
        if (value is null or <= 0) return "unknown";
        for (var index = 0; index < boundaries.Length; index++)
            if (value <= boundaries[index]) return index.ToString(System.Globalization.CultureInfo.InvariantCulture);
        return boundaries.Length.ToString(System.Globalization.CultureInfo.InvariantCulture);
    }

    public static LandingTraits From(LandingSearchTeaser value) => new(value.Type,
        Bucket(value.MaxPrice ?? value.MinPrice, 20_000_000m, 40_000_000m, 60_000_000m, 80_000_000m, 120_000_000m, 200_000_000m),
        Bucket(value.MaxArea ?? value.MinArea, 35m, 55m, 80m, 120m, 200m),
        Bucket(value.MaxRooms ?? value.MinRooms, 1m, 2m, 3m, 4m, 6m), value.OwnerAccountType,
        value.Locations.Distinct(StringComparer.Ordinal).ToArray());

    public static LandingTraits From(LandingPropertyTeaser value) => new(value.Type,
        Bucket(value.Price, 20_000_000m, 40_000_000m, 60_000_000m, 80_000_000m, 120_000_000m, 200_000_000m),
        Bucket(value.Area, 35m, 55m, 80m, 120m, 200m),
        Bucket(value.Rooms, 1m, 2m, 3m, 4m, 6m), value.OwnerAccountType, [value.Location]);
}

internal sealed record LandingCandidate<T>(Guid SourceId, T Value, LandingTraits Traits);

/// <summary>
/// A bounded union of independent reservoirs retains uncommon types, budgets and
/// dimensions even when the input contains thousands of otherwise similar rows.
/// Up to 48 uniformly ranked place groups supplement the numerical categories.
/// </summary>
internal sealed class LandingCandidatePool<T>(Random random)
{
    private sealed class Reservoir(int capacity)
    {
        private long seen;
        public List<LandingCandidate<T>> Items { get; } = [];
        public void Add(LandingCandidate<T> candidate, Random source)
        {
            seen++;
            if (Items.Count < capacity) Items.Add(candidate);
            else
            {
                var replacement = source.NextInt64(seen);
                if (replacement < capacity) Items[(int)replacement] = candidate;
            }
        }
    }
    private sealed record PlaceReservoir(uint Rank, Reservoir Rows);
    private readonly Reservoir uniform = new(64);
    private readonly Dictionary<string, Reservoir> types = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Reservoir> budgets = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Reservoir> areas = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Reservoir> rooms = new(StringComparer.Ordinal);
    private readonly Dictionary<string, PlaceReservoir> places = new(StringComparer.Ordinal);
    private readonly int placeSalt = random.Next();
    private List<Guid> previous = [];
    private const int PlaceLimit = 48;

    public void Add(LandingCandidate<T> candidate)
    {
        uniform.Add(candidate, random);
        AddCategory(types, candidate.Traits.Type, 16, candidate);
        AddCategory(budgets, candidate.Traits.Budget, 8, candidate);
        AddCategory(areas, candidate.Traits.Area, 8, candidate);
        AddCategory(rooms, candidate.Traits.Rooms, 8, candidate);
        foreach (var place in candidate.Traits.Places)
        {
            if (!places.TryGetValue(place, out var bucket))
            {
                var rank = unchecked((uint)HashCode.Combine(placeSalt, StringComparer.Ordinal.GetHashCode(place)));
                if (places.Count == PlaceLimit)
                {
                    var worst = places.MaxBy(item => item.Value.Rank);
                    if (rank >= worst.Value.Rank) continue;
                    places.Remove(worst.Key);
                }
                places[place] = bucket = new PlaceReservoir(rank, new Reservoir(4));
            }
            bucket.Rows.Add(candidate, random);
        }
    }

    private void AddCategory(Dictionary<string, Reservoir> collection, string key, int capacity, LandingCandidate<T> candidate)
    {
        if (!collection.TryGetValue(key, out var reservoir)) collection[key] = reservoir = new Reservoir(capacity);
        reservoir.Add(candidate, random);
    }

    private IEnumerable<LandingCandidate<T>> Candidates() => uniform.Items
        .Concat(types.Values.SelectMany(bucket => bucket.Items))
        .Concat(budgets.Values.SelectMany(bucket => bucket.Items))
        .Concat(areas.Values.SelectMany(bucket => bucket.Items))
        .Concat(rooms.Values.SelectMany(bucket => bucket.Items))
        .Concat(places.Values.SelectMany(bucket => bucket.Rows.Items))
        .DistinctBy(candidate => candidate.SourceId);

    public List<LandingCandidate<T>> Select(int limit)
    {
        var candidates = Candidates().ToList();
        // If there are alternatives, force at least one change in membership on
        // consecutive calls to the same snapshot. Prefer exchanging a common
        // member, preserving a sole representative of a rare type or price band.
        if (candidates.Count > limit && previous.Count > 0)
        {
            var frequencies = candidates.SelectMany(candidate => candidate.Traits.Keys())
                .GroupBy(key => key, StringComparer.Ordinal).ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal);
            var prior = candidates.Where(candidate => previous.Contains(candidate.SourceId)).ToArray();
            if (prior.Length > 0)
            {
                var costs = prior.Select(candidate => new {
                    Candidate = candidate,
                    Cost = candidate.Traits.Keys().Where(key => frequencies[key] == 1).Sum(UniqueWeight)
                }).ToArray();
                var minimum = costs.Min(item => item.Cost);
                var interchangeable = costs.Where(item => item.Cost == minimum).ToArray();
                var excluded = interchangeable[random.Next(interchangeable.Length)].Candidate.SourceId;
                candidates.RemoveAll(candidate => candidate.SourceId == excluded);
            }
        }

        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        var selected = new List<LandingCandidate<T>>();
        while (selected.Count < limit && candidates.Count > 0)
        {
            LandingCandidate<T>? best = null;
            var bestScore = double.NegativeInfinity;
            foreach (var candidate in candidates)
            {
                var score = Score(candidate.Traits, counts) + random.NextDouble() * .1;
                if (score > bestScore) { bestScore = score; best = candidate; }
            }
            selected.Add(best!);
            foreach (var key in best!.Traits.Keys()) counts[key] = counts.GetValueOrDefault(key) + 1;
            candidates.Remove(best);
        }
        for (var index = selected.Count - 1; index > 0; index--)
        {
            var other = random.Next(index + 1);
            (selected[index], selected[other]) = (selected[other], selected[index]);
        }
        if (selected.Count > 1 && selected.Select(candidate => candidate.SourceId).SequenceEqual(previous))
        {
            var first = selected[0]; selected.RemoveAt(0); selected.Add(first);
        }
        previous = selected.Select(candidate => candidate.SourceId).ToList();
        return selected;
    }

    private static double Score(LandingTraits traits, Dictionary<string, int> counts)
    {
        var typeCount = counts.GetValueOrDefault("type:" + traits.Type);
        var placeScore = traits.Places.Length == 0 ? 0 : traits.Places.Average(place => 1d / (1 + counts.GetValueOrDefault("place:" + place)));
        return (typeCount == 0 ? 100 : 0) + 8d / (1 + typeCount)
            + 4d / (1 + counts.GetValueOrDefault("budget:" + traits.Budget))
            + 3d * placeScore + 2d / (1 + counts.GetValueOrDefault("area:" + traits.Area))
            + 1.5d / (1 + counts.GetValueOrDefault("rooms:" + traits.Rooms))
            + .25d / (1 + counts.GetValueOrDefault("owner:" + traits.Owner));
    }

    private static double UniqueWeight(string key) => key.StartsWith("type:", StringComparison.Ordinal) ? 100
        : key.StartsWith("budget:", StringComparison.Ordinal) ? 4
        : key.StartsWith("place:", StringComparison.Ordinal) ? 3
        : key.StartsWith("area:", StringComparison.Ordinal) ? 2
        : key.StartsWith("rooms:", StringComparison.Ordinal) ? 1.5 : .25;
}
