using System.Data;
using System.Data.Common;
using System.Globalization;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace Otthonra.Api;

/// <summary>
/// Request-relative matching stays in MySQL: only the selected IDs and small
/// ranking values cross the database boundary. No candidate-side Take precedes
/// evaluation, and an exact-only query never evaluates geographic distances.
/// </summary>
public static class RecommendationSql
{
    public sealed record RankedPair(Guid PropertyId, Guid SearchRequestId, int Score, bool IsExact,
        bool LikedYou, decimal ValueForMoney, int Specificity, double DistanceSquared, double LocationDistanceKm);

    public sealed record Query(string Text, IReadOnlyDictionary<string, object?> Parameters);

    public static Query Build(User user, Property? property = null, SearchRequest? search = null,
        bool exact = true, bool existsOnly = false, string[]? boundingBoxesWkt = null, double? radiusKm = null)
    {
        if ((property is null) == (search is null)) throw new ArgumentException("Supply exactly one active entity.");
        var buyer = search is not null;
        var parameters = new Dictionary<string, object?> {
            ["userId"] = user.Id.ToString("D"), ["activeId"] = (search?.Id ?? property!.Id).ToString("D"),
            ["agent"] = AccountTypes.Agent, ["userIsAgent"] = user.AccountType == AccountTypes.Agent
        };
        string Array(string name, IEnumerable<string> values)
        {
            parameters[name] = JsonSerializer.Serialize(values.Distinct(StringComparer.Ordinal).ToArray());
            // These are canonical identities, not accent-insensitive labels.
            // Komló and Kömlő must remain different even on an older database
            // whose Properties/SearchLocations columns still use an AI collation.
            return $"SELECT j.`Value` COLLATE utf8mb4_bin FROM JSON_TABLE(@{name}, '$[*]' COLUMNS (`Value` VARCHAR(191) PATH '$')) AS j";
        }
        var activePrepared = buyer ? MatchingRanking.Prepare(search!) : null;
        string exactLocation;
        string geography;
        string geographicTargetExists;
        var buyerExactBranches=new List<string>();
        string? sellerExactIds=null;
        if (buyer)
        {
            var prepared = activePrepared!;
            var ids = LocationCatalog.All.Where(location => (location.Kind is "city" or "district")
                && (prepared.Cities.Contains(location.City) || prepared.DistrictIds.Contains(location.Id))).Select(location => location.Id);
            var places = Array("exactPlaces", ids);
            var neighborhoods = Array("exactNeighborhoods", prepared.NeighborhoodIds);
            var streets = Array("exactStreets", prepared.StreetIds);
            exactLocation = $"COALESCE((place.`Id` IN ({places}) OR EXISTS (SELECT 1 FROM `PropertyNeighborhoods` pn WHERE pn.`PropertyId`=p.`Id` AND pn.`NeighborhoodId` IN ({neighborhoods})) OR (NOT p.`HideStreet` AND street.`Id` IN ({streets}))),0)";
            parameters["wantedType"]=search!.Type;
            var typeGate=string.IsNullOrEmpty(search.Type)?"":"AND p.`Type`=@wantedType";
            // Each branch can start from an existing location-first index;
            // wrapping the property LocationId in a legacy CASE for every row
            // would otherwise prevent this cheap candidate lookup.
            buyerExactBranches.Add($"SELECT p.`Id` FROM `Properties` p WHERE p.`Archived`=0 {typeGate} AND p.`LocationId` IN ({places})");
            buyerExactBranches.Add($"SELECT pn.`PropertyId` AS `Id` FROM `PropertyNeighborhoods` pn WHERE pn.`NeighborhoodId` IN ({neighborhoods})");
            buyerExactBranches.Add($"SELECT p.`Id` FROM `Properties` p WHERE p.`Archived`=0 {typeGate} AND NOT p.`HideStreet` AND p.`StreetId` IN ({streets})");
            buyerExactBranches.Add($"SELECT p.`Id` FROM `Properties` p JOIN `MatchingLocationAreas` place ON place.`Id`=({PropertyLocationSql()}) COLLATE utf8mb4_bin AND place.`Kind` IN ('city','district') LEFT JOIN `StreetCatalog` street ON street.`Id`=p.`StreetId` AND street.`City` COLLATE utf8mb4_bin=place.`City` COLLATE utf8mb4_bin AND (street.`District` IS NULL OR place.`District` IS NULL OR street.`District` COLLATE utf8mb4_bin=place.`District` COLLATE utf8mb4_bin) WHERE p.`Archived`=0 {typeGate} AND TRIM(COALESCE(p.`LocationId`,''))='' AND {exactLocation}");
            var targets = Array("targetAreas", MatchingGeography.SelectedAreaIds(search!));
            geography = $"(SELECT MIN(ST_Distance({PointSql}, a.`Boundary`))/1000.0 FROM `MatchingLocationAreas` a WHERE a.`Id` IN ({targets}))";
            geographicTargetExists=$"EXISTS(SELECT 1 FROM `MatchingLocationAreas` a WHERE a.`Id` IN ({targets}))";
            parameters["specificity"] = prepared.Specificity;
        }
        else
        {
            var accepted = AcceptedLocations(property!);
            var acceptedSql = Array("acceptedLocations", accepted);
            sellerExactIds=$"SELECT DISTINCT sl.`SearchRequestId` AS `Id` FROM `SearchLocations` sl WHERE sl.`LocationId` IN ({acceptedSql})";
            exactLocation = $"EXISTS (SELECT 1 FROM `SearchLocations` sl WHERE sl.`SearchRequestId`=s.`Id` AND sl.`LocationId` IN ({acceptedSql}))";
            geography = $"(SELECT MIN(ST_Distance({PointSql}, a.`Boundary`))/1000.0 FROM `SearchLocations` gl JOIN `MatchingLocationMembers` lm ON lm.`SelectionId`=gl.`LocationId` COLLATE utf8mb4_bin JOIN `MatchingLocationAreas` a ON a.`Id`=lm.`AreaId` WHERE gl.`SearchRequestId`=s.`Id`)";
            geographicTargetExists="EXISTS(SELECT 1 FROM `SearchLocations` gl JOIN `MatchingLocationMembers` lm ON lm.`SelectionId`=gl.`LocationId` COLLATE utf8mb4_bin JOIN `MatchingLocationAreas` a ON a.`Id`=lm.`AreaId` WHERE gl.`SearchRequestId`=s.`Id`)";
        }
        var maxPrice = buyer ? "s.`MaxPrice`" : "COALESCE(s.`PublicMaxPrice`,s.`MaxPrice`)";
        var house = Equal("s.`Type`", "Ház");
        var flat = Equal("s.`Type`", "Lakás");
        var floorKnown = "(p.`Floor` IS NOT NULL AND p.`Floor` BETWEEN -5 AND 200 AND (p.`Floor`=0.5 OR MOD(p.`Floor`,1)=0))";
        var top = "(CASE WHEN p.`Floor`=0.5 AND p.`BuildingFloors`=0 THEN 0.5 ELSE p.`BuildingFloors` END)";
        var belowTop = $"({floorKnown} AND NOT p.`FloorIsUpperRange` AND p.`BuildingFloors` BETWEEN 0 AND 200 AND p.`Floor`<{top})";
        var aboveGround = $"({floorKnown} AND p.`Floor`>0)";
        var attic = "(s.`AtticPreference` NOT IN ('only','exclude') OR (s.`AtticPreference`='only' AND p.`IsAttic`=1) OR (s.`AtticPreference`='exclude' AND p.`IsAttic`=0))";
        var floorCount = Count("s.`FloorsJson`", "Floor");
        var floorMinimum = $"COALESCE((SELECT MIN(CASE WHEN f.`Value` BETWEEN 9 AND 11 AND p.`Floor`>=9 THEN 0 ELSE ABS((CASE WHEN f.`Value` BETWEEN 9 AND 11 THEN 9 ELSE f.`Value` END)-p.`Floor`)/5.0 END) FROM JSON_TABLE(COALESCE(s.`FloorsJson`,'[]'),'$[*]' COLUMNS (`Value` DECIMAL(10,2) PATH '$')) f),0)";
        var floorLoss = $"CASE WHEN {house} THEN 0 ELSE GREATEST(CASE WHEN {floorCount}=0 THEN 0 WHEN {floorKnown} THEN {floorMinimum} ELSE 1 END,CASE WHEN s.`ExcludeTopFloor` AND NOT COALESCE({belowTop},0) THEN 1 ELSE 0 END,CASE WHEN s.`ExcludeGroundFloorAndBelow` AND NOT COALESCE({aboveGround},0) THEN 1 ELSE 0 END,CASE WHEN NOT COALESCE({attic},0) THEN 1 ELSE 0 END) END";
        var condition = Rank("p.`Condition`", PropertyAttributes.Conditions, "Condition");
        var conditionMin = MinimumRank("s.`ConditionsJson`", PropertyAttributes.Conditions, "Condition");
        var energy = Rank("p.`EnergyRating`", PropertyAttributes.EnergyRatings, binary: true);
        var minEnergy = Rank("s.`MinEnergyRating`", PropertyAttributes.EnergyRatings, binary: true);
        var age = Rank("p.`ConstructionAge`", PropertyAttributes.ConstructionAges);
        var terms = new List<(string Alias, decimal Weight, string Loss)> {
            ("MinPriceLoss",MatchingRanking.MinPriceWeight,Minimum("p.`Price`","s.`MinPrice`")),
            ("MaxPriceLoss",MatchingRanking.MaxPriceWeight,Maximum("p.`Price`",maxPrice)),
            ("MinRoomsLoss",MatchingRanking.MinRoomsWeight,Minimum("p.`Rooms`","s.`MinRooms`")),
            ("MaxRoomsLoss",MatchingRanking.MaxRoomsWeight,Maximum("p.`Rooms`","s.`MaxRooms`")),
            ("MinAreaLoss",MatchingRanking.MinAreaWeight,Minimum("p.`Area`","s.`MinArea`")),
            ("MaxAreaLoss",MatchingRanking.MaxAreaWeight,Maximum("p.`Area`","s.`MaxArea`")),
            ("ConditionLoss",MatchingRanking.ConditionWeight,$"CASE WHEN {Count("s.`ConditionsJson`","Condition")}=0 THEN 0 WHEN {condition}<0 OR {conditionMin}<0 THEN 1 ELSE GREATEST(0,({conditionMin}-{condition})/3.0) END"),
            ("FloorLoss",MatchingRanking.FloorWeight,floorLoss),
            ("ElevatorLoss",MatchingRanking.ElevatorWeight,$"CASE WHEN NOT {house} AND s.`Elevator` AND NOT p.`Elevator` THEN 1 ELSE 0 END"),
            ("BalconyLoss",MatchingRanking.BalconyWeight,$"CASE WHEN NOT {house} AND s.`Balcony` AND COALESCE(p.`Balcony`,0)<>1 THEN 1 ELSE 0 END"),
            ("AirConditioningLoss",MatchingRanking.AirConditioningWeight,"CASE WHEN s.`AirConditioning` AND COALESCE(p.`AirConditioning`,0)<>1 THEN 1 ELSE 0 END"),
            ("PrivateGardenLoss",MatchingRanking.PrivateGardenWeight,$"CASE WHEN {flat} AND s.`PrivateGarden` AND COALESCE(p.`PrivateGarden`,0)<>1 THEN 1 ELSE 0 END"),
            ("BuildingLoss",MatchingRanking.BuildingWeight,CategoryLoss("p.`Building`","s.`BuildingsJson`",PropertyAttributes.Buildings)),
            ("HeatingLoss",MatchingRanking.HeatingWeight,CategoryLoss("p.`HeatingType`","s.`HeatingTypesJson`",PropertyAttributes.HeatingTypes,"Heating")),
            ("EnergyLoss",MatchingRanking.EnergyWeight,$"CASE WHEN s.`MinEnergyRating`='' THEN 0 WHEN p.`EnergyRatingScheme`<>'2023' OR {energy}<0 OR {minEnergy}<0 THEN 1 ELSE GREATEST(0,({minEnergy}-{energy})/11.0) END"),
            ("AgeLoss",MatchingRanking.AgeWeight,$"CASE WHEN {Count("s.`ConstructionAgesJson`")}=0 THEN 0 WHEN {age}<0 THEN 1 ELSE COALESCE((SELECT MIN(ABS({Rank("j.`Value`",PropertyAttributes.ConstructionAges)}-{age})/4.0) FROM {Items("s.`ConstructionAgesJson`")} j),1) END"),
            ("CeilingLoss",MatchingRanking.CeilingWeight,$"CASE WHEN TRIM(s.`CeilingHeight`)='' THEN 0 WHEN {Canonical("p.`CeilingHeight`",PropertyAttributes.CeilingHeights)}<>'' AND {Canonical("p.`CeilingHeight`",PropertyAttributes.CeilingHeights)}={Canonical("s.`CeilingHeight`",PropertyAttributes.CeilingHeights)} THEN 0 ELSE 1 END"),
            ("ViewLoss",MatchingRanking.ViewWeight,CategoryLoss("p.`View`","s.`ViewsJson`",PropertyAttributes.Views))
        };
        var q = string.Join(" + ", terms.Select(term => $"{Number(term.Weight)}*POW({term.Alias},2)"));
        if (!exact) q += $" + {Number(MatchingRanking.LocationWeight)}*POW(LocationDistanceKm/{MatchingRanking.LocationDistanceScaleKm.ToString("R",CultureInfo.InvariantCulture)},2)";
        var actorKind = buyer ? "search" : "property";
        var opposite = buyer ? "property" : "search";
        var owner = buyer ? "p" : "s";
        var oppositeOwner = buyer ? "p.`OwnerId`" : "s.`OwnerId`";
        // Availability has no score threshold: an otherwise valid outside
        // location is partial at every finite distance. Merely proving that a
        // point and a nonstreet target exist avoids calculating that distance.
        var outsideGeo=existsOnly?$"CASE WHEN {PointSql} IS NOT NULL AND {geographicTargetExists} THEN 0.0 ELSE NULL END":geography;
        var geo = exact ? "0.0" : $"CASE WHEN {exactLocation} THEN 0.0 ELSE {outsideGeo} END";
        var specificity = buyer ? "@specificity" : SpecificitySql(maxPrice, house, flat, conditionMin);
        var extraLocationGate = exact ? $"AND {exactLocation}" : "";
        var activeGate = buyer ? "s.`Id`=@activeId" : "p.`Id`=@activeId";
        var selectedColumns = $"p.`Id` AS PropertyId,s.`Id` AS SearchRequestId,{exactLocation} AS ExactLocation,{geo} AS LocationDistanceKm,EXISTS(SELECT 1 FROM `Decisions` incoming WHERE incoming.`PropertyId`=p.`Id` AND incoming.`SearchRequestId`=s.`Id` AND incoming.`ActorKind`='{opposite}' AND incoming.`Liked` AND incoming.`ActorUserId`={oppositeOwner}) AS LikedYou,{ValueForMoneySql()} AS ValueForMoney,{specificity} AS Specificity";
        var features = string.Join(",\n", terms.Select(term => $"({term.Loss}) AS {term.Alias}"));
        var exactPredicate = "(ExactLocation AND DistanceSquared=0)";
        var score = $"CASE WHEN {exactPredicate} THEN 100 ELSE LEAST(99,GREATEST(0,ROUND(CAST(100.0*EXP(-SQRT(DistanceSquared)) AS DECIMAL(30,12)),0))) END";
        var order = buyer ? "Score DESC,LikedYou DESC,ValueForMoney DESC,PropertyId,SearchRequestId"
            : "LikedYou DESC,Score DESC,Specificity DESC,PropertyId,SearchRequestId";
        var final = existsOnly ? "SELECT 1 FROM ranked LIMIT 1"
            : $"SELECT PropertyId,SearchRequestId,Score,IsExact,LikedYou,ValueForMoney,Specificity,DistanceSquared,LocationDistanceKm FROM ranked ORDER BY {order} LIMIT {RecommendationFeed.PageSize}";
        var coarseCte="";var coarseJoin="";var coarseSearchJoin="";
        if(buyer && (exact || boundingBoxesWkt is {Length:>0}))
        {
            // Exact canonical memberships (including a selected visible street)
            // must survive even when an old/synthetic coordinate is outside the
            // selected polygon. Only foreign-location candidates use the box.
            var pointBranches=(boundingBoxesWkt??[]).Select((box,index)=>{
                parameters["box"+index]=box;
                return $"SELECT boxpoint.`PropertyId` AS `Id` FROM `MatchingPropertyPoints` boxpoint WHERE MBRIntersects(boxpoint.`Position`,ST_GeomFromText(@box{index},4326,'axis-order=long-lat'))";
            });
            var branches=buyerExactBranches.Concat(pointBranches).ToList();
            coarseCte=$"""
                candidate_properties AS (
                    {string.Join(" UNION ",branches)}
                ),
                """;
            coarseJoin="JOIN candidate_properties candidates ON candidates.`Id`=p.`Id`";
        }
        else if(!buyer && (exact || radiusKm.HasValue))
        {
            var branches=new List<string>{sellerExactIds!};
            if(!exact && property!.Latitude is {} latitude && property.Longitude is {} longitude
                && ExpandedRectangle(new Bounds(longitude,latitude,longitude,latitude),radiusKm!.Value) is {} box)
            {
                parameters["west"]=box.West;parameters["east"]=box.East;parameters["south"]=box.South;parameters["north"]=box.North;
                // Original-geodesic padded bounds contain every polygon edge.
                // A metadata-only pass over ~7.5k places selects search IDs
                // before touching their criteria or expensive shape distance.
                branches.Add("SELECT sl.`SearchRequestId` AS `Id` FROM `MatchingLocationAreas` a JOIN `MatchingLocationMembers` lm ON lm.`AreaId`=a.`Id` JOIN `SearchLocations` sl ON sl.`LocationId` COLLATE utf8mb4_bin=lm.`SelectionId` WHERE a.`West`<=@east AND a.`East`>=@west AND a.`South`<=@north AND a.`North`>=@south");
            }
            coarseCte=$"candidate_searches AS ({string.Join(" UNION ",branches)}),";
            coarseSearchJoin="JOIN candidate_searches candidates ON candidates.`Id`=s.`Id`";
        }
        var activeOwner=buyer?"s":"p";
        var sql = $"""
            WITH {coarseCte} features AS (
                SELECT {selectedColumns},
                    {features}
                FROM `Properties` p
                {coarseJoin}
                JOIN `SearchRequests` s ON {activeGate}
                {coarseSearchJoin}
                JOIN `Users` owner ON owner.`Id`={owner}.`OwnerId`
                JOIN `MatchingLocationAreas` place ON place.`Id`=({PropertyLocationSql()}) COLLATE utf8mb4_bin AND place.`Kind` IN ('city','district')
                LEFT JOIN `StreetCatalog` street ON street.`Id`=p.`StreetId` AND street.`City` COLLATE utf8mb4_bin=place.`City` COLLATE utf8mb4_bin
                    AND (street.`District` IS NULL OR place.`District` IS NULL OR street.`District` COLLATE utf8mb4_bin=place.`District` COLLATE utf8mb4_bin)
                LEFT JOIN `MatchingPropertyPoints` pp ON pp.`PropertyId`=p.`Id`
                WHERE p.`Archived`=0 AND s.`Archived`=0 AND p.`OwnerId`<>s.`OwnerId`
                    AND {activeOwner}.`OwnerId`=@userId AND {owner}.`OwnerId`<>@userId AND (s.`Type`='' OR p.`Type`=s.`Type`)
                    AND (NOT @userIsAgent OR owner.`AccountType`<>@agent)
                    AND NOT EXISTS (SELECT 1 FROM `Decisions` d WHERE d.`PropertyId`=p.`Id` AND d.`SearchRequestId`=s.`Id` AND d.`ActorKind`='{actorKind}')
                    {extraLocationGate}
            ), distances AS (
                SELECT PropertyId,SearchRequestId,ExactLocation,LocationDistanceKm,LikedYou,ValueForMoney,Specificity,({q}) AS DistanceSquared
                FROM features WHERE LocationDistanceKm IS NOT NULL
            ), ranked AS (
                SELECT PropertyId,SearchRequestId,LocationDistanceKm,LikedYou,ValueForMoney,Specificity,DistanceSquared,{exactPredicate} AS IsExact,{score} AS Score
                FROM distances WHERE {(exact ? exactPredicate : "NOT " + exactPredicate)}
            )
            {final}
            """;
        return new Query(sql, parameters);
    }

    public static async Task<RankedPair[]> SelectAsync(AppDb db, User user, Property? property, SearchRequest? search,
        bool exact, CancellationToken cancellationToken = default)
    {
        if(!exact && search is not null && MatchingRanking.Prepare(search).HasNonStreetLocations)
        {
            var bounds=await ReadBoundsAsync(db,MatchingGeography.SelectedAreaIds(search),cancellationToken);
            if(bounds.Length>0)
                foreach(var radius in new[]{5d,20d,80d,320d})
                {
                    var boxes=ExpandedBoxes(bounds,radius);
                    if(boxes.Length==0)break;
                    var partial=await ReadRankedAsync(db,Build(user,property,search,exact:false,boundingBoxesWkt:boxes),cancellationToken);
                    // Strict inequality preserves every rounded-score tie and
                    // its incoming-like/value tie breakers. At equal scores we
                    // expand, rather than silently using a nearest-N shortcut.
                    var outsideUpperScore=MatchingRanking.ScoreFromDistanceSquared((double)MatchingRanking.LocationWeight
                        *Math.Pow(radius/MatchingRanking.LocationDistanceScaleKm,2));
                    if(partial.Length==RecommendationFeed.PageSize && outsideUpperScore<partial[^1].Score)return partial;
                }
        }
        else if(!exact && property is not null && property.Latitude is {} latitude && property.Longitude is {} longitude
            && double.IsFinite(latitude) && double.IsFinite(longitude))
        {
            // Incoming interest has higher priority than percentage for the
            // seller. The count is an upper bound (it may include an invalid
            // location), so it can only prevent an early stop, never hide one.
            var incomingCount=await CountIncomingAsync(db,user,property,cancellationToken);
            foreach(var radius in new[]{5d,20d,80d,320d})
            {
                if(ExpandedRectangle(new Bounds(longitude,latitude,longitude,latitude),radius) is null)break;
                var partial=await ReadRankedAsync(db,Build(user,property,search,exact:false,radiusKm:radius),cancellationToken);
                var outsideUpperScore=MatchingRanking.ScoreFromDistanceSquared((double)MatchingRanking.LocationWeight
                    *Math.Pow(radius/MatchingRanking.LocationDistanceScaleKm,2));
                if(partial.Length==RecommendationFeed.PageSize && outsideUpperScore<partial[^1].Score
                    && (partial[^1].LikedYou || partial.Count(candidate=>candidate.LikedYou)>=incomingCount))return partial;
            }
        }
        return await ReadRankedAsync(db,Build(user,property,search,exact),cancellationToken);
    }

    private static async Task<RankedPair[]> ReadRankedAsync(AppDb db,Query query,CancellationToken cancellationToken)
    {
        return await ExecuteAsync(db,query,async reader => {
            var result = new List<RankedPair>(RecommendationFeed.PageSize);
            while (await reader.ReadAsync(cancellationToken))
                result.Add(new(reader.GetGuid(0),reader.GetGuid(1),Convert.ToInt32(reader.GetValue(2)),
                    Convert.ToBoolean(reader.GetValue(3)),Convert.ToBoolean(reader.GetValue(4)),Convert.ToDecimal(reader.GetValue(5)),
                    Convert.ToInt32(reader.GetValue(6)),Convert.ToDouble(reader.GetValue(7)),Convert.ToDouble(reader.GetValue(8))));
            return result.ToArray();
        },cancellationToken);
    }

    private sealed record Bounds(double West,double South,double East,double North);
    private static async Task<int> CountIncomingAsync(AppDb db,User user,Property property,CancellationToken cancellationToken)
    {
        var query=new Query("""
            SELECT COUNT(DISTINCT s.`Id`) FROM `Decisions` incoming
            JOIN `SearchRequests` s ON s.`Id`=incoming.`SearchRequestId`
            JOIN `Users` owner ON owner.`Id`=s.`OwnerId`
            WHERE incoming.`PropertyId`=@propertyId AND incoming.`ActorKind`='search' AND incoming.`Liked`=1
                AND incoming.`ActorUserId`=s.`OwnerId` AND s.`OwnerId`<>@userId AND s.`Archived`=0
                AND (s.`Type`='' OR s.`Type`=@type) AND (NOT @agent OR owner.`AccountType`<>@agentType)
                AND NOT EXISTS(SELECT 1 FROM `Decisions` previous WHERE previous.`PropertyId`=@propertyId
                    AND previous.`SearchRequestId`=s.`Id` AND previous.`ActorKind`='property')
            """,new Dictionary<string,object?>{["propertyId"]=property.Id.ToString("D"),["userId"]=user.Id.ToString("D"),["type"]=property.Type,
                ["agent"]=user.AccountType==AccountTypes.Agent,["agentType"]=AccountTypes.Agent});
        return await ExecuteAsync(db,query,async reader=>{
            await reader.ReadAsync(cancellationToken);return Convert.ToInt32(reader.GetValue(0));
        },cancellationToken);
    }
    private static async Task<Bounds[]> ReadBoundsAsync(AppDb db,string[] ids,CancellationToken cancellationToken)
    {
        var query=new Query("SELECT `West`,`South`,`East`,`North` FROM `MatchingLocationAreas` WHERE `Id` IN (SELECT j.`Value` COLLATE utf8mb4_bin FROM JSON_TABLE(@ids,'$[*]' COLUMNS (`Value` VARCHAR(255) PATH '$')) j)",
            new Dictionary<string,object?>{["ids"]=JsonSerializer.Serialize(ids)});
        return await ExecuteAsync(db,query,async reader=>{
            var rows=new List<Bounds>();
            while(await reader.ReadAsync(cancellationToken))rows.Add(new(reader.GetDouble(0),reader.GetDouble(1),reader.GetDouble(2),reader.GetDouble(3)));
            return rows.ToArray();
        },cancellationToken);
    }

    private static string[] ExpandedBoxes(Bounds[] source,double radiusKm)
    {
        var boxes=new List<Bounds>();
        foreach(var row in source)
        {
            // WGS84 latitude degrees are at least 110km. Longitude uses the
            // highest latitude reachable by a radius-long geodesic, therefore
            // this rectangle is conservative rather than a distance filter.
            var rectangle=ExpandedRectangle(row,radiusKm);
            if(rectangle is null)return [];
            var next=rectangle;
            for(var index=0;index<boxes.Count;)
            {
                var previous=boxes[index];
                if(next.West<=previous.East && next.East>=previous.West && next.South<=previous.North && next.North>=previous.South)
                {
                    next=new(Math.Min(next.West,previous.West),Math.Min(next.South,previous.South),Math.Max(next.East,previous.East),Math.Max(next.North,previous.North));
                    boxes.RemoveAt(index);index=0;
                }
                else index++;
            }
            boxes.Add(next);
        }
        // Disjoint selections remain correct with a larger enclosing box; this
        // caps SQL branch/parameter count without removing any eligible point.
        if(boxes.Count>16)boxes=[new(boxes.Min(box=>box.West),boxes.Min(box=>box.South),boxes.Max(box=>box.East),boxes.Max(box=>box.North))];
        return boxes.Select(box=>FormattableString.Invariant($"POLYGON(({box.West:R} {box.South:R},{box.East:R} {box.South:R},{box.East:R} {box.North:R},{box.West:R} {box.North:R},{box.West:R} {box.South:R}))")).ToArray();
    }

    private static Bounds? ExpandedRectangle(Bounds row,double radiusKm)
    {
        var latitudeMargin=radiusKm/110d;
        var maximumLatitude=Math.Max(Math.Abs(row.South),Math.Abs(row.North))+latitudeMargin;
        if(maximumLatitude>=89d)return null;
        var longitudeMargin=radiusKm/(110d*Math.Cos(maximumLatitude*Math.PI/180d));
        return new(Math.Max(-179.999999999d,row.West-longitudeMargin),Math.Max(-90d,row.South-latitudeMargin),
            Math.Min(180d,row.East+longitudeMargin),Math.Min(90d,row.North+latitudeMargin));
    }

    public static async Task<bool> ExistsAsync(AppDb db, User user, Property? property, SearchRequest? search,
        bool exact, CancellationToken cancellationToken = default) =>
        await ExecuteAsync(db,Build(user,property,search,exact,existsOnly:true),async reader => await reader.ReadAsync(cancellationToken),cancellationToken);

    private static async Task<T> ExecuteAsync<T>(AppDb db, Query query, Func<DbDataReader,Task<T>> read, CancellationToken cancellationToken)
    {
        var connection = db.Database.GetDbConnection();
        var openedHere = connection.State != ConnectionState.Open;
        if (openedHere) await db.Database.OpenConnectionAsync(cancellationToken);
        try
        {
            await using var command = connection.CreateCommand();
            command.CommandText=query.Text; command.CommandTimeout=30;
            command.Transaction=db.Database.CurrentTransaction?.GetDbTransaction();
            foreach(var (name,value) in query.Parameters)
            {
                var parameter=command.CreateParameter();parameter.ParameterName="@"+name;parameter.Value=value??DBNull.Value;
                command.Parameters.Add(parameter);
            }
            await using var reader=await command.ExecuteReaderAsync(cancellationToken);
            return await read(reader);
        }
        finally { if(openedHere) await db.Database.CloseConnectionAsync(); }
    }

    // SaveChanges and the bounded startup backfill maintain this verified point
    // atomically. Use the same source as direct-pair/decision eligibility.
    private const string PointSql = "pp.`Position`";
    private static string Number(decimal value)=>value.ToString(CultureInfo.InvariantCulture);
    private static string Literal(string value)=>"_utf8mb4'"+value.Replace("'","''")+"'";
    private static string Equal(string expression,string value)=>$"TRIM({expression}) COLLATE utf8mb4_0900_ai_ci={Literal(value)} COLLATE utf8mb4_0900_ai_ci";
    private static string Minimum(string value,string minimum)=>$"CASE WHEN {minimum}>0 THEN GREATEST(0,({minimum}-{value})/{minimum}) ELSE 0 END";
    private static string Maximum(string value,string maximum)=>$"CASE WHEN {maximum} IS NULL THEN 0 WHEN {maximum}>0 THEN GREATEST(0,({value}-{maximum})/{maximum}) WHEN {value}>{maximum} THEN 1 ELSE 0 END";
    private static string Items(string json)=>$"JSON_TABLE(COALESCE({json},'[]'),'$[*]' COLUMNS (`Value` VARCHAR(200) PATH '$'))";
    private static string Count(string json,string kind="")
    {
        // Match CompiledSearch's sets, rather than counting raw legacy JSON:
        // 9/10/11 are one floor bucket, and heating/condition aliases can name
        // the same choice more than once. BINARY preserves ordinal identity of
        // unknown legacy labels after known choices have been canonicalized.
        if(kind=="Floor" || json.Contains("FloorsJson",StringComparison.Ordinal))
            return $"(SELECT COUNT(DISTINCT CASE WHEN counted.`Value` BETWEEN 9 AND 11 THEN 9 ELSE counted.`Value` END) FROM JSON_TABLE(COALESCE({json},'[]'),'$[*]' COLUMNS (`Value` DECIMAL(10,2) PATH '$')) counted)";
        var options=kind=="Condition" || json.Contains("ConditionsJson",StringComparison.Ordinal)?PropertyAttributes.Conditions
            :json.Contains("BuildingsJson",StringComparison.Ordinal)?PropertyAttributes.Buildings
            :json.Contains("HeatingTypesJson",StringComparison.Ordinal)?PropertyAttributes.HeatingTypes
            :json.Contains("ConstructionAgesJson",StringComparison.Ordinal)?PropertyAttributes.ConstructionAges
            :json.Contains("ViewsJson",StringComparison.Ordinal)?PropertyAttributes.Views:null;
        if(options is null)return $"COALESCE(JSON_LENGTH({json}),0)";
        var normalization=ReferenceEquals(options,PropertyAttributes.Conditions)?"Condition"
            :ReferenceEquals(options,PropertyAttributes.HeatingTypes)?"Heating":"";
        var canonical=Canonical("counted.`Value`",options,normalization);
        var value=$"COALESCE(NULLIF({canonical},''),TRIM(COALESCE(counted.`Value`,'')))";
        return $"(SELECT COUNT(DISTINCT CAST(({value}) AS BINARY)) FROM {Items(json)} counted)";
    }
    private static Dictionary<string,string> Aliases(string kind)=>kind switch {
            "Condition"=>new Dictionary<string,string>{{"Felújított","Új/felújított"},{"Újszerű","Új/felújított"},{"Új építésű","Új/felújított"},{"Jó állapotú","Jó"}},
            "Heating"=>new Dictionary<string,string>{{"Gázkazán","Gázkazán / cirkó"},{"Gázcirkó","Gázkazán / cirkó"},{"Klíma","Fűtő klíma"},{"Vegyes tüzelésű kazán","Fa- / vegyes tüzelésű kazán"},{"Vegyes tüezelésű kazán","Fa- / vegyes tüzelésű kazán"},{"Cserépkályha","Kályha / cserépkályha"}},
            _=>new Dictionary<string,string>()
        };
    private static string Canonical(string expression,string[] options,string kind="")
    {
        var cases=Aliases(kind).Concat(options.Select(option=>new KeyValuePair<string,string>(option,option)));
        return "(CASE "+string.Join(" ",cases.Select(pair=>$"WHEN {Equal(expression,pair.Key)} THEN {Literal(pair.Value)}"))+" ELSE '' END)";
    }
    private static string Rank(string expression,string[] options,string kind="",bool binary=false)
    {
        if(binary)return "(CASE "+string.Join(" ",options.Select((value,index)=>$"WHEN BINARY {expression}=BINARY {Literal(value)} THEN {index}"))+" ELSE -1 END)";
        var labels=Aliases(kind).Concat(options.Select(option=>new KeyValuePair<string,string>(option,option)));
        return "(CASE "+string.Join(" ",labels.Select(pair=>$"WHEN {Equal(expression,pair.Key)} THEN {Array.IndexOf(options,pair.Value)}"))+" ELSE -1 END)";
    }
    private static string MinimumRank(string json,string[] options,string kind="")=>
        $"COALESCE((SELECT MIN({Rank("j.`Value`",options,kind)}) FROM {Items(json)} j),-1)";
    private static string CategoryLoss(string property,string selected,string[] options,string kind="")=>
        $"CASE WHEN {Count(selected)}=0 THEN 0 WHEN {Canonical(property,options,kind)}<>'' AND EXISTS(SELECT 1 FROM {Items(selected)} j WHERE {Canonical("j.`Value`",options,kind)}={Canonical(property,options,kind)}) THEN 0 ELSE 1 END";

    private static string PropertyLocationSql()
    {
        // Current rows always use their strict canonical identity. For old
        // free-text rows prefer a case-insensitive, accent-sensitive city name
        // through the (City,Kind) index. Accent folding is only a fallback and
        // may resolve exactly one city: bare "Komlo" must not choose between
        // Komló and Kömlő arbitrarily.
        var cityLabel=$"TRIM(p.`City`) COLLATE {MatchingGeography.CityLabelCollation}";
        var exactCity=$"(SELECT legacy_city.`Id` FROM `MatchingLocationAreas` legacy_city WHERE legacy_city.`Kind`='city' AND legacy_city.`City`={cityLabel} LIMIT 1)";
        var uniqueFoldedCity="(SELECT MIN(folded_city.`Id`) FROM `MatchingLocationAreas` folded_city WHERE folded_city.`Kind`='city' AND folded_city.`City` COLLATE utf8mb4_0900_ai_ci=TRIM(p.`City`) COLLATE utf8mb4_0900_ai_ci HAVING COUNT(*)=1)";
        var city=$"COALESCE({exactCity},{uniqueFoldedCity})";
        var fromCity=LegacyDistrictSql("p.`City`");
        var fromDistrict=LegacyDistrictSql("p.`District`");
        var legacy=$"CASE WHEN TRIM(p.`City`) COLLATE utf8mb4_0900_ai_ci LIKE _utf8mb4'Budapest %' COLLATE utf8mb4_0900_ai_ci THEN {fromCity} WHEN {city}='city:Budapest' AND TRIM(COALESCE(p.`District`,''))<>'' THEN {fromDistrict} ELSE {city} END";
        return $"CASE WHEN TRIM(COALESCE(p.`LocationId`,''))<>'' THEN p.`LocationId` ELSE {legacy} END";
    }

    private static string LegacyDistrictSql(string expression)
    {
        // Same accepted legacy vocabulary as DistrictNumber: Roman or numeric
        // wards, optional Budapest/kerület text and periods (including the old
        // city label "Budapest II." without the word kerület).
        var marks=Literal("["+'\u0300'+"-"+'\u036f'+"]");
        var normalized=$"REGEXP_REPLACE(UPPER(TRIM(COALESCE({expression},''))),{marks},'')";
        foreach(var (accent,plain) in new[]{("Á","A"),("É","E"),("Í","I"),("Ó","O"),("Ö","O"),("Ő","O"),("Ú","U"),("Ü","U"),("Ű","U")})
            normalized=$"REPLACE({normalized},{Literal(accent)},{Literal(plain)})";
        var clean=$"TRIM(REPLACE(REPLACE(REPLACE({normalized},_utf8mb4'BUDAPEST',''),_utf8mb4'KERULET',''),'.',''))";
        var districts=LocationCatalog.All.Where(location=>location.Kind=="district").Select(location=>
            $"WHEN {Literal(location.District!.TrimEnd('.'))} THEN {Literal(location.Id)}");
        var numeric=$"CASE WHEN REGEXP_LIKE({clean},'^[0-9]+$') AND CAST({clean} AS UNSIGNED) BETWEEN 1 AND 23 THEN CONCAT('district:Budapest:',CAST({clean} AS UNSIGNED)) ELSE NULL END";
        return "(CASE "+clean+" COLLATE utf8mb4_0900_ai_ci "+string.Join(" ",districts)+" ELSE "+numeric+" END)";
    }

    private static string[] AcceptedLocations(Property property)
    {
        var place=LocationCatalog.ForProperty(property);
        if(place is null)return [];
        var values=new List<string>{"city:"+place.City};
        if(place.Kind=="district")values.Add(place.Id);
        if(MatchingRanking.VerifiedStreetId(property,place) is {} street)values.Add(street);
        values.AddRange(Dto.Strings(property.NeighborhoodIdsJson).Where(id=>NeighborhoodCatalog.Get(id)is not null));
        foreach(var area in LocationCatalog.All.Where(location=>location.Kind=="area"))
            if(MatchingRanking.Prepare(new SearchRequest{LocationIdsJson=JsonSerializer.Serialize(new[]{area.Id})}).Cities.Contains(place.City))values.Add(area.Id);
        return values.Distinct(StringComparer.Ordinal).ToArray();
    }

    private static string SpecificitySql(string maximum,string house,string flat,string conditionMinimum)
    {
        var cityCount="(SELECT COUNT(DISTINCT m.`AreaId`) FROM `SearchLocations` x JOIN `MatchingLocationMembers` m ON m.`SelectionId`=x.`LocationId` COLLATE utf8mb4_bin WHERE x.`SearchRequestId`=s.`Id` AND m.`AreaId` LIKE 'city:%')";
        var budapest="EXISTS(SELECT 1 FROM `SearchLocations` x JOIN `MatchingLocationMembers` m ON m.`SelectionId`=x.`LocationId` COLLATE utf8mb4_bin WHERE x.`SearchRequestId`=s.`Id` AND m.`AreaId`='city:Budapest')";
        var districts=$"(SELECT COUNT(*) FROM `SearchLocations` x WHERE x.`SearchRequestId`=s.`Id` AND x.`LocationId` LIKE 'district:%' AND NOT {budapest})";
        string Locations(string prefix)=>$"(SELECT COUNT(*) FROM `SearchLocations` x WHERE x.`SearchRequestId`=s.`Id` AND x.`LocationId` LIKE '{prefix}:%')";
        var coverage=$"({cityCount}+{districts}/23.0+{Locations("neighborhood")}/100.0+{Locations("street")}/10000.0)";
        var selected=new List<string>{$"CASE WHEN {coverage}>0 THEN 8.0/(1.0+LOG2(1.0+{coverage})) ELSE 0 END"};
        var total=new List<string>{"8"};
        void Add(string key,string strength,string applicable="1")
        {
            var weight=Number(MatchingRanking.SpecificityWeight(key));
            selected.Add($"CASE WHEN {applicable} THEN {weight}*LEAST(1,GREATEST(0,{strength})) ELSE 0 END");
            total.Add($"CASE WHEN {applicable} THEN {weight} ELSE 0 END");
        }
        void Bounds(string minimum,string max,string minKey,string maxKey)
        {
            var strength=$"CASE WHEN {minimum}>0 AND {max} IS NOT NULL THEN 0.5+0.5*LEAST(1,GREATEST(0,CASE WHEN {max}>0 THEN {minimum}/{max} ELSE 1 END)) ELSE 0.5 END";
            Add(minKey,$"CASE WHEN {minimum}>0 THEN {strength} ELSE 0 END");
            Add(maxKey,$"CASE WHEN {max} IS NOT NULL THEN {strength} ELSE 0 END");
        }
        string Category(string json,int options)=>$"CASE WHEN {Count(json)}>0 THEN 1.0/SQRT(LEAST({Count(json)},{options})) ELSE 0 END";
        Bounds("s.`MinPrice`",maximum,"minPrice","maxPrice");
        Bounds("s.`MinArea`","s.`MaxArea`","minArea","maxArea");
        Bounds("s.`MinRooms`","s.`MaxRooms`","minRooms","maxRooms");
        Add("condition",$"CASE WHEN {conditionMinimum}>=0 THEN ({conditionMinimum}+1)/4.0 ELSE 0 END");
        Add("building",Category("s.`BuildingsJson`",PropertyAttributes.Buildings.Length));
        Add("heatingType",Category("s.`HeatingTypesJson`",PropertyAttributes.HeatingTypes.Length));
        var energy=Rank("s.`MinEnergyRating`",PropertyAttributes.EnergyRatings,binary:true);
        Add("minEnergyRating",$"CASE WHEN {energy}>=0 THEN ({energy}+1)/12.0 ELSE 0 END");
        Add("constructionAge",Category("s.`ConstructionAgesJson`",PropertyAttributes.ConstructionAges.Length));
        Add("view",Category("s.`ViewsJson`",PropertyAttributes.Views.Length));
        Add("ceilingHeight","CASE WHEN TRIM(s.`CeilingHeight`)<>'' THEN 1 ELSE 0 END");
        Add("airConditioning","s.`AirConditioning`");
        Add("privateGarden","s.`PrivateGarden`",flat);
        Add("floor",$"GREATEST({Category("s.`FloorsJson`",12)},CASE WHEN s.`ExcludeTopFloor` OR s.`ExcludeGroundFloorAndBelow` OR s.`AtticPreference`<>'' THEN 1 ELSE 0 END)","NOT "+house);
        Add("elevator","s.`Elevator`","NOT "+house);
        Add("balcony","s.`Balcony`","NOT "+house);
        return $"LEAST(100,GREATEST(0,ROUND(CAST(100.0*({string.Join("+",selected)})/({string.Join("+",total)}) AS DECIMAL(30,12)),0)))";
    }

    private static string ValueForMoneySql()
    {
        var house=Equal("p.`Type`","Ház");var flat=Equal("p.`Type`","Lakás");
        var condition=Rank("p.`Condition`",PropertyAttributes.Conditions,"Condition");
        var building=Canonical("p.`Building`",PropertyAttributes.Buildings);
        var age=Rank("p.`ConstructionAge`",PropertyAttributes.ConstructionAges);
        var view=Canonical("p.`View`",PropertyAttributes.Views);
        var heating=Canonical("p.`HeatingType`",PropertyAttributes.HeatingTypes,"Heating");
        var energy="UPPER(TRIM(p.`EnergyRating`))";
        var parking="COALESCE(p.`ParkingTypesJson`,JSON_ARRAY(p.`ParkingType`))";
        var garage=$"EXISTS(SELECT 1 FROM {Items(parking)} j WHERE TRIM(j.`Value`) COLLATE utf8mb4_0900_ai_ci IN ('Garázs','Mélygarázs','Teremgarázs'))";
        var driveway=$"EXISTS(SELECT 1 FROM {Items(parking)} j WHERE TRIM(j.`Value`) COLLATE utf8mb4_0900_ai_ci IN ('Fedett beálló','Udvari beálló'))";
        var floorKnown="(p.`Floor` IS NOT NULL AND p.`Floor` BETWEEN -5 AND 200 AND (p.`Floor`=0.5 OR MOD(p.`Floor`,1)=0))";
        var quality=new[]{
            $"GREATEST(0,{condition})/3.0*0.05",
            $"CASE WHEN {building}='Passzívház' THEN 0.02 WHEN {building} IN ('Tégla','Kő és tégla','Fa','Rönkház','Könnyűszerkezet') THEN 0.015 WHEN {building}='Panel' THEN 0.01 WHEN {building}<>'' THEN 0.005 ELSE 0 END",
            $"CASE WHEN {age}<0 THEN 0 ELSE (4-{age})/4.0*0.025 END",
            $"CASE {view} WHEN 'Panorámás' THEN 0.015 WHEN 'Kertre néző' THEN 0.01 WHEN 'Udvari' THEN 0.005 ELSE 0 END",
            $"CASE WHEN {heating}='Hőszivattyú' THEN 0.025 WHEN {heating} IN ('Gázkazán / cirkó','Távfűtés','Házközponti fűtés') THEN 0.015 WHEN {heating}<>'' AND {heating}<>'Nincs fűtés' THEN 0.005 ELSE 0 END",
            "CASE WHEN p.`Insulated`=1 THEN 0.015 ELSE 0 END",
            $"CASE WHEN REGEXP_LIKE({energy},'^(AA?|A[1-4])[+]{{0,3}}$') THEN 0.02 WHEN REGEXP_LIKE({energy},'^BB?[+]{{0,3}}$') THEN 0.015 WHEN REGEXP_LIKE({energy},'^CC?[+]{{0,3}}$') THEN 0.005 ELSE 0 END",
            "CASE WHEN p.`AirConditioning`=1 THEN 0.01 ELSE 0 END",
            $"CASE WHEN {flat} AND p.`PrivateGarden`=1 THEN 0.015 ELSE 0 END",
            "CASE WHEN p.`SolarPanels`=1 THEN 0.015 ELSE 0 END",
            $"CASE WHEN {garage} THEN 0.015 WHEN {driveway} THEN 0.01 ELSE 0 END",
            $"CASE WHEN {Canonical("p.`CeilingHeight`",PropertyAttributes.CeilingHeights)}='3 m feletti' THEN 0.005 ELSE 0 END",
            $"CASE WHEN NOT {house} AND {floorKnown} AND p.`Floor` BETWEEN 0 AND 3 THEN 0.005 ELSE 0 END",
            $"CASE WHEN NOT {house} AND p.`Balcony`=1 THEN 0.01 ELSE 0 END",
            $"CASE WHEN NOT {house} AND p.`Elevator`=1 THEN 0.01 ELSE 0 END",
            "LEAST(1,GREATEST(0,p.`Rooms`)/(p.`Area`/25.0))*0.005"
        };
        return $"CASE WHEN p.`Area`<=0 OR p.`Price`<=0 THEN 0 ELSE (p.`Area`+CASE WHEN {house} THEN 0.04*LEAST(GREATEST(0,COALESCE(p.`LotArea`,0)),5*p.`Area`) ELSE 0 END)/(p.`Price`/1000000.0)*(1+LEAST(0.25,{string.Join("+",quality)})) END";
    }
}
